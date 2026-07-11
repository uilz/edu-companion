# Task 0018: 练习壳（Practice Shell）深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核深度设计）、Task 0014（事件协议设计）

---

## 1. 定位与边界

### 1.1 一句话定位

练习壳是用户与认知节点之间最明确的「探测交互」：它负责把用户的答题行为转化为可量化的学习事实，并通过事件驱动的方式把这些事实交给认知 OS 内核，同时从内核读取认知投影来指导选题、反馈与推荐。

### 1.2 练习壳的职责（必须做）

| 职责 | 说明 |
|------|------|
| **会话生命周期管理** | 创建、开始、暂停、恢复、完成、放弃练习/考试/复习会话 |
| **题目组织与呈现** | 维护会话内的题目顺序、当前题号、已答/未答/跳过状态 |
| **答题判定** | 根据题目类型（单选/多选/判断/填空/自由作答）判定对错 |
| **学习事实发布** | 每次答题、跳过、完成只产生不可变领域事件 |
| **基础反馈返回** | 同步返回是否正确、正确答案、简要解析 |
| **完整反馈拉取** | 通过投影接口异步拉取信息增益、元认知建议、复习推荐 |
| **多源组卷** | 从题库、错题本、变式生成、AI 新题等来源混合出题 |
| **考试模式支持** | 限时、乱序、不允许中途查看解析、最终评分报告 |

### 1.3 练习壳的禁止（不由它做）

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 直接更新认知投影 | 破坏 SSOT | 认知状态中心订阅 `AnswerSubmitted` 后更新 |
| 维护掌握度/紧迫度 | 这是认知投影 | 认知 OS 内核 |
| 生成跨模块计划 | 属于秘书/规划 | 秘书编排器生成提案，规划壳生成计划项 |
| 生成用户级学习策略文案 | 属于秘书 | 秘书编排器读取 `CognitiveStateChanged` 后生成 |
| 直接读写闪卡/错题本表 | 属于其他壳 | 通过事件让对应壳消费 |
| 解释事件语义做跨模块编排 | 属于秘书 | 秘书编排器 |

### 1.4 练习壳与内核的读写边界

```
┌─────────────────────────────────────────┐
│           练习壳（Practice Shell）         │
│  ┌─────────────┐  ┌───────────────────┐ │
│  │ Command API │  │ Query API         │ │
│  │ 写：产生事件 │  │ 读：投影视图       │ │
│  └──────┬──────┘  └─────────┬─────────┘ │
└─────────┼───────────────────┼───────────┘
          │                   │
          ▼                   ▼
┌─────────────────────────────────────────┐
│         认知 OS 内核                      │
│  事件总线 ←─── 发布/订阅                  │
│  认知状态中心 ←── 更新 projection         │
│  秘书编排器 ←── 生成提案                  │
└─────────────────────────────────────────┘
```

---

## 2. 领域模型

### 2.1 聚合根：PracticeSession

```python
@dataclass
class PracticeSession:
    """练习会话聚合根 — 唯一可变状态入口。"""

    session_id: str
    user_id: str
    bank_id: str
    session_type: Literal["practice", "exam", "review"] = "practice"
    mode: Literal["adaptive", "sequential", "random", "mastery"] = "adaptive"
    status: Literal["created", "started", "paused", "completed", "abandoned"] = "created"

    question_ids: list[str] = field(default_factory=list)
    answered_question_ids: list[str] = field(default_factory=list)
    skipped_question_ids: list[str] = field(default_factory=list)
    flagged_question_ids: list[str] = field(default_factory=list)

    correct_count: int = 0
    wrong_count: int = 0
    score: float | None = None
    duration_seconds: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    version: int = 0

    # 考试模式专用
    exam_config: ExamConfig | None = None
    time_remaining_seconds: int | None = None

    # 来源追踪（用于分析组卷效果）
    source_mix: SourceMix | None = None
```

**设计要点：**
- 聚合根内只保存**题目 ID 列表**和**答题状态**，不保存题目内容（题目内容属于题库壳/阅读壳）。
- `score` 在考试完成前为 `None`，防止前端展示半成品分数。
- `version` 用于乐观并发控制，防止重复提交。

### 2.2 值对象

#### 2.2.1 ExamConfig（考试配置）

```python
@dataclass(frozen=True)
class ExamConfig:
    duration_minutes: int
    allow_pause: bool = False
    show_answer_after_each: bool = False
    shuffle_questions: bool = False
    passing_score: float = 0.6
    max_attempts: int = 1
```

#### 2.2.2 SourceMix（组卷来源配比）

