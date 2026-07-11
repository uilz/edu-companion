# Task 0020: 规划壳（Planning Shell）深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核深度设计）、Task 0018（练习壳深度设计）、Task 0019（秘书编排器深度设计）

---

## 1. 定位与边界

### 1.1 一句话定位

规划壳是学习时间、目标与行动的「时间容器」：它把来自用户、秘书、考试的目标意图转化为可排程、可执行、可追踪的计划项，并通过事件驱动的方式与其他壳层联动。

### 1.2 规划壳的职责（必须做）

| 职责 | 说明 |
|------|------|
| **计划项管理** | 创建、开始、完成、跳过、延长、删除计划项 |
| **目标管理** | 创建、更新、追踪目标进度 |
| **排程** | 根据时间预算、优先级、认知状态把计划项放到日/周时间轴 |
| **自适应重排** | 根据学习事件自动调整计划 |
| **偏差记录** | 记录计划与实际执行的偏差，用于后续校准 |
| **周期回顾** | 生成日/周/月的学习回顾 |
| **视图聚合** | 提供日视图、周视图、知识视图、目标视图 |

### 1.3 规划壳的禁止（不由它做）

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 决定用户该学什么 | 属于秘书编排器的诊断与策略 | 秘书编排器 |
| 维护掌握度/紧迫度 | 属于认知状态中心 | 认知 OS 内核 |
| 直接生成题目/闪卡 | 属于对应壳层 | 练习壳 / 闪卡壳 |
| 直接修改认知节点 | 属于知识树壳 / 认知中心 | 知识树壳 |
| 替用户直接开始练习 | 属于练习壳 | 练习壳（规划壳只创建 plan item） |

### 1.4 规划壳与秘书的关系

```
秘书编排器（决定做什么）
  │ publish(PlanItemRequested)
  ▼
规划壳（决定什么时候做、怎么做）
  │ publish(PlanItemCreated)
  ▼
用户/系统执行
  │
  ▼
规划壳 publish(PlanItemCompleted)
  │
  ▼
秘书编排器订阅 → 评估后续行动
```

---

## 2. 领域模型

### 2.1 聚合根：Plan

```python
@dataclass
class Plan:
    """用户的学习计划聚合根。"""

    plan_id: str
    user_id: str

    # 时间范围
    plan_date: date | None = None           # 日计划
    week_start: date | None = None          # 周计划

    # 容量约束
    available_minutes: int = 120            # 当日可用学习时长（用户设置或系统估算）
    committed_minutes: int = 0              # 已排程时长
    buffer_minutes: int = 30                # 缓冲时间

    # 组成
    items: list[PlanItem] = field(default_factory=list)
    goals: list[PlanGoal] = field(default_factory=list)

    # 元数据
    source: Literal["manual", "secretary", "adaptive", "imported"] = "manual"
    version: int = 0
```

### 2.2 实体：PlanItem

```python
@dataclass
class PlanItem:
    """计划项 — 一次具体的学习行动。"""

    item_id: str
    user_id: str

    # 内容
    title: str
    description: str = ""

    # 来源与目标
    source_module: str                      # manual / secretary / practice / flashcard / reading
    target_type: Literal[
        "practice_session", "review_node", "read_material",
        "review_flashcards", "conversation", "exam_prep", "custom"
    ]
    target_ref_id: str = ""                 # 关联到具体对象（如 session_id、node_id）
    linked_node_ids: list[str] = field(default_factory=list)

    # 排程
    priority: int = 3                       # 1-5
    estimated_minutes: int = 25
    actual_minutes: int | None = None
    scheduled_for: datetime | None = None
    plan_date: date | None = None

    # 状态
    status: Literal[
        "pending", "scheduled", "in_progress", "completed",
        "skipped", "extended", "overdue", "abandoned"
    ] = "pending"

    # 时间戳
    created_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    skipped_at: datetime | None = None
    extended_at: datetime | None = None

    # 策略标记
    is_mood_rule_affected: bool = False     # 是否因情绪/压力规则调整
    is_auto_generated: bool = False         # 是否由秘书/自适应系统生成

    # 完成来源（谁标记完成）
    completed_by: Literal["user", "system", "linked_event"] = "user"
    linked_event_id: str | None = None      # 若由事件自动完成
```

### 2.3 实体：PlanGoal

