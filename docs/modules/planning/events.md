# Planning 事件

> Planning 模块产生和消费的事件定义、边界与路由。

**相关 ADR**：
- [`docs/adr/0006-planning-module.md`](../../adr/0006-planning-module.md) — 原始事件设计
- [`docs/adr/0024-planning-shell-migration.md`](../../adr/0024-planning-shell-migration.md) — Phase 5 服务下沉

---

## 1. 事件总览

### 1.1 Planning 发布的事件

| 事件 | 触发时机 | 发布者 |
|------|---------|--------|
| `PlanItemCreated` | 创建计划项 | `services.planning.items.create_plan_item` |
| `PlanItemScheduled` | 更新计划项且设置了 `scheduled_for` | `services.planning.items.update_plan_item` |
| `PlanItemStarted` | 标记计划项开始 | `services.planning.items.start_plan_item` |
| `PlanItemCompleted` | 标记计划项完成 | `services.planning.items.complete_plan_item` |
| `PlanItemSkipped` | 标记计划项跳过 | `services.planning.items.skip_plan_item` |
| `PlanItemExtended` | 延长计划项 | `services.planning.items.extend_plan_item` |
| `PlanGoalCreated` | 创建学习目标 | `services.planning.goals.create_goal` |
| `PlanPeriodicReviewGenerated` | 生成周期回顾 | `services.planning.reviews.generate_review` |
| `PlanItemSuggested` | 基于学习事件主动建议计划项 | `api.planning.proactive_generator` |

### 1.2 Planning 消费的事件

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `PlanItemRequested` | `api.planning.event_handler.PlanningEventHandler` | `requires_user_confirmation=True` 写入 `plan_item_confirmations`；否则直接创建 `plan_item` |
| `CognitiveNodeMetadataChanged` | `api.planning.proactive_generator.PlanningProactiveGenerator` | 掌握度下降时发布 `PlanItemSuggested` |
| `SessionCompleted` | `api.planning.proactive_generator.PlanningProactiveGenerator` | 低正确率建议复习/练习，高正确率建议探索 |
| `MoodStressRuleTriggered` | `services.planning.completion_writer.PlanningCompletionWriter` | 标记受影响计划项 `is_mood_rule_affected=true` |

### 1.3 声明但未启用的事件（保留字段，供后续扩展）

以下事件在 `shared.events` 中已定义，但当前版本**尚未发布**或**仅作为下游订阅契约**：

- `PlanItemUpdated`
- `PlanItemActivated`
- `PlanGoalProgressUpdated`
- `PlanGoalCompleted`
- `PlanDeviationRecorded`
- `PlanGoalRequested`

---

## 2. Schema

### 2.1 计划项生命周期

```python
class PlanItemCreated(DomainEvent):
    user_id: str
    source_module: str      # 固定为 "planning"
    plan_item_id: str
    target_type: str
    target_ref_id: str
    title: str
    description: str
    priority: int
    linked_node_ids: list[str]
    generation_reason: str
    created_at: datetime

class PlanItemScheduled(DomainEvent):
    user_id: str
    plan_item_id: str
    source_module: str      # PlanningSourceModule 字符串值
    scheduled_for: datetime
    plan_date: str          # ISO date
    is_mood_rule_affected: bool
    scheduled_at: datetime

class PlanItemStarted(DomainEvent):
    user_id: str
    plan_item_id: str
    source_module: str      # PlanningSourceModule 字符串值
    started_at: datetime

class PlanItemCompleted(DomainEvent):
    user_id: str
    plan_item_id: str
    source_module: str      # PlanningSourceModule 字符串值
    target_type: str
    target_ref_id: str
    actual_minutes: int
    linked_node_ids: list[str]
    completed_at: datetime

class PlanItemSkipped(DomainEvent):
    user_id: str
    plan_item_id: str
    source_module: str      # PlanningSourceModule 字符串值
    skipped_at: datetime

class PlanItemExtended(DomainEvent):
    user_id: str
    plan_item_id: str
    source_module: str      # PlanningSourceModule 字符串值
    extended_minutes: int
    extended_at: datetime
```

### 2.2 目标

```python
class PlanGoalCreated(DomainEvent):
    user_id: str
    goal_id: str
    title: str
    target_module: str      # CrossModuleTarget 字符串值
    target_metric: str      # node_count / card_count / practice_count / duration_minutes
    target_value: int
    deadline: str           # ISO date
    created_at: datetime
```

### 2.3 周期回顾

```python
class PlanPeriodicReviewGenerated(DomainEvent):
    user_id: str
    review_id: str
    period_type: Literal["weekly", "monthly"]
    period_start: str       # ISO date
    period_end: str         # ISO date
    summary_data: dict
    generated_at: datetime
```

### 2.4 主动建议