```python
@dataclass(frozen=True)
class SourceMix:
    """一次会话的题目来源配比。"""
    bank: int = 0          # 题库自适应选题
    errors: int = 0        # 错题本
    variants: int = 0      # 已有题目变式
    new: int = 0           # AI 新题
    due_review: int = 0    # 到期复习题
```

#### 2.2.3 AttemptRecord（答题记录值对象）

```python
@dataclass(frozen=True)
class AttemptRecord:
    attempt_id: str
    session_id: str
    question_id: str
    user_id: str
    user_answer: list[str]
    is_correct: bool
    response_time_ms: int
    hints_used: int
    confidence_before: int | None
    error_pattern: str = ""
    error_detail: dict = field(default_factory=dict)
    submitted_at: datetime = field(default_factory=_now)
```

**设计要点：**
- `AttemptRecord` 是**事实记录**，与聚合根分开存储。
- 一次 `AnswerSubmitted` 事件对应一条 `AttemptRecord`。
- `error_pattern` 来自规则分类（如 careless / misconception / procedure_error），`error_detail` 可包含 LLM 详细分析。

### 2.3 题目实体（只读引用）

练习壳不拥有题目，只从题库读取题目视图：

```python
@dataclass(frozen=True)
class QuestionView:
    question_id: str
    bank_id: str
    question_type: Literal["single", "multiple", "judge", "fill", "free_form"]
    stem: str
    options: list[OptionView]
    correct_answer: list[str]
    explanation: str
    difficulty: float | None
    cognitive_node_ids: list[str]
    skill_id: str = ""
    source: Literal["bank", "errors", "variants", "new", "due_review"] = "bank"
```

### 2.4 答题行为遥测（Answer Behavior Telemetry）

练习壳不只是记录「最终答案」，还要记录用户在答题过程中的微观行为。这些行为是认知诊断的重要信号。

#### 2.4.1 遥测值对象

```python
@dataclass(frozen=True)
class OptionHoverEvent:
    """选项悬停事件。"""
    option_letter: str
    start_at_ms: int          # 相对题目呈现时刻的毫秒偏移
    duration_ms: int          # 悬停时长


@dataclass(frozen=True)
class OptionSelectionEvent:
    """选项选中/取消事件。"""
    option_letter: str
    action: Literal["select", "deselect"]
    at_ms: int


@dataclass(frozen=True)
class AnswerChangeEvent:
    """答案变更事件（用于单选/多选/填空）。"""
    from_answer: list[str]
    to_answer: list[str]
    at_ms: int
    reason: Literal["click", "keyboard", "auto_clear"] = "click"


@dataclass(frozen=True)
class TextInputEvent:
    """文本输入事件（用于填空/自由作答）。"""
    inserted_text: str        # 本次输入的字符/字符串
    cursor_position: int
    at_ms: int
    pause_before_ms: int      # 距上一次输入的间隔（思考停顿）


@dataclass(frozen=True)
class HintEvent:
    """提示使用事件。"""
    hint_level: int
    at_ms: int
    duration_ms: int          # 用户看了多久提示


@dataclass(frozen=True)
class AnswerBehaviorTelemetry:
    """一次答题的完整行为遥测。"""
    telemetry_id: str
    session_id: str
    question_id: str
    user_id: str

    time_on_question_ms: int                # 题目呈现到提交的总时长
    first_interaction_ms: int | None        # 首次交互（悬停/点击/输入）时间

    option_hover_events: list[OptionHoverEvent] = field(default_factory=list)
    option_selection_events: list[OptionSelectionEvent] = field(default_factory=list)
    answer_change_events: list[AnswerChangeEvent] = field(default_factory=list)
    text_input_events: list[TextInputEvent] = field(default_factory=list)
    hint_events: list[HintEvent] = field(default_factory=list)

    # 派生指标（可由 builder 计算）
    hesitation_ms: int = 0                  # 首次交互前空白时长
    answer_change_count: int = 0
    total_hover_ms: int = 0
    avg_text_pause_ms: float = 0.0
```

**设计要点：**
- 遥测数据**只追加、不修改**，作为 `AnswerBehaviorRecorded` 事件的 payload。
- 遥测可以异步批量发送，不阻塞答题提交。
- 认知中心可以结合遥测中的 `hesitation_ms`、`answer_change_count`、`hint_events` 等特征，修正对「猜测」「粗心」「真正不会」的判断。

---

## 3. 状态机

### 3.1 练习会话状态机

```
                    ┌─────────────┐
         create     │             │
        ───────────▶│   created   │
                    │             │
                    └──────┬──────┘
                           │ start
                           ▼
                    ┌─────────────┐     pause      ┌─────────┐
                    │             │◀──────────────▶│  paused │
                    │   started   │                │         │
                    │             │───────────────▶│         │
                    └──────┬──────┘   resume       └─────────┘
                           │
              submit / skip│
                           │（每题推进，不切换状态）
                           │
                           │ complete / abandon
                           ▼
              ┌────────────────────────┐
              │     completed /        │
              │     abandoned          │
              └────────────────────────┘
```