```python
@dataclass
class PlanGoal:
    """学习目标。"""

    goal_id: str
    user_id: str
    title: str
    description: str = ""

    # 目标指向
    target_module: Literal["practice", "flashcard", "reading", "conversation", "exam"]
    target_metric: Literal[
        "questions_count", "correct_rate", "nodes_mastered",
        "cards_reviewed", "minutes_studied", "exam_score"
    ]
    target_value: float
    current_value: float = 0.0

    # 时间
    deadline: datetime | None = None

    # 状态
    status: Literal["active", "completed", "paused", "abandoned"] = "active"
    progress_pct: float = 0.0

    # 自动拆解出的子计划项
    derived_item_ids: list[str] = field(default_factory=list)
```

### 2.4 值对象

#### 2.4.1 PlanDeviation（计划偏差）

```python
@dataclass(frozen=True)
class PlanDeviation:
    """计划与实际执行的偏差记录。"""

    deviation_id: str
    plan_item_id: str
    user_id: str

    planned_minutes: int
    actual_minutes: int
    deviation_minutes: int
    deviation_type: Literal["early_complete", "timeout", "skipped", "extended", "no_show"]

    recorded_at: datetime = field(default_factory=_now)
```

#### 2.4.2 PlanSnapshot（计划快照）

```python
@dataclass(frozen=True)
class PlanSnapshot:
    """某一时点的完整计划快照，用于回溯与重放。"""

    snapshot_id: str
    user_id: str
    plan_type: Literal["daily", "weekly", "monthly"]
    period_start: date
    period_end: date
    plan_json: dict
    changes_summary: dict
    created_at: datetime = field(default_factory=_now)
```

#### 2.4.3 TimeSlot（时间槽）

```python
@dataclass(frozen=True)
class TimeSlot:
    """一日内可用于学习的时间段。"""

    start: time
    end: time
    slot_type: Literal["focus", "maintenance", "flexible"]
    available_minutes: int
```

---

## 3. 状态机

### 3.1 计划项状态机

```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │ schedule
                           ▼
                    ┌─────────────┐
                    │  scheduled  │◀─────────────┐
                    └──────┬──────┘              │
                           │ start               │ reschedule
                           ▼                     │
                    ┌─────────────┐              │
                    │ in_progress │──────────────┘
                    └──────┬──────┘
              ┌────────────┼────────────┐
              │            │            │
   complete   ▼   skip     ▼   extend   ▼
        ┌──────────┐  ┌────────┐  ┌──────────┐
        │ completed│  │ skipped│  │ extended │
        └────┬─────┘  └────────┘  └────┬─────┘
             │                         │
             ▼                         ▼
    publish(PlanItemCompleted)  publish(PlanItemExtended)
```

**关键规则：**
1. `pending` → `scheduled`：用户或系统为计划项分配了时间。
2. `scheduled` → `in_progress`：用户开始执行。
3. `in_progress` → `completed`：完成目标行为。
4. `scheduled`/`in_progress` → `overdue`：超过截止时间未处理（由定时任务标记）。
5. 完成后不可再次开始；如需重做，创建新 plan item。

### 3.2 目标状态机

```
┌─────────┐   complete   ┌───────────┐
│ active  │─────────────▶│ completed │
└────┬────┘              └───────────┘
     │ pause
     ▼
┌─────────┐   abandon    ┌───────────┐
│ paused  │─────────────▶│ abandoned │
└─────────┘              └───────────┘
```

---

## 4. 事件协议

### 4.1 规划壳订阅的事件

| 事件 | 来源 | 用途 |
|------|------|------|
| `PlanItemRequested` | 秘书编排器 | 创建计划项 |
| `PlanGoalRequested` | 秘书 / 用户 | 创建目标 |
| `CognitiveStateChanged` | 认知中心 | 调整计划优先级 |
| `SessionCompleted` | 练习壳 | 自动完成关联计划项 |
| `FlashCardReviewed` | 闪卡壳 | 自动完成关联计划项 |
| `ReadingMaterialCompleted` | 阅读壳 | 自动完成关联计划项 |
| `ProposalAccepted` | 前端/系统 | 用户接受提案后创建计划项 |
| `ExamScheduled` | 考试模块 | 创建备考计划 |

### 4.2 规划壳发布的事件

