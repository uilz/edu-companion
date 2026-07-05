# Planning 事件 schema

> Planning 模块产生和消费的事件定义。

**ADR**：[`docs/adr/0006-planning-module.md`](../../adr/0006-planning-module.md)

---

## 1. 事件清单

| 事件 | 触发时机 |
|------|---------|
| `PlanItemCreated` | 创建计划项 |
| `PlanItemScheduled` | 用户安排项 |
| `PlanItemActivated` | 到达安排时间 |
| `PlanItemStarted` | 用户标记开始 |
| `PlanItemCompleted` | 用户标记完成 |
| `PlanItemSkipped` | 用户跳过 |
| `PlanItemExtended` | 用户延长 |
| `PlanGoalCreated` | 创建目标 |
| `PlanGoalProgressUpdated` | 目标进度更新（由其他模块触发）|
| `PlanGoalCompleted` | 目标完成 |
| `PlanPeriodicReviewGenerated` | 周期回顾生成 |
| `PlanDeviationRecorded` | 偏差记录 |

---

## 2. 事件 Schema

### 2.1 计划项生命周期

```python
class PlanItemCreated(DomainEvent):
    user_id: str
    plan_item_id: str
    source_module: str
    target_type: str
    target_ref_id: str
    title: str
    # source_module 的合法值统一为 CrossModuleTarget 枚举字符串：
    #   - "practice"           : 练习来源（聚合 SessionCompleted）
    #   - "flashcard"          : 卡片复习来源（聚合 FlashCardSessionEnded）
    #   - "project"            : 项目节点来源（聚合 ProjectNodeCompleted）
    #   - "reading"            : 阅读来源（聚合 ReadingSessionEnded）
    #   - "language_room"      : 语言房间来源（聚合 LanguageRoomCompleted）
    created_at: datetime

class PlanItemScheduled(DomainEvent):
    user_id: str
    plan_item_id: str
    scheduled_for: datetime
    plan_date: date
    is_mood_rule_affected: bool   # 是否被 MoodStress 规则标记
    scheduled_at: datetime

class PlanItemActivated(DomainEvent):
    user_id: str
    plan_item_id: str
    activated_at: datetime

class PlanItemStarted(DomainEvent):
    user_id: str
    plan_item_id: str
    started_at: datetime

class PlanItemCompleted(DomainEvent):
    """计划项完成 - 触发完成回写"""
    user_id: str
    plan_item_id: str
    source_module: str
    target_type: str
    target_ref_id: str
    actual_minutes: int
    linked_node_ids: list[str]
    completed_at: datetime

class PlanItemSkipped(DomainEvent):
    user_id: str
    plan_item_id: str
    skipped_at: datetime

class PlanItemExtended(DomainEvent):
    user_id: str
    plan_item_id: str
    extended_minutes: int
    extended_at: datetime
```

### 2.2 目标

```python
class PlanGoalCreated(DomainEvent):
    user_id: str
    goal_id: str
    title: str
    target_module: str
    target_metric: str
    target_value: int
    deadline: date
    created_at: datetime

class PlanGoalProgressUpdated(DomainEvent):
    user_id: str
    goal_id: str
    old_value: int
    new_value: int
    target_value: int
    progress_pct: float
    updated_at: datetime

class PlanGoalCompleted(DomainEvent):
    user_id: str
    goal_id: str
    final_value: int
    completed_at: datetime
```

### 2.3 回顾与偏差

```python
class PlanPeriodicReviewGenerated(DomainEvent):
    user_id: str
    review_id: str
    period_type: Literal["weekly", "monthly"]
    period_start: date
    period_end: date
    summary_data: dict
    generated_at: datetime

class PlanDeviationRecorded(DomainEvent):
    user_id: str
    plan_item_id: str
    deviation_type: Literal["timeout", "skip", "early_complete", "extra_insert"]
    planned_minutes: int
    actual_minutes: int
    deviation_minutes: int
    recorded_at: datetime
```

---

## 3. 事件消费者

### 3.1 本模块消费

