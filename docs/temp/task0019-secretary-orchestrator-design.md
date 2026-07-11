# Task 0019: 秘书编排器（Secretary Orchestrator）深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核深度设计）、Task 0018（练习壳深度设计）

---

## 1. 定位与边界

### 1.1 一句话定位

秘书编排器是认知 OS 内核的「学习编排大脑」：它只读事件流与认知投影，不直接修改任何业务状态；它通过生成提案、触发计划、注入对话上下文三种方式，把认知状态转化为可执行的学习行动。

### 1.2 秘书编排器 vs 聊天机器人

| 维度 | 秘书编排器 | 聊天机器人 |
|------|-----------|-----------|
| 核心能力 | 观察、诊断、策略、编排 | 对话、回答、陪伴 |
| 状态修改 | **只通过事件建议，不直接写** | 可直接回复用户 |
| 输出形态 | 提案（Proposal）、计划请求、上下文包 | 消息文本 |
| 触发方式 | 事件驱动 + 定时检查 | 用户输入驱动 |
| 与模块关系 | 跨壳层协调者 | 通常只服务于对话壳 |

**关键原则：秘书不是用户聊天的对象，而是让各个壳层协同工作的编排者。** 用户可以在对话壳里与秘书「对话」，但对话壳只是秘书的一个展示面。

### 1.3 秘书编排器的职责（必须做）

| 职责 | 说明 |
|------|------|
| **事件感知** | 订阅所有学习事实事件与派生事件 |
| **情境评估** | 评估用户当前状态：认知负荷、疲劳、专注度、目标进度 |
| **认知诊断** | 基于事件与投影，识别薄弱点、停滞点、可扩展点 |
| **提案生成** | 生成具体、可执行、可接受的提案 |
| **计划请求** | 向规划壳发出「创建计划项」的请求 |
| **对话上下文注入** | 为对话壳提供当前学习状态、推荐话题、可用工具上下文 |
| **策略学习** | 根据用户对提案的采纳/忽略历史，调整推送策略 |
| **静默任务** | 预生成复习列表、预生成题目、预计算诊断报告 |

### 1.4 秘书编排器的禁止（不由它做）

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 直接更新认知投影 | 破坏 SSOT | 认知状态中心 |
| 直接创建/修改题目 | 属于练习壳 | 练习壳 |
| 直接创建/修改闪卡 | 属于闪卡壳 | 闪卡壳 |
| 直接读写用户对话消息 | 属于对话壳 | 对话壳 |
| 直接修改计划项状态 | 属于规划壳 | 规划壳 |
| 替用户做最终决定 | 用户拥有最终控制权 | 用户 |

### 1.5 秘书编排器在架构中的位置

```
┌─────────────────────────────────────────────────────────┐
│                       场景壳层                           │
│  对话壳  │  练习壳  │  闪卡壳  │  阅读壳  │  规划壳  │  知识树壳 │
│    ▲         ▲         ▲         ▲         ▲         ▲   │
│    │         │         │         │         │         │   │
│    └─────────┴─────────┴────┬────┴─────────┴─────────┘   │
│                             │                            │
│                    统一事件协议                            │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                  认知 OS 内核                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│
│  │  事件总线    │  │ 认知状态中心 │  │   秘书编排器         ││
│  │             │  │             │  │  ┌───────────────┐  ││
│  │             │  │             │  │  │ 感知 Perception│  ││
│  │             │  │             │  │  ├───────────────┤  ││
│  │             │  │             │  │  │ 诊断 Diagnosis │  ││
│  │             │  │             │  │  ├───────────────┤  ││
│  │             │  │             │  │  │ 策略 Strategy  │  ││
│  │             │  │             │  │  ├───────────────┤  ││
│  │             │  │             │  │  │ 行动 Action    │  ││
│  │             │  │             │  │  └───────────────┘  ││
│  └─────────────┘  └─────────────┘  └─────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

## 2. 领域模型

### 2.1 聚合根：UserOrchestrationProfile

```python
@dataclass
class UserOrchestrationProfile:
    """用户编排画像 — 秘书对用户的长期记忆与策略状态。"""

    user_id: str

    # 信任与疲劳
    trust_score: float = 0.5            # 0-1，越高用户越信任秘书提案
    fatigue_score: float = 0.0          # 0-1，越高越应减少打扰
    proactive_quota_today: int = 5      # 今日剩余可推送提案数
    last_proactive_at: datetime | None = None

    # 策略偏好
    enabled_modules: list[str] = field(default_factory=lambda: [
        "review_reminder", "fatigue_manager", "daily_brief", "behavior_trigger"
    ])
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"

    # 关系记忆：action_type:kp_id → {accept_count, ignore_count, last_at}
    relation_memory: dict[str, RelationMemoryEntry] = field(default_factory=dict)

    # 当前会话上下文（短期）
    current_context: OrchestrationContext | None = None

    version: int = 0