```python
class PlanItemSuggested(DomainEvent):
    user_id: str
    source_module: str = "planning"
    suggestion_id: str              # 幂等键
    trigger_event_type: str         # 如 "SessionCompleted"
    trigger_event_id: str
    target_type: str                # flashcard / practice / review / reading / explore
    target_ref_id: str
    title: str
    description: str
    priority: int
    estimated_minutes: int
    linked_node_ids: list[str]
    proposed_scheduled_for: datetime | None
    reason: str                     # 如 "mastery_dropped" / "low_accuracy_session"
    suggested_at: datetime

class PlanItemRequested(DomainEvent):
    user_id: str
    source_module: str = "secretary"
    request_id: str                 # 幂等键
    target_type: str
    target_ref_id: str
    title: str
    description: str
    priority: int
    linked_node_ids: list[str]
    requires_user_confirmation: bool
    estimated_minutes: int
    proposed_scheduled_for: datetime | None
    metadata: dict[str, Any]        # 通常包含 suggestion_id
    requested_at: datetime
```

---

## 3. 完成回写链路

`PlanItemCompleted` 由 `items.complete_plan_item` 发布后，`PlanningCompletionWriter` 按 `source_module` 路由：

| source_module | 回写目标 |
|---------------|---------|
| `project` | `project_nodes.status = 'completed'` |
| `flashcard` | 卡片复习状态 |
| `practice` | 练习完成状态 |
| `reading` | 阅读进度 |
| `language_room` | 语言房间状态 |

**关键约束**：

- 回写 handler **不回发**源模块完成事件（如 `ProjectNodeCompleted`）。
- 源模块如需感知“计划项已完成”，直接订阅 `PlanItemCompleted`。
- 同一 `plan_item_id` 在 `completion_writer` 内部幂等去重。

```
PlanItemCompleted
    │
    ▼
PlanningCompletionWriter._on_completed
    │
    ├─► source_module='project'   → project_nodes
    ├─► source_module='flashcard' → flashcard review
    ├─► source_module='practice'  → practice completion
    ├─► source_module='reading'   → reading progress
    └─► source_module='language_room' → language_room state
```

---

## 4. 主动建议链路

```
CognitiveNodeMetadataChanged / SessionCompleted
    │
    ▼
PlanningProactiveGenerator
    │
    ▼
PlanItemSuggested
    │
    ▼
SecretaryEventHandler
    │
    ▼
PlanItemRequested
    │
    ├─► requires_user_confirmation=True  → plan_item_confirmations（前端确认）
    └─► requires_user_confirmation=False → plan_items（直接创建）
```

**策略约束**：

- 高疲劳时（`fatigue_risk=high`），优先级 ≥3 的建议被秘书过滤，不向用户请求。
- 同一 `suggestion_id` 不会重复生成确认请求（幂等）。

---

## 5. 状态机

```
pending ──► scheduled ──► in_progress ──► completed
   │             │             │
   └─────────► skipped ◄───────┘
   │
   └─────────► extended ──► in_progress
```

状态迁移函数位于 `services.planning.items`：

| 迁移 | 函数 | 发布事件 |
|------|------|---------|
| pending → scheduled | `update_plan_item`（设置 `scheduled_for`） | `PlanItemScheduled` |
| pending → in_progress | `start_plan_item` | `PlanItemStarted` |
| pending/scheduled → skipped | `skip_plan_item` | `PlanItemSkipped` |
| pending → extended | `extend_plan_item` | `PlanItemExtended` |
| scheduled/extended → in_progress | `start_plan_item` | `PlanItemStarted` |
| in_progress → completed | `complete_plan_item` | `PlanItemCompleted` |

---

## 6. 枚举约定

### 6.1 source_module

计划项 `source_module` 必须使用 [`PlanningSourceModule`](../../backend/shared/events.py) 枚举字符串值：

```python
"flashcard"
"practice"
"project"
"reading"
"language_room"
"manual"
"interest"
"interest_explorer"
"mood_stress"
"secretary"
"system"
```

### 6.2 target_module（目标模块）

目标模块 `target_module` 必须使用 [`CrossModuleTarget`](../../backend/shared/events.py) 枚举字符串值：

```python
"flashcard"
"project"
"reading"
"language_room"
"material"
"cognitive_node"
"plan"
"conversation"
"practice"
"interest_explorer"
"mood_stress"
```

---

## 7. 边界原则

- `PlanItem*` 事件**不**直接更新 `CognitiveNode.Belief`；Belief 更新由学习行为本身触发。
- Planning 只发布自身状态变化事件，不回写其他模块的完成事件，防止事件循环。
- 事件发布统一通过 `app.infrastructure.event_bus_utils.publish_event_safe`，服务层负责发布，API 路由层不直接发布。