### 3.2 考试模式专用状态机

```
                    ┌─────────────┐
                    │   created   │
                    └──────┬──────┘
                           │ start
                           ▼
                    ┌─────────────┐
                    │   started   │◀────── timeout ─────┐
                    └──────┬──────┘                      │
                           │ submit_all / auto_submit    │
                           ▼                             │
                    ┌─────────────┐                      │
                    │   grading   │──────────────────────┘
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   graded    │
                    └─────────────┘
```

**关键规则：**
1. `created` → `started` 只能由 `StartSessionCommand` 触发。
2. `started` 状态下允许 `submit_answer` 和 `skip_question`。
3. `completed` 状态下不允许再次提交。
4. `abandoned` 状态下可重放事件，但不计入学习统计。
5. 考试模式下，倒计时到 0 自动触发 `auto_submit`，状态变为 `grading`。

---

## 4. 事件协议

### 4.1 练习壳发布的事件

| 事件 | 触发条件 | 消费者 | 说明 |
|------|---------|--------|------|
| `SessionCreated` | 创建会话 | 秘书、规划、分析 | 会话元数据 |
| `SessionStarted` | 开始会话 | 分析、秘书 | 用户开始学习 |
| `AnswerSubmitted` | 提交答案 | 认知中心、秘书、错题本、反馈构建器 | **核心事实事件** |
| `QuestionSkipped` | 跳过题目 | 认知中心（低权重）、分析 | 用户放弃该题 |
| `SessionPaused` | 暂停会话 | 分析 | 记录中断 |
| `SessionResumed` | 恢复会话 | 分析 | 记录恢复 |
| `SessionCompleted` | 完成会话 | 秘书、规划、分析 | 生成报告/提案 |
| `SessionAbandoned` | 放弃会话 | 分析 | 不计入有效学习 |
| `AnswerBehaviorRecorded` | 答题行为批量上报 | 认知中心、分析 | 微观行为用于认知诊断 |
| `QuestionPresented` | 题目呈现给用户 | 分析 | 记录用户何时看到某题 |
| `HintRequested` | 用户请求提示 | 认知中心、分析 | 降低该题的认知权重 |

### 4.2 练习壳订阅的事件

| 事件 | 用途 | 处理方式 |
|------|------|---------|
| `CognitiveStateChanged` | 自适应选题 | 读取节点掌握度/紧迫度，选择下一题 |
| `PlanItemCompleted` | 计划驱动练习 | 当用户完成「练习某节点」计划项时，可触发复习会话 |
| `ProposalAccepted` | 接受秘书提案 | 用户接受「来场 5 题快练」提案，创建会话 |
| `FlashCardReviewed` | 复习后联动 | 闪卡复习结果可影响练习选题优先级 |

### 4.3 事件 Schema（核心）

#### 4.3.1 SessionCreated

```python
@dataclass(frozen=True)
class SessionCreated(DomainEvent):
    user_id: str
    source_module: str = "practice"
    session_id: str
    bank_id: str
    session_type: str
    mode: str
    question_ids: list[str]
    source_mix: dict
    exam_config: dict | None = None
```

#### 4.3.2 AnswerSubmitted（已存在，强化版）

```python
@dataclass(frozen=True)
class AnswerSubmitted(DomainEvent):
    user_id: str
    source_module: str = "practice"
    source_id: str  # session_id
    correlation_id: str
    session_id: str
    question_id: str
    skill_id: str
    is_correct: bool
    answer: str
    correct_answer: str
    time_spent: float
    response_time_ms: int
    hints_used: int
    confidence_before: int | None
    difficulty: float | None
    cognitive_node_ids: list[str]
    attempt_id: str
    submitted_at: datetime
```

**关键变化：**
- 新增 `attempt_id`，与 `practice_attempts` 表主键一致，便于反馈拉取。
- `cognitive_node_ids` 必填，为空时由认知中心按 `skill_id` 兜底映射。

#### 4.3.3 SessionCompleted

```python
@dataclass(frozen=True)
class SessionCompleted(DomainEvent):
    user_id: str
    source_module: str = "practice"
    session_id: str
    session_type: str
    total_questions: int
    answered_count: int
    skipped_count: int
    correct_count: int
    wrong_count: int
    accuracy: float
    duration_minutes: float
    source_mix_result: dict
```

#### 4.3.4 AnswerBehaviorRecorded