```

### 2.2 值对象

#### 2.2.1 Proposal（提案）

```python
@dataclass(frozen=True)
class Proposal:
    """协商提案 — 秘书向用户或系统提出的行动建议。"""

    id: str
    user_id: str

    emoji: str = ""
    title: str
    description: str = ""
    action_type: Literal[
        "review", "practice", "rest", "explore", "exam_prep",
        "plan", "deep_process", "daily_brief", "conversation"
    ]

    # 执行负载
    payload: dict = field(default_factory=dict)

    # 策略元数据
    priority: int = 3                   # 1-5，越小越紧急
    generated_by: str = ""              # 生成模块名
    insight_source: str = ""            # 来源分析函数/事件
    insight_evidence: list[str] = field(default_factory=list)  # 证据摘要

    # 用户交互
    overrideable: bool = True
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=_now)

    # 上下文
    correlation_id: str = ""            # 关联事件 ID
    caused_by_event_id: str | None = None
```

**设计要点：**
- 提案是**不可变建议**，不是命令。用户或系统可以采纳、忽略、修改。
- `insight_evidence` 让提案可解释，例如「近 3 次在该节点答错」「已 7 天未复习」。
- `action_type` 决定由哪个壳层执行。

#### 2.2.2 OrchestrationContext（编排上下文）

```python
@dataclass(frozen=True)
class OrchestrationContext:
    """某一时点用户情境的快照。"""

    user_id: str
    assessed_at: datetime

    # 学习状态
    is_cold_start: bool = False
    session_duration_min: float = 0.0
    recent_accuracy: float = 0.0
    questions_done_recently: int = 0
    engagement_streak: int = 0
    cognitive_load: float = 0.0
    estimated_energy: Literal["high", "normal", "low"] = "normal"

    # 时间情境
    is_quiet_hours: bool = False
    is_deep_focus: bool = False
    last_interaction_min_ago: float = 0.0

    # 目标情境
    active_goals: list[GoalContext] = field(default_factory=list)
    upcoming_deadline: datetime | None = None

    # 对话情境
    current_subject: str = ""
    last_conv_summary: str = ""
```

#### 2.2.3 SilentTask（静默任务）

```python
@dataclass(frozen=True)
class SilentTask:
    """秘书在后台执行的预计算任务。"""

    id: str
    user_id: str
    task_type: Literal[
        "prepare_review_list",
        "pre_generate_quiz",
        "compute_diagnosis",
        "generate_daily_brief",
        "expand_knowledge_graph",
    ]
    payload: dict = field(default_factory=dict)
    ready_at: datetime
    status: Literal["pending", "running", "ready", "failed"] = "pending"
    result_ref: str = ""                # 结果引用 ID
    priority: int = 3
```

### 2.3 诊断结果

```python
@dataclass(frozen=True)
class DiagnosisReport:
    """用户学习诊断报告。"""

    user_id: str
    snapshot_id: str
    generated_at: datetime

    weak_points: list[WeakPoint] = field(default_factory=list)
    stale_points: list[StalePoint] = field(default_factory=list)
    expansion_candidates: list[ExpansionCandidate] = field(default_factory=list)

    cognitive_load: float = 0.0
    forgetting_risk_score: float = 0.0
    overall_progress_pct: float = 0.0

    highlight: str = ""
    summary: str = ""
    source_findings: list[str] = field(default_factory=list)
```

---

## 3. 状态机

### 3.1 提案状态机

```
                    ┌─────────────┐
                    │   pending   │  （已生成，未推送）
                    └──────┬──────┘
                           │ push / 用户可见
                           ▼
                    ┌─────────────┐
                    │  presented  │  （已展示给用户/系统）
                    └──────┬──────┘
              ┌────────────┼────────────┐
              │            │            │
    accept    ▼   dismiss  ▼   expire   ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ accepted│  │dismissed│  │ expired │
        └────┬────┘  └────┬────┘  └─────────┘
             │            │
             ▼            ▼
        publish(ProposalAccepted)  publish(ProposalDismissed)