- `PlanItemCreated` → 写入 `plan_items` 表
- `PlanItemScheduled` → 更新 `plan_items.status='scheduled'` + `scheduled_for`
- `PlanItemCompleted` → 更新 `plan_items.status='completed'` + 写入 `plan_deviations`
- `FlashCardSessionEnded` → 创建 `PlanItemCompleted`（`source_module='flashcard'`）
- `SessionCompleted` → 创建 `PlanItemCompleted`（`source_module='practice'`）
- `ProjectNodeCompleted` → 创建 `PlanItemCompleted`（`source_module='project'`）
- `ReadingSessionEnded` → 创建 `PlanItemCompleted`（`source_module='reading'`）
- `LanguageRoomCompleted` → 创建 `PlanItemCompleted`（`source_module='language_room'`）
- `AnswerSubmitted` → 用于 session 来源的完成触发（配合 `SessionCompleted` 聚合）

### 3.2 完成回写链路

```
PlanItemCompleted
    ├─→ FlashCard 模块：标记对应卡片已复习（如果 source_module='flashcard'）
    ├─→ 练习模块：标记对应练习完成
    ├─→ 项目模块：标记对应节点完成
    ├─→ 阅读模块：标记对应阅读完成
    └─→ 目标进度更新：PlanGoalProgressUpdated
```

**回写不重发源事件**（避免事件循环）：

- Planning 消费 `FlashCardSessionEnded` / `SessionCompleted` / `ProjectNodeCompleted` / `ReadingSessionEnded` / `LanguageRoomCompleted` 后，仅发布 `PlanItemCompleted`，**不**反向重新发布源模块的"完成"事件。
- 源模块如果需要感知"计划项已完成"状态，订阅 `PlanItemCompleted` 即可。
- 同一计划项的多次回写必须通过 `plan_item_id` 做幂等去重。

### 3.3 其他模块消费

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `PlanItemCompleted` | 各源模块 | 标记对应状态 |
| `PlanItemCompleted` | 秘书系统 | 记录"完成计划项"行为 |
| `PlanGoalProgressUpdated` | 全局事件流 | 时间线展示 |
| `PlanGoalCompleted` | 秘书系统 | 记录目标完成 |
| `PlanPeriodicReviewGenerated` | 秘书系统 | 写入 `daily_brief` 周报 |
| `PlanDeviationRecorded` | 秘书系统 | 写入 `habit_formation` 偏差分析 |
| `MoodStressRuleTriggered`（来自 0005）| 规划模块 | 标记 `plan_items.is_mood_rule_affected = true` |
| `PlanItemScheduled`（`source_module='reading'`）| 阅读模块 | 显示"已安排回顾" |

### 3.4 心情压力规则消费

```python
# 0005 MoodStress 规则触发 → 规划模块标记
async def on_mood_stress_rule_triggered(event: MoodStressRuleTriggered):
    """规则触发时标记受影响的计划项 - 不自动修改"""
    if event.action == "postpone_high_intensity":
        # 标记所有"高强度"项目任务
        await update_plan_items(
            user_id=event.user_id,
            source_module="project",
            is_mood_rule_affected=True
        )
        # 不修改 scheduled_for
```

---

## 4. 事件粒度

### 4.1 计划项状态机

```
pending → scheduled → in_progress → completed
        ↓           ↓              ↓
        skipped    skipped        (无后继)
        
scheduled → extended → in_progress
        → in_progress → extended → in_progress
```

### 4.2 完成回写粒度

- `PlanItemCompleted` 每次**单个目标**发一次事件
- 同一计划项可能触发多个模块的状态更新（每个模块各收一次）

### 4.3 偏差记录粒度

- 每次状态变更**自动**记录偏差
- 不单独触发"偏差事件"（由 `PlanItemCompleted` 携带）

---

## 5. 不更新 Belief 的事件

**关键设计原则**：

- 所有 `PlanItem*` 事件**不**直接更新 `CognitiveNode.Belief`
- Belief 的更新由**各源模块**触发（FlashCard 复习、练习答题等）
- 计划项完成**只**标记完成状态，**不**触发 Belief 更新

**理由**：计划项是"用户决定"而非"学习行为"；Belief 的合法来源是用户的实际学习行为。