```python
@dataclass(frozen=True)
class AnswerBehaviorRecorded(DomainEvent):
    """答题行为遥测事件 — 前端批量上报。"""
    user_id: str
    source_module: str = "practice"
    source_id: str  # session_id
    correlation_id: str
    session_id: str
    question_id: str
    attempt_id: str | None = None   # 若提交时尚未生成 attempt，可为空
    telemetry: AnswerBehaviorTelemetry
```

#### 4.3.5 QuestionPresented

```python
@dataclass(frozen=True)
class QuestionPresented(DomainEvent):
    """题目呈现事件 — 前端在题目渲染时触发。"""
    user_id: str
    source_module: str = "practice"
    session_id: str
    question_id: str
    question_index: int
    presented_at: datetime
```

#### 4.3.6 HintRequested

```python
@dataclass(frozen=True)
class HintRequested(DomainEvent):
    """用户请求提示事件。"""
    user_id: str
    source_module: str = "practice"
    session_id: str
    question_id: str
    hint_level: int
    requested_at: datetime
```

---

## 5. 核心流程

### 5.1 创建会话流程

```
用户/秘书发起创建
  │
  ▼
CreateSessionCommand
  │
  ▼
QuestionSelectionService 根据 source_mix 和认知投影组卷
  │
  ├── 从 bank 自适应选题
  ├── 从 errors 选错题
  ├── 从 due_review 选到期复习题
  ├── 调用变式服务生成 variants
  └── 调用 AI 生成 new 题
  │
  ▼
PracticeSessionAggregate 初始化（created 状态）
  │
  ▼
持久化：聚合根快照 + 命令记录 + practice_sessions 行
  │
  ▼
publish(SessionCreated)
  │
  ▼
返回 {session_id, questions（脱敏，无答案/解析）, config}
```

### 5.2 提交答案流程

```
用户提交答案
  │
  ▼
SubmitAnswerCommand（携带 attempt_id 与可选的 behavior_telemetry_id）
  │
  ▼
加载 PracticeSessionAggregate
  │
  ▼
验证：状态=started、题目属于会话、未答过
  │
  ▼
判题：check_answer(user_answer, correct_answer, question_type)
  │
  ▼
错因分析：classify_error + classify_llm（异步/可降级）
  │
  ▼
写入 AttemptRecord
  │
  ▼
聚合根 submit_answer() → 更新 answered/correct/wrong/score/version
  │
  ▼
保存聚合根快照 + 命令记录
  │
  ▼
publish(AnswerSubmitted)
  ├── 认知中心 → 更新 cognitive_node_projections
  ├── 秘书编排器 → 评估是否生成提案
  ├── 错题本 handler → 更新错误记录
  └── 反馈构建器 → 生成/更新 FeedbackProjection
  │
  ▼
若前端已上报 AnswerBehaviorRecorded：
  认知中心订阅该事件，结合 behavior 特征修正信念更新权重
  │
  ▼
同步返回基础反馈
  {
    attempt_id,
    is_correct,
    correct_answer,
    explanation,
    error_type,
    metacognition_feedback,
    session_status,
    next_question_id  # 可选，用于顺序模式
  }
```

### 5.3 完成会话流程

```
用户点击完成 / 自动提交
  │
  ▼
CompleteSessionCommand
  │
  ▼
聚合根 complete() → status=completed
  │
  ▼
更新会话统计
  │
  ▼
保存聚合根快照 + 命令记录
  │
  ▼
publish(SessionCompleted)
  ├── 秘书 → 生成「是否需要复习/休息/继续」提案
  ├── 规划 → 更新相关 plan item 状态
  └── 分析 → 记录学习会话
  │
  ▼
返回会话结果摘要
```

---

## 6. 关键设计决策（多方案对比）

### 6.1 决策 1：选题/组卷策略

#### 方案 A：Projection-Driven Adaptive Selection（推荐）

**核心思想：**
- 选题服务读取 `cognitive_node_projections` 中的 `proficiency`、`urgency`、`next_action_type`。
- 使用多臂老虎机（Thompson Sampling）或基于信息增益的贪心策略选择下一题。
- 每道题的难度与目标节点的 `proficiency` 匹配：选择 `difficulty ≈ proficiency ± 0.15` 的题目。

**公式：**
```
score(q) = w1 * information_gain_potential(q)
         + w2 * urgency(node(q))
         + w3 * (1 - |difficulty(q) - proficiency(node(q))|)
         - w4 * recent_exposure(q)
```

**优点：**
- 最大化每次练习的认知收益。
- 与认知投影天然联动。

**缺点：**
- 冷启动时数据不足，需要探索策略。
- 计算量比简单随机大。

#### 方案 B：Rule-Based Selection