```

**关键规则：**
1. 提案生成后先进入 `pending`，由 PolicyEngine 决定是否推送。
2. `presented` 状态表示已到达用户/系统。
3. 用户采纳后发布 `ProposalAccepted`，由对应壳层执行。
4. 用户忽略后发布 `ProposalDismissed`，更新关系记忆。
5. 过期未交互自动转为 `expired`。

### 3.2 静默任务状态机

```
┌─────────┐   trigger   ┌─────────┐   start   ┌─────────┐   finish   ┌─────────┐
│ pending │ ──────────▶ │ running │ ────────▶ │  ready  │ ─────────▶ │ consumed│
└─────────┘             └────┬────┘           └─────────┘            └─────────┘
                             │
                             │ fail
                             ▼
                          ┌─────────┐
                          │ failed  │
                          └─────────┘
```

---

## 4. 事件协议

### 4.1 秘书编排器订阅的事件

| 事件 | 来源 | 用途 |
|------|------|------|
| `AnswerSubmitted` | 练习壳 | 实时判断薄弱点、生成复习提案 |
| `AnswerBehaviorRecorded` | 练习壳 | 结合行为遥测做更精准诊断 |
| `SessionCompleted` | 练习壳 | 会话总结、疲劳检测、下一步提案 |
| `ExamSubmitted` | 练习壳 | 生成诊断报告与备考计划 |
| `CognitiveStateChanged` | 认知中心 | 核心触发源，驱动大多数提案 |
| `CognitiveNodeMetadataChanged` | 认知中心 | 节点属性变化时调整计划 |
| `FlashCardReviewed` | 闪卡壳 | 复习结果影响诊断与计划 |
| `PlanItemCompleted` | 规划壳 | 计划完成后的后续行动 |
| `PlanItemOverdue` | 规划壳 | 逾期提醒与策略调整 |
| `ProposalAccepted` | 前端/系统 | 执行提案对应动作 |
| `ProposalDismissed` | 前端/系统 | 更新关系记忆 |
| `AssistantReplied` / `MessageClassified` | 对话壳 | 理解当前对话主题 |
| `ReadingNoteCreated` | 阅读壳 | 识别新的学习材料 |
| `NodeCreated` / `NodeLinked` | 知识树壳 | 知识图谱变化触发扩展 |

### 4.2 秘书编排器发布的事件

| 事件 | 消费者 | 说明 |
|------|--------|------|
| `ProposalGenerated` | 前端、对话壳、规划壳 | 生成的提案 |
| `ProposalAccepted` | 对应壳层 | 用户采纳 |
| `ProposalDismissed` | 秘书自身 | 用户忽略 |
| `PlanItemRequested` | 规划壳 | 请求创建计划项 |
| `SilentTaskCreated` | 秘书调度器 | 创建静默任务 |
| `SilentTaskCompleted` | 秘书自身 / 对话壳 | 静默任务完成 |
| `ConversationContextInjected` | 对话壳 | 注入对话上下文 |
| `DiagnosisReportGenerated` | 前端、对话壳、规划壳 | 诊断报告 |
| `SecretaryStrategyUpdated` | 自身 | 策略调整 |

### 4.3 核心事件 Schema

#### 4.3.1 ProposalGenerated

```python
@dataclass(frozen=True)
class ProposalGenerated(DomainEvent):
    user_id: str
    source_module: str = "secretary"
    proposal: Proposal
    context: OrchestrationContext
    presentation_channel: Literal["ui", "conversation", "planning", "silent"] = "ui"
```

#### 4.3.2 PlanItemRequested

```python
@dataclass(frozen=True)
class PlanItemRequested(DomainEvent):
    """秘书请求规划壳创建计划项。"""
    user_id: str
    source_module: str = "secretary"
    request_id: str
    target_type: str
    target_ref_id: str
    title: str
    description: str
    priority: int = 0
    linked_node_ids: list[str] = field(default_factory=list)
    requires_user_confirmation: bool = True
    estimated_minutes: int = 10
    proposed_scheduled_for: datetime | None = None
    requested_at: datetime = field(default_factory=datetime.now)