| 事件 | 消费者 | 说明 |
|------|--------|------|
| `PlanItemCreated` | 秘书、分析 | 计划项已创建 |
| `PlanItemScheduled` | 秘书、前端 | 计划项已排程 |
| `PlanItemStarted` | 分析、秘书 | 用户开始执行 |
| `PlanItemCompleted` | 秘书、分析、奖励 | 计划项完成 |
| `PlanItemSkipped` | 秘书、分析 | 计划项跳过 |
| `PlanItemExtended` | 秘书、分析 | 计划项延长 |
| `PlanItemOverdue` | 秘书 | 逾期提醒 |
| `PlanGoalCreated` | 秘书、分析 | 目标创建 |
| `PlanGoalUpdated` | 秘书、分析 | 目标进度更新 |
| `PlanSnapshotCreated` | 分析 | 计划快照 |
| `PlanPeriodicReviewGenerated` | 秘书、前端 | 周期回顾 |

### 4.3 核心事件 Schema

#### 4.3.1 PlanItemRequested

```python
@dataclass(frozen=True)
class PlanItemRequested(DomainEvent):
    """秘书请求创建计划项。"""
    user_id: str
    source_module: str = "secretary"
    request_id: str
    title: str
    description: str
    target_type: str
    target_ref_id: str
    linked_node_ids: list[str]
    estimated_minutes: int
    scheduled_for: datetime | None
    priority: int
    triggered_by_proposal_id: str | None = None
```

#### 4.3.2 PlanItemCreated

```python
@dataclass(frozen=True)
class PlanItemCreated(DomainEvent):
    user_id: str
    source_module: str = "planning"
    plan_item_id: str
    source_module_origin: str         # 原始来源：manual / secretary / practice
    target_type: str
    target_ref_id: str
    title: str
    scheduled_for: datetime | None
    plan_date: date | None
```

#### 4.3.3 PlanItemCompleted

```python
@dataclass(frozen=True)
class PlanItemCompleted(DomainEvent):
    user_id: str
    source_module: str = "planning"
    plan_item_id: str
    source_module_origin: str
    target_type: str
    target_ref_id: str
    actual_minutes: int
    linked_node_ids: list[str]
    completed_at: datetime
    completed_by: str = "user"
    linked_event_id: str | None = None
```

#### 4.3.4 PlanGoalCreated

```python
@dataclass(frozen=True)
class PlanGoalCreated(DomainEvent):
    user_id: str
    source_module: str = "planning"
    goal_id: str
    title: str
    target_module: str
    target_metric: str
    target_value: float
    deadline: str = ""
```

---

## 5. 核心流程

### 5.1 创建计划项流程

```
来源 1：用户手动创建
来源 2：秘书 publish(PlanItemRequested)
来源 3：目标自动拆解
来源 4：考试/事件触发
  │
  ▼
CreatePlanItemCommand
  │
  ▼
规划壳检查时间容量与冲突
  │
  ▼
分配默认时间槽（若无 scheduled_for）
  │
  ▼
写入 plan_items
  │
  ▼
publish(PlanItemCreated)
  │
  ▼
秘书编排器订阅 → 可能生成关联提案
```

### 5.2 完成计划项流程

```
用户点击完成 / 关联事件触发
  │
  ▼
CompletePlanItemCommand
  │
  ▼
更新 plan_items：status=completed, actual_minutes, completed_at
  │
  ▼
写入 plan_deviations（如果实际与计划有偏差）
  │
  ▼
publish(PlanItemCompleted)
  │
  ▼
关联目标更新进度
  │
  ▼
秘书编排器订阅 → 评估是否生成后续提案
```

### 5.3 自适应重排流程

```
触发条件：
  - 用户完成计划项后剩余时间变化
  - CognitiveStateChanged 导致某节点优先级变化
  - 秘书接受新提案
  - 计划项逾期
  │
  ▼
ReplanCommand
  │
  ▼
读取当前所有未完成计划项 + 容量约束
  │
  ▼
SchedulingEngine 重新排程
  │
  ▼
保存 PlanSnapshot
  │
  ▼
publish(PlanSnapshotCreated)
  │
  ▼
前端刷新日/周视图
```

---

## 6. 关键设计决策（多方案对比）

### 6.1 决策 1：排程算法

#### 方案 A：基于优先级 + 时间槽的贪心排程（推荐默认）

```python
def schedule_items(items: list[PlanItem], slots: list[TimeSlot]) -> list[ScheduledItem]:
    """贪心排程：按优先级排序，依次填入可用时间槽。"""
    sorted_items = sorted(items, key=lambda x: (x.priority, -x.estimated_minutes))
    scheduled = []
    for item in sorted_items:
        for slot in slots:
            if slot.available_minutes >= item.estimated_minutes:
                scheduled.append(ScheduledItem(item, slot))
                slot.available_minutes -= item.estimated_minutes
                break
    return scheduled
```

