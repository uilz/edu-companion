# Task 0014 Phase 1: 事件协议与 Schema 设计文档

## 目标

为「全面底层重构」第一个垂直切片定义统一的模块协作事件协议，使练习、认知、秘书、规划四个模块通过事件总线联动，消除双路径更新。

## 关键决策

1. `DomainEvent` 基类统一携带：
   - `event_id`: 事件唯一 ID
   - `occurred_at`: 业务发生时间
   - `source_id`: 业务来源 ID
   - `correlation_id`: 请求/会话追踪 ID
   - `caused_by_event_id`: 因果链上一事件 ID（防循环与审计）

2. `source_module` 不放在基类中，因为不同事件对其语义要求不同（PlanningSourceModule vs CrossModuleTarget vs 模块名）。需要 `source_module` 的事件自行定义。

3. `AnswerSubmitted` 不再携带 `p_known_before` / `p_known_after` 等派生状态，改由 `CognitiveStateChanged` 发布。

## 新增事件

| 事件 | 发布者 | 说明 |
|---|---|---|
| `CognitiveStateChanged` | cognitive | 认知节点状态变化，含掌握度/不确定性/urgency/action |
| `ProposalGenerated` | secretary | 秘书生成跨模块提案 |
| `ProposalDismissed` | secretary/frontend | 用户忽略提案 |
| `PlanItemUpdated` | planning | plan item 合并去重时发布 |

## 改造事件

| 事件 | 变化 |
|---|---|
| `AnswerSubmitted` | 移除 `p_known_before`/`p_known_after`；新增 `source_module`；`cognitive_node_ids` 必填 |
| `ErrorRecorded` | 新增 `source_module`；`caused_by_event_id` 指向对应 `AnswerSubmitted` |
| `PracticeSubmitted` | 标记 DEPRECATED，保留兼容 |
| `ProposalAccepted` | 新增 `source_module`/`target_module`/`target_ref_id`/`linked_node_ids` |
| `PlanItemCreated` | 新增 `source_module`/`description`/`priority`/`linked_node_ids`/`generation_reason`；移除原 `source_module` 的 PlanningSourceModule 语义（改为固定 "planning"） |

## 事件注册

所有新事件已加入 `backend/shared/events.py` 的 `EVENT_TYPES` 注册表，供 `PersistentEventBus._resolve_event_class()` 从 payload 重建事件。

## 文件变更

- `backend/shared/events.py`: 新增/改造事件定义，更新 `EVENT_TYPES`
- `backend/tests/conftest.py`: 更新 `sample_answer_event` / `sample_error_answer_event`
- `backend/tests/factories.py`: 更新 `make_answer_submitted_event`
- `backend/tests/test_contract_events.py`: 更新 `TestAnswerSubmitted`

## 验收

- `python3 -c "from shared.events import *"` 无报错
- 新事件可通过 `asdict()` 序列化并可通过 `EVENT_TYPES[...](**payload)` 重建
- `pytest tests/test_contract_events.py::TestAnswerSubmitted` 通过

## 下一步

Phase 2: 练习模块单事件源改造。