**核心思想：**
- 固定规则：优先错题 → 到期复习题 → 薄弱节点题 → 新节点题。
- 每条规则有硬编码权重。

**优点：**
- 简单可解释，易于调试。
- 冷启动友好。

**缺点：**
- 难以随用户数据演进。
- 容易陷入局部最优（反复做同一批错题）。

#### 方案 C：LLM-Based Selection

**核心思想：**
- 把用户认知状态、历史记录、目标节点交给 LLM，让 LLM 决定下一题。
- 主要用于生成变式题和新题。

**优点：**
- 灵活，可理解复杂语义。

**缺点：**
- 成本高、延迟大、不可解释。
- 不应作为实时选题主路径，只用于生成环节。

**推荐：方案 A 为主，方案 B 作为冷启动兜底，方案 C 仅用于生成新题/变式。**

---

### 6.2 决策 2：反馈模型

#### 方案 A：FeedbackProjection + 拉取模式（推荐）

**核心思想：**
- `submit_answer` 同步返回基础反馈。
- 后台 `FeedbackBuilder` 消费 `AnswerSubmitted` 和 `CognitiveStateChanged`，生成 `FeedbackProjection`。
- 前端通过 `GET /practice/feedback/{attempt_id}` 拉取完整反馈。

**FeedbackProjection 字段：**
```python
@dataclass
class FeedbackProjection:
    attempt_id: str
    session_id: str
    question_id: str
    user_id: str
    is_correct: bool
    
    # 信息增益
    information_gain: float
    uncertainty_reduction_percent: float
    p_known_before: float
    p_known_after: float
    
    # 元认知
    confidence_before: int | None
    metacognition_feedback: str
    calibration_status: Literal["overconfident", "underconfident", "well_calibrated"]
    
    # 学习建议
    analysis: str
    learning_tips: list[str]
    next_action_type: Literal["review", "practice_similar", "deep_process", "rest"]
    next_action_text: str
    
    # 关联资源
    related_node_ids: list[str]
    reference_materials: list[dict]
    
    created_at: datetime
    updated_at: datetime
```

**优点：**
- 反馈可审计、可回放。
- 可异步加入 LLM 深度解析，不阻塞主路径。
- 秘书系统可基于 FeedbackProjection 调整策略。

**缺点：**
- 前端需要轮询或 SSE。
- 增加一个投影表和 builder。

#### 方案 B：同步完整反馈

**核心思想：**
- `submit_answer` 同步计算并返回完整反馈。
- 认知更新也在同步路径完成。

**优点：**
- 前端交互简单，一次请求拿到所有内容。

**缺点：**
- 阻塞主路径，LLM 分析无法加入。
- 与认知中心耦合，违背 SSOT。

#### 方案 C：SSE 推送

**核心思想：**
- 基础反馈同步返回。
- 完整反馈通过 SSE/WebSocket 推送。

**优点：**
- 实时性好。

**缺点：**
- 连接管理复杂。
- 对移动端/弱网不友好。

**推荐：方案 A（FeedbackProjection + 拉取），未来可在拉取基础上叠加 SSE 作为体验增强。**

---

### 6.3 决策 3：考试模式与练习模式的差异

| 维度 | 练习模式 | 考试模式 |
|------|---------|---------|
| 目标 | 学习、探测、巩固 | 评估、认证 |
| 反馈时机 | 每题即时反馈 | 交卷后统一反馈 |
| 答案/解析 | 提交后立即显示 | 交卷前不显示 |
| 选题 | 自适应，可重复探测 | 固定卷面，可乱序 |
| 时间 | 不限或软限制 | 硬限制，超时自动交卷 |
| 对认知投影的影响 | 正常更新 | 可配置为「诊断性」低权重更新 |
| 完成事件 | `SessionCompleted` | `SessionCompleted{session_type="exam"}` |
| 秘书联动 | 生成复习提案 | 生成薄弱点分析/学习计划 |

**考试模式事件增强：**
```python
@dataclass(frozen=True)
class ExamSubmitted(DomainEvent):
    """考试提交事件，继承 SessionCompleted 的核心字段。"""
    user_id: str
    session_id: str
    total_questions: int
    correct_count: int
    accuracy: float
    duration_minutes: float
    passing_score: float
    is_passed: bool
    weak_node_ids: list[str]
```

**设计要点：**
- 考试模式使用与练习模式相同的聚合根，但 `exam_config` 字段控制行为。
- 考试答题期间仍发布 `AnswerSubmitted`，但前端不展示反馈。
- 考试结束后，秘书基于 `ExamSubmitted` 生成诊断报告和学习计划。

---

### 6.4 决策 4：错题本集成

#### 方案 A：错题本作为独立壳层（推荐）