**优点：**
- 简单、可解释、执行快。
- 易于处理硬性约束（如考试倒计时）。

**缺点：**
- 不考虑认知节律、疲劳曲线。
- 长任务可能挤占短任务。

#### 方案 B：整数线性规划（ILP）排程

- 把计划项、时间槽、优先级、认知状态建模为 ILP 问题。
- 求解目标：最大化总体认知收益，同时满足时间约束。

**优点：**
- 理论上最优。
- 可加入复杂约束。

**缺点：**
- 实现复杂、求解耗时。
- 对用户而言不透明。

#### 方案 C：强化学习排程

- 用 RL 学习用户执行计划的模式，预测最佳排程。

**优点：**
- 可个性化。

**缺点：**
- 需要大量数据。
- 难以解释。

**推荐：方案 A 作为默认路径，方案 B 用于考试冲刺等特殊场景，方案 C 作为远期研究。**

---

### 6.2 决策 2：重排触发策略

| 策略 | 触发条件 | 优点 | 缺点 |
|------|---------|------|------|
| **事件触发** | 每次关键事件都重排 | 实时 | 计算频繁、可能抖动 |
| **定时重排** | 每天/每次登录时 | 稳定 | 不够实时 |
| **阈值触发** | 累积变化超过阈值 | 平衡 | 阈值难调 |
| **用户触发** | 用户主动刷新 | 用户可控 | 不够智能 |

**推荐：定时重排 + 事件阈值触发。例如每天 0 点自动重排，同时当秘书生成高优先级提案时立即重排。**

---

### 6.3 决策 3：目标自动拆解

#### 方案 A：秘书主导拆解（推荐）

- 用户创建目标后，秘书编排器根据目标类型和认知状态生成阶段性 plan items。
- 例如目标「掌握线性代数」→ 拆解为「完成矩阵运算练习 5 题」「复习特征值概念」等。

**优点：**
- 秘书拥有全局视角，拆解更合理。
- 可与认知诊断联动。

#### 方案 B：规划壳自拆解

- 规划壳内置目标模板，根据目标 metric 自动拆解。

**优点：**
- 不依赖秘书。

**缺点：**
- 难以利用认知诊断信息。

#### 方案 C：用户手动拆解

- 只提供目标容器，用户自己创建子计划项。

**优点：**
- 完全可控。

**缺点：**
- 智能性不足。

**推荐：方案 A。秘书生成拆解请求，规划壳执行创建。**

---

### 6.4 决策 4：计划项与事件的自动关联

#### 方案 A：显式关联（推荐）

- PlanItem 创建时指定 `target_type` 和 `target_ref_id`。
- 当对应事件发生时，规划壳自动完成该 plan item。
- 例如 `target_type="practice_session", target_ref_id="ses_xxx"`，当 `SessionCompleted` 事件到达时自动完成。

**优点：**
- 精确、可追溯。
- 不依赖模糊匹配。

#### 方案 B：隐式关联

- 规划壳监听事件，根据节点 ID、时间窗口等模糊匹配完成 plan item。

**优点：**
- 用户无需显式创建关联。

**缺点：**
- 容易误匹配。

**推荐：方案 A 为主，方案 B 作为 fallback（如用户从对话中直接开始练习，没有显式 plan item）。**

---

## 7. API 契约

### 7.1 写命令端点

| 端点 | 方法 | 请求 | 响应 |
|------|------|------|------|
| `/api/v2/planning/items` | POST | `PlanItemCreate` | `PlanItemResponse` |
| `/api/v2/planning/items/{id}` | PATCH | `PlanItemUpdate` | `PlanItemResponse` |
| `/api/v2/planning/items/{id}/start` | POST | `{}` | `PlanItemResponse` |
| `/api/v2/planning/items/{id}/complete` | POST | `{actual_minutes}` | `PlanItemResponse` |
| `/api/v2/planning/items/{id}/skip` | POST | `{}` | `PlanItemResponse` |
| `/api/v2/planning/items/{id}/extend` | POST | `{minutes}` | `PlanItemResponse` |
| `/api/v2/planning/items/{id}` | DELETE | `{}` | `{status, id}` |
| `/api/v2/planning/goals` | POST | `PlanGoalCreate` | `PlanGoalResponse` |
| `/api/v2/planning/goals/{id}` | PATCH | `PlanGoalUpdate` | `PlanGoalResponse` |
| `/api/v2/planning/replan` | POST | `{scope: "daily"|"weekly"}` | `PlanSnapshotResponse` |