```

#### 4.3.3 ConversationContextInjected

```python
@dataclass(frozen=True)
class ConversationContextInjected(DomainEvent):
    """秘书向对话壳注入上下文。"""
    user_id: str
    source_module: str = "secretary"
    conv_id: str | None = None
    injection_type: Literal["topic_suggestion", "learning_state", "proposal", "reminder"]
    payload: dict
    expires_at: datetime | None = None
```

#### 4.3.4 DiagnosisReportGenerated

```python
@dataclass(frozen=True)
class DiagnosisReportGenerated(DomainEvent):
    user_id: str
    source_module: str = "secretary"
    report: DiagnosisReport
    visibility: Literal["user", "system", "both"] = "both"
```

---

## 5. 核心流程

### 5.1 事件驱动的提案生成流程

```
领域事件发生
  │
  ▼
SecretaryEventHandler 路由到对应模块
  │
  ▼
Perception Layer 更新 OrchestrationContext
  │
  ▼
Diagnosis Layer 生成/更新 DiagnosisReport
  │
  ▼
Strategy Layer 决定：是否生成提案？生成何种提案？何时推送？
  │
  ▼
ProposalGenerator 生成候选提案列表
  │
  ▼
PolicyEngine 过滤、去重、限流、降级
  │
  ▼
发布 ProposalGenerated
  │
  ▼
前端/对话壳/规划壳消费
```

### 5.2 会话完成后的秘书联动流程

```
练习壳 publish(SessionCompleted)
  │
  ▼
SecretaryEventHandler._on_session_completed
  │
  ▼
ContextEngine.assess(user_id) → 获取当前情境
  │
  ▼
判断是否疲劳：
  ├─ 是 → 生成 rest 提案
  └─ 否 → 继续
  │
  ▼
BehaviorTriggerModule.run_check(user_id) → 生成复习/扩展提案
  │
  ▼
PolicyEngine.filter(...) → 过滤后得到最终提案列表
  │
  ▼
发布 ProposalGenerated × N
  │
  ▼
用户采纳 practice 提案 → publish(ProposalAccepted)
  │
  ▼
练习壳订阅 → 创建新会话
```

### 5.3 对话上下文注入流程

```
对话壳准备回复 / 用户打开对话
  │
  ▼
对话壳调用 SecretaryOrchestrator.get_conversation_context(user_id, conv_id)
  │
  ▼
秘书读取：
  ├─ 最新认知投影
  ├─ 未处理提案
  ├─ 活跃计划项
  ├─ 最近学习事件
  └─ 用户偏好
  │
  ▼
组装 ConversationContextPayload
  │
  ▼
发布 ConversationContextInjected
  │
  ▼
对话壳把上下文注入 LLM prompt
```

---

## 6. 关键设计决策（多方案对比）

### 6.1 决策 1：提案生成模型

#### 方案 A：规则 + 轻量模板（推荐作为默认路径）

**核心思想：**
- 每个秘书模块（behavior_trigger、review、fatigue_manager）内置规则。
- 规则基于认知投影阈值（如 proficiency < 0.5 → practice 提案）。
- 模板化文案，可配置。

**优点：**
- 低延迟、低成本、可解释。
- 冷启动即可工作。
- 便于 A/B 测试和策略调整。

**缺点：**
- 复杂语义难覆盖。
- 文案可能机械化。

#### 方案 B：LLM 生成提案

**核心思想：**
- 把用户事件流、认知投影、目标、偏好打包成 prompt。
- LLM 直接生成提案列表（JSON 格式）。

**优点：**
- 文案自然、灵活。
- 可理解复杂情境（如「考试在即 + 多节点薄弱」）。

**缺点：**
- 成本高、延迟高。
- 输出不稳定，需要强 schema 约束。
- 难以解释为什么生成某个提案。

#### 方案 C：混合模型（推荐最终形态）

**核心思想：**
- 规则引擎生成候选提案骨架（action_type、priority、payload）。
- LLM 仅负责生成 `title`、`description`、`insight_evidence` 等文案。
- PolicyEngine 做最终过滤。

**优点：**
- 保留规则的可控性和 LLM 的表达力。
- 成本低于纯 LLM。

**推荐：方案 A 作为默认路径，方案 C 作为高级路径，方案 B 仅在复杂策略场景使用。**

---

### 6.2 决策 2：提案触发时机

#### 方案 A：纯事件驱动

- 秘书订阅事件，事件到达即处理。
- 优点：实时、与事件流天然一致。
- 缺点：事件密集时可能提案过多；需要较强的限流和去重。

#### 方案 B：定时轮询 + 事件唤醒

- 秘书模块每 N 分钟运行一次 `run_check`。
- 关键事件（如 SessionCompleted）可唤醒立即检查。
- 优点：避免事件风暴，批量决策更稳定。
- 缺点：实时性略差。

#### 方案 C：事件驱动 + 批处理窗口

- 事件到达后进入时间窗口（如 30 秒）。
- 窗口内的事件聚合后统一决策。
- 优点：平衡实时性与稳定性。
- 缺点：实现复杂。

**推荐：方案 B 作为默认，关键事件（考试完成、连续错误）使用方案 A 的即时路径。**

---

### 6.3 决策 3：避免打扰与策略学习

#### 6.3.1 打扰预算模型

```python
@dataclass
class InterruptionBudget:
    """用户每日可被打扰的预算。"""
    daily_max: int = 5
    used_today: int = 0
    current_energy: float = 1.0

    def can_interrupt(self, priority: int) -> bool:
        if priority <= 1:            # 紧急提案 always allow
            return True
        if self.used_today >= self.daily_max:
            return False
        if self.current_energy < 0.2:
            return priority <= 2
        return True