- 练习壳答错时只发布 `ErrorRecorded`。
- 错题本壳（ErrorBook Shell）订阅 `ErrorRecorded`，维护错题记录。
- 练习壳从错题本壳的投影读取「待复习错题」用于组卷。

**优点：**
- 职责清晰，错题本可独立演进。
- 支持跨模块来源（练习、考试、闪卡自评）汇聚错题。

#### 方案 B：错题本作为练习壳子模块

- 练习壳直接维护 `practice_attempts` 中的 `is_wrong` 字段。
- 错题查询直接读 `practice_attempts`。

**优点：**
- 实现简单。

**缺点：**
- 错题来源单一，无法整合闪卡、对话等来源。
- 与练习壳职责混杂。

**推荐：方案 A。错题本独立成壳，练习壳通过事件和投影与之交互。**

---

### 6.5 决策 5：出题自定义能力

你提到「出题能不能自定义」，这一点非常关键。练习壳不能只让用户被动接受 AI 出题，必须支持从自然语言意图到精确参数的自定义。

#### 6.5.1 自定义维度

```python
@dataclass(frozen=True)
class QuestionGenerationSpec:
    """用户自定义出题规格。"""
    target_node_ids: list[str]              # 目标认知节点
    excluded_question_ids: list[str] = field(default_factory=list)

    # 难度控制
    difficulty_mode: Literal["auto", "fixed", "range"] = "auto"
    difficulty_fixed: float | None = None
    difficulty_min: float | None = None
    difficulty_max: float | None = None

    # 题型与认知层次
    question_types: list[Literal["single", "multiple", "judge", "fill", "free_form"]] = field(
        default_factory=lambda: ["single", "multiple"]
    )
    bloom_levels: list[Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]] = field(
        default_factory=list
    )

    # 内容与风格
    source_material_ids: list[str] = field(default_factory=list)  # 基于指定资料出题
    style_prompt: str = ""                    # 自然语言风格描述，如「出得像考研真题」
    constraints: list[str] = field(default_factory=list)          # 硬性约束，如「必须包含计算步骤」

    # 数量与来源配比
    count: int = 5
    source_mix: SourceMix = field(default_factory=lambda: SourceMix(new=5))

    # 元数据
    generated_for: Literal["practice", "conversation", "exam", "review"] = "practice"
    conv_context: str = ""                    # 对话上下文（对话壳出题时携带）
```

#### 6.5.2 自定义层级

| 层级 | 用户输入 | 系统处理 |
|------|---------|---------|
| **L1 自然语言** | 「给我出 5 道像考研真题的概率题」 | LLM 解析为 `QuestionGenerationSpec`，用户可二次确认 |
| **L2 参数面板** | 勾选题型、难度、节点、资料 | 直接构造 `QuestionGenerationSpec` |
| **L3 模板/示例** | 上传一道例题，要求生成变式 | 提取例题特征，按相同风格生成 |
| **L4 程序化** | 其他壳通过事件携带 spec | 直接执行生成 |

#### 6.5.3 事件协议

```python
@dataclass(frozen=True)
class PracticeGenerationRequested(DomainEvent):
    """其他壳请求练习壳出题。"""
    user_id: str
    source_module: str              # 发起方：conversation / planning / user
    request_id: str
    spec: QuestionGenerationSpec


@dataclass(frozen=True)
class QuestionsGenerated(DomainEvent):
    """练习壳完成出题后发布。"""
    user_id: str
    source_module: str = "practice"
    request_id: str
    bank_id: str
    question_ids: list[str]
    generated_count: int
    spec_snapshot: dict
```

**关键规则：**
- 对话壳发起出题时必须携带 `conv_context`，避免「丢失信息、出的不是用户想要的题」。
- 生成结果不直接注入对话，而是通过 `QuestionsGenerated` 事件返回，由对话壳决定展示方式。
- 用户可对生成结果进行「 thumbs up / thumbs down / edit 」，系统记录反馈用于改进生成模型。

---

### 6.6 决策 6：练习壳的「智能性」分层

「够不够智能」需要分层定义，否则容易做成黑盒。

#### 6.6.1 智能性三层模型

```
┌─────────────────────────────────────────┐
│  L3 策略智能 Strategy Intelligence      │
│  · 基于周目标/考试倒计时制定练习计划      │
│  · 疲劳管理、学习节奏调控                │
│  · 由秘书编排器主导，练习壳执行          │
├─────────────────────────────────────────┤
│  L2 诊断智能 Diagnostic Intelligence    │
│  · 基于答题结果 + 行为遥测判断「真会/猜对/粗心/不会」│
│  · 识别知识漏洞、先决条件缺失、概念混淆   │
│  · 由认知状态中心 + 错因分析服务完成      │
├─────────────────────────────────────────┤
│  L1 适配智能 Adaptive Intelligence      │
│  · 选题难度匹配掌握度                    │
│  · 反馈时机与内容个性化                  │
│  · 由练习壳的 QuestionSelectionService  │
│    和 FeedbackBuilder 完成               │
└─────────────────────────────────────────┘
```