### 7.2 查询端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/planning/daily` | GET | 日视图 |
| `/api/v2/planning/weekly` | GET | 周视图 |
| `/api/v2/planning/knowledge` | GET | 知识视图（按节点聚合计划项） |
| `/api/v2/planning/items` | GET | 计划项列表 |
| `/api/v2/planning/goals` | GET | 目标列表 |
| `/api/v2/planning/reviews` | GET | 周期回顾列表 |
| `/api/v2/planning/reviews/generate` | POST | 生成周期回顾 |

### 7.3 核心 DTO

```python
class PlanItemResponse(BaseModel):
    id: str
    user_id: str
    source_module: str
    target_type: str
    target_ref_id: str
    title: str
    description: str
    estimated_minutes: int
    actual_minutes: int | None
    linked_node_ids: list[str]
    priority: int
    status: str
    scheduled_for: datetime | None
    plan_date: date | None
    created_at: datetime


class DailyViewResponse(BaseModel):
    date: date
    status_bar: dict
    timeline_items: list[PlanItemResponse]
    pending_pool: list[PlanItemResponse]
    adaptive_recommendations: list[dict]
    brief_summary: dict


class PlanGoalResponse(BaseModel):
    id: str
    title: str
    description: str
    target_module: str
    target_metric: str
    target_value: float
    current_value: float
    progress_pct: float
    deadline: datetime | None
    status: str
```

---

## 8. 与内核/其他壳的集成

### 8.1 与秘书编排器

```
秘书 publish(PlanItemRequested)
  │
  ▼
规划壳创建 PlanItem
  │
  ▼
规划壳 publish(PlanItemCreated)
  │
  ▼
秘书订阅 → 可能生成「计划已创建」确认或后续提案

用户完成 PlanItem
  │
  ▼
规划壳 publish(PlanItemCompleted)
  │
  ▼
秘书订阅 → 生成鼓励/下一步提案
```

### 8.2 与练习壳

```
规划壳创建练习类 PlanItem
  │
  ▼
用户点击开始 → 跳转练习壳创建会话
  │
  ▼
练习壳 publish(SessionCompleted)
  │
  ▼
规划壳订阅 → 自动完成对应 PlanItem
```

### 8.3 与闪卡壳 / 阅读壳

```
规划壳创建复习/阅读类 PlanItem
  │
  ▼
用户执行后
  │
  ▼
闪卡壳 publish(FlashCardReviewed) / 阅读壳 publish(ReadingMaterialCompleted)
  │
  ▼
规划壳订阅 → 自动完成对应 PlanItem
```

### 8.4 与对话壳

```
用户在对话中说「帮我规划一下这周」
  │
  ▼
对话壳理解意图 → 调用秘书/规划 API
  │
  ▼
规划壳生成周计划
  │
  ▼
对话壳展示计划摘要，用户可确认/修改
```

---

## 9. 风险与验收条件

### 9.1 主要风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 自动重排频繁导致用户困惑 | 体验差 | 默认定时重排 + 阈值触发，避免每次事件都重排 |
| 计划项过多造成压力 | 用户放弃 | 容量约束 + 秘书打扰预算共享 |
| 目标拆解不合理 | 用户不信任 | 秘书主导拆解 + 用户可编辑 |
| 自动完成误判 | 计划数据失真 | 显式关联为主，模糊匹配为辅 |
| 计划与实际偏差大 | 后续排程不准 | 记录偏差并用于校准 estimated_minutes |

### 9.2 验收条件

- [ ] 规划壳支持计划项的完整生命周期：pending → scheduled → in_progress → completed/skipped/extended。
- [ ] 秘书可通过 `PlanItemRequested` 事件请求创建计划项。
- [ ] 练习/闪卡/阅读事件可自动完成显式关联的计划项。
- [ ] 支持日视图、周视图、知识视图三种视图聚合。
- [ ] 支持目标创建与自动进度追踪。
- [ ] 支持计划快照与偏差记录。
- [ ] 支持自适应重排，默认每天 0 点自动执行。
- [ ] 周期回顾可汇总计划完成情况、目标进度、模块分布。
- [ ] 规划壳不直接维护掌握度/紧迫度，只读取认知投影。
- [ ] 端到端通过 `rebuild.sh` 验证。