```

#### 6.3.2 关系记忆与策略学习

```python
@dataclass
class RelationMemoryEntry:
    action_type: str
    target_id: str
    accept_count: int = 0
    ignore_count: int = 0
    last_interaction_at: datetime | None = None
    effective_priority_bias: int = 0

    def update(self, action: Literal["accept", "dismiss"]):
        if action == "accept":
            self.accept_count += 1
            self.ignore_count = 0
            self.effective_priority_bias = max(0, self.effective_priority_bias - 1)
        else:
            self.ignore_count += 1
            self.last_interaction_at = _now()
            if self.ignore_count >= 3:
                self.effective_priority_bias = min(2, self.effective_priority_bias + 1)
```

**关键规则：**
- 连续 3 次忽略同类提案，自动降级（减少推送频率）。
- 采纳后重置忽略计数，提升优先级。
- 安静时段只推送 priority=1 的紧急提案。

#### 6.3.3 疲劳检测

```
疲劳信号：
- 连续 2 个以上会话正确率 < 40%
- 单次学习时长 > 45 分钟
- 认知负荷 > 0.7
- 答题行为遥测显示犹豫时间长、修改频繁

响应：
- 生成 rest 提案
- 暂停非紧急 proactive 提案
- 降低选题难度（通过事件影响练习壳）
```

---

### 6.4 决策 4：秘书与对话壳的上下文注入

#### 方案 A：被动拉取（推荐）

- 对话壳在每次回复前主动调用秘书 API 获取上下文。
- 优点：对话壳控制注入时机，不污染无关对话。
- 缺点：每次请求多一次调用。

#### 方案 B：主动推送

- 秘书检测到重要状态变化时，主动推送上下文到对话壳。
- 优点：实时。
- 缺点：可能打断用户当前对话流。

#### 方案 C：事件订阅

- 对话壳订阅 `ConversationContextInjected` 事件，按需合并。
- 优点：解耦。
- 缺点：事件顺序需要管理。

**推荐：方案 A 为主，重要事件使用方案 C 触发方案 A 的重新拉取。**

---

## 7. API 契约

### 7.1 秘书编排器对外 API

| 端点 | 方法 | 请求 | 响应 | 说明 |
|------|------|------|------|------|
| `/api/v2/secretary/proposals` | GET | `?limit=&status=` | `Proposal[]` | 获取用户提案 |
| `/api/v2/secretary/proposals/{id}/accept` | POST | `{}` | `ActionResult` | 采纳提案 |
| `/api/v2/secretary/proposals/{id}/dismiss` | POST | `{}` | `ActionResult` | 忽略提案 |
| `/api/v2/secretary/diagnosis` | GET | `?scope=user&node_id=` | `DiagnosisReport` | 获取诊断报告 |
| `/api/v2/secretary/context` | GET | `?conv_id=` | `ConversationContextPayload` | 获取对话上下文 |
| `/api/v2/secretary/preferences` | GET/PUT | `SecretaryPrefs` | `SecretaryPrefs` | 用户偏好 |
| `/api/v2/secretary/silent-tasks` | GET | | `SilentTask[]` | 静默任务列表 |

### 7.2 核心 DTO

```python
class ConversationContextPayload(BaseModel):
    """注入对话壳的上下文包。"""
    user_id: str
    conv_id: str | None

    # 当前学习状态
    active_goals: list[dict]
    due_plan_items: list[dict]
    recent_learning_summary: str

    # 推荐内容
    suggested_topics: list[str]
    pending_proposals: list[ProposalResponse]

    # 可用工具上下文
    available_tools: list[dict]  # [{tool_name, when_to_use, params}]

    # 限制与风格
    response_style_hint: str = ""  # 如「用户今天疲劳，回复简短」
    should_avoid_proactive_suggestions: bool = False