#### 6.6.2 当前设计覆盖

| 层级 | 是否覆盖 | 说明 |
|------|---------|------|
| L1 适配智能 | ✅ | Projection-Driven Adaptive Selection、FeedbackProjection |
| L2 诊断智能 | ⚠️ 部分 | 有 `classify_error` 和 `ErrorRecorded`，但还没整合行为遥测做联合诊断 |
| L3 策略智能 | ⚠️ 由秘书主导 | 练习壳发布事件，秘书生成提案 |

#### 6.6.3 增强 L2 诊断智能的设计

引入 `DiagnosticSignal` 概念，把答题结果与行为遥测合并为一个诊断信号：

```python
@dataclass(frozen=True)
class DiagnosticSignal:
    """一次答题的联合诊断信号。"""
    attempt_id: str
    is_correct: bool
    correctness_confidence: float   # 结合行为遥测后对「是否真会」的置信度
    primary_diagnosis: Literal[
        "mastered",
        "lucky_guess",
        "careless_error",
        "procedural_error",
        "conceptual_gap",
        "prerequisite_missing",
        "insufficient_evidence",
    ]
    contributing_behaviors: list[str]  # 如 ["long_hesitation", "multiple_answer_changes", "hint_used_before_correct"]
    suggested_action: Literal["increase_difficulty", "review_concept", "practice_similar", "revisit_prerequisite"]
```

**生成逻辑：**
1. 规则引擎先做初筛：
   - 答对 + `hesitation_ms < 2s` + 无修改 → `mastered`
   - 答对 + `hint_used` + 长停顿 → `lucky_guess` 或 `insufficient_evidence`
   - 答错 + 选错选项被长悬停 → `careless_error`
   - 答错 + 多次修改后仍错 → `conceptual_gap`
2. LLM 对复杂情况做二次诊断（可异步、可降级）。
3. 认知中心在更新 belief 时使用 `correctness_confidence` 作为权重，避免「猜对」被当作「掌握」。

#### 6.6.4 多方案：诊断模型选择

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|---------|
| **规则 + 行为阈值** | 可解释、低延迟、无 LLM 成本 | 复杂模式难覆盖 | 实时反馈、冷启动 |
| **贝叶斯诊断模型** | 概率化、可量化不确定性 | 需要大量标注数据 | 中期，数据积累后 |
| **LLM 诊断** | 灵活、可处理复杂语义 | 成本高、有幻觉 | 异步深度报告 |

**推荐：规则 + 行为阈值作为默认路径，LLM 诊断作为增强，贝叶斯模型作为后续迭代。**

---

## 7. API 契约

### 7.1 写命令端点

| 端点 | 方法 | 请求体 | 响应 |
|------|------|--------|------|
| `/api/v2/practice/sessions` | POST | `{bank_id, session_type, mode, count, source_mix, cognitive_node_ids, exam_config?}` | `SessionView` |
| `/api/v2/practice/sessions/{id}/start` | POST | `{}` | `SessionView` |
| `/api/v2/practice/sessions/{id}/submit` | POST | `{question_id, answer, time_spent, hints_used, confidence_before}` | `BasicFeedback` |
| `/api/v2/practice/sessions/{id}/skip` | POST | `{question_id}` | `SessionView` |
| `/api/v2/practice/sessions/{id}/pause` | POST | `{}` | `SessionView` |
| `/api/v2/practice/sessions/{id}/resume` | POST | `{}` | `SessionView` |
| `/api/v2/practice/sessions/{id}/complete` | POST | `{}` | `SessionResultView` |
| `/api/v2/practice/sessions/{id}/abandon` | POST | `{}` | `SessionView` |
| `/api/v2/practice/generate` | POST | `QuestionGenerationSpec` | `{request_id, bank_id, questions[]}` |
| `/api/v2/practice/telemetry` | POST | `AnswerBehaviorTelemetry` | `{telemetry_id}` |
| `/api/v2/practice/questions/{id}/hint` | POST | `{current_level}` | `{hint_level, text}` |

### 7.2 查询端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/practice/sessions/{id}` | GET | 会话状态（含题目列表，脱敏） |
| `/api/v2/practice/feedback/{attempt_id}` | GET | 完整反馈投影 |
| `/api/v2/practice/sessions/{id}/result` | GET | 会话完成后的结果报告 |
| `/api/v2/practice/recommendations` | GET | 基于认知投影的推荐 |

### 7.3 核心 DTO

```python
class BasicFeedback(BaseModel):
    attempt_id: str
    is_correct: bool
    correct_answer: list[str]
    explanation: str
    error_type: str = ""
    metacognition_feedback: str = ""
    session_status: str
    next_question_id: str | None = None

class SessionResultView(BaseModel):
    session_id: str
    session_type: str
    total_questions: int
    correct_count: int
    wrong_count: int
    skipped_count: int
    accuracy: float
    duration_minutes: float
    weak_node_ids: list[str]
    mastered_node_ids: list[str]
    next_recommended_action: dict | None = None
```

---

## 8. 与内核/其他壳的集成

### 8.1 与认知 OS 内核

```
练习壳 ──publish──▶ AnswerSubmitted
                      │
                      ▼
            认知状态中心 CognitiveEventHandler
                      │
                      ▼
            更新 cognitive_node_projections
                      │
                      ▼
            publish CognitiveStateChanged
                      │
                      ▼
            练习壳订阅 ──▶ 用于自适应选题、反馈拉取
```

### 8.2 与秘书编排器

```
练习壳 ──publish──▶ SessionCompleted / AnswerSubmitted
                      │
                      ▼
            秘书编排器 Secretary Orchestrator
                      │
                      ▼
            生成 ProposalGenerated
                      │
                      ▼
            用户接受 ──publish──▶ ProposalAccepted
                      │
                      ▼
            练习壳订阅 ──▶ 创建新会话（如「再练 5 题」）
```

### 8.3 与规划壳

```
规划壳创建「练习某节点」计划项
  │
  ▼
用户完成 plan item ──publish──▶ PlanItemCompleted
  │
  ▼
练习壳订阅（可选）──▶ 记录「由计划驱动的练习」

练习壳完成会话 ──publish──▶ SessionCompleted
  │
  ▼
规划壳订阅 ──▶ 更新相关 plan item 进度/状态
```

### 8.4 与对话壳

```
对话壳需要出题 ──publish──▶ PracticeGenerationRequested
  │
  ▼
练习壳的 QuestionGenerationService 生成题目
  │
  ▼
练习壳 publish QuestionsGenerated
  │
  ▼
对话壳订阅 ──▶ 在对话中嵌入题目卡片

用户在对话中提交答案 ──▶ 对话壳调用练习壳 API 或 publish AnswerSubmitted
```

**关键要求：** 对话壳不能把「想出的题」直接交给练习壳出题，导致信息丢失。正确方式是：对话壳携带上下文（节点 ID、参考资料、用户原话）请求练习壳生成，练习壳生成后通过事件返回，对话壳展示。

---

## 9. 风险与验收条件

### 9.1 主要风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 事件订阅者失败导致认知投影未更新 | 数据不一致 | PersistentEventBus 持久化 + 幂等重试 + 死信队列 |
| 反馈拉取延迟高 | 用户体验差 | 基础反馈同步返回；完整反馈可降级为预计算模板 |
| 考试模式与练习模式代码分支过多 | 维护困难 | 用 `exam_config` 驱动行为差异，避免复制逻辑 |
| 自适应选题探索不足导致冷启动差 | 用户流失 | 冷启动用 rule-based 兜底，积累数据后切换 Thompson Sampling |
| 聚合根快照与命令记录不一致 | 状态机错误 | 快照版本与命令记录版本单调递增，重建时校验 |

### 9.2 验收条件

- [ ] `submit_answer` 不再直接调用认知仓库更新。
- [ ] 一次答题只发布一个 `AnswerSubmitted` 核心事件（`PracticeSubmitted` 彻底移除）。
- [ ] 基础反馈同步返回，完整反馈可通过 `GET /practice/feedback/{attempt_id}` 拉取。
- [ ] 练习会话状态机可通过事件回放完整重建。
- [ ] 考试模式下，交卷前不泄露答案与解析。
- [ ] 错题本作为独立壳层，练习壳通过 `ErrorRecorded` 事件与之交互。
- [ ] 自适应选题至少支持：题库、错题、到期复习、变式、AI 新题五种来源。
- [ ] 出题接口支持 `QuestionGenerationSpec` 全维度自定义，对话壳出题必须携带 `conv_context`。
- [ ] 答题行为遥测至少采集：选项悬停、选项选中/取消、答案变更、文本输入停顿、提示使用。
- [ ] 认知中心结合行为遥测生成 `DiagnosticSignal`，能区分「掌握/猜对/粗心/概念漏洞」。
- [ ] 所有事件携带 `correlation_id` 和 `caused_by_event_id`，支持因果追踪。
- [ ] 端到端通过 `rebuild.sh` 验证。