class ProposalResponse(BaseModel):
    id: str
    emoji: str
    title: str
    description: str
    action_type: str
    priority: int
    payload: dict
    insight_evidence: list[str]
    expires_at: datetime | None
    created_at: datetime
```

---

## 8. 与内核/其他壳的集成

### 8.1 与认知 OS 内核

```
认知中心 publish CognitiveStateChanged
  │
  ▼
秘书 Diagnosis Layer 读取 projection
  │
  ▼
生成/更新 DiagnosisReport
  │
  ▼
Strategy Layer 决策
  │
  ▼
生成提案 / 计划请求 / 上下文注入
```

### 8.2 与练习壳

```
练习壳 publish AnswerSubmitted / SessionCompleted
  │
  ▼
秘书 BehaviorTriggerModule
  │
  ▼
生成 practice / review / rest 提案
  │
  ▼
用户采纳 practice 提案 → publish(ProposalAccepted)
  │
  ▼
练习壳创建对应会话
```

### 8.3 与规划壳

```
秘书 Strategy Layer 决定需要创建计划项
  │
  ▼
publish(PlanItemRequested)
  │
  ▼
规划壳创建 PlanItem
  │
  ▼
用户完成 plan item → publish(PlanItemCompleted)
  │
  ▼
秘书订阅 → 评估是否需要后续行动
```

### 8.4 与对话壳

```
秘书 publish ConversationContextInjected
  │
  ▼
对话壳读取后注入 LLM prompt
  │
  ▼
对话壳可展示 pending proposals 或触发工具调用
  │
  ▼
用户在对话中接受提案 → 对话壳调用秘书 accept API → publish(ProposalAccepted)
```

### 8.5 与闪卡壳 / 阅读壳 / 知识树壳

```
闪卡壳 publish FlashCardReviewed
  │
  ▼
秘书评估是否需要练习补充 → 生成 practice 提案

阅读壳 publish ReadingNoteCreated
  │
  ▼
秘书评估是否生成闪卡 / 计划项

知识树壳 publish NodeCreated
  │
  ▼
秘书触发知识扩展静默任务
```

---

## 9. 风险与验收条件

### 9.1 主要风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 提案过多打扰用户 | 用户关闭秘书 | PolicyEngine 限流 + 关系记忆 + 疲劳检测 |
| LLM 生成提案不稳定 | 文案质量差 | 规则骨架 + LLM 文案的混合模型 |
| 事件处理延迟影响实时性 | 用户体验差 | 关键事件即时路径 + 非关键事件批处理 |
| 秘书与对话壳职责模糊 | 架构混乱 | 明确秘书只输出提案/上下文，不直接回复 |
| 策略学习导致推荐窄化 | 用户错过重要提案 | 设置探索比例（如 10% 提案来自新策略） |
| 用户不信任黑盒提案 | 不采纳 | insight_evidence 必须可解释 |

### 9.2 验收条件

- [ ] 秘书编排器订阅所有关键学习事件，不遗漏 `CognitiveStateChanged`。
- [ ] 提案生成必须携带 `insight_evidence`，用户可见。
- [ ] 用户连续忽略同类提案 3 次后，系统主动降低该类提案推送频率。
- [ ] 安静时段（默认 22:00-08:00）只推送 priority=1 的紧急提案。
- [ ] 对话壳每次请求都能获取 `ConversationContextPayload`。
- [ ] 秘书不直接调用任何壳层的写操作，只通过事件和 API 建议。
- [ ] 支持至少 6 种 action_type：review、practice、rest、explore、exam_prep、plan。
- [ ] 诊断报告可从认知投影和事件流重建。
- [ ] 秘书偏好可配置：安静时段、每日提案上限、启用模块。
- [ ] 端到端通过 `rebuild.sh` 验证。
