# ADR 0020: 规划壳主动生成计划项（Phase 5）

## 状态

已接受 (Accepted)

## 背景

在底层重构中，规划壳最初只被动响应秘书编排器通过 `PlanItemRequested` 事件发起的计划项创建请求。随着学习场景丰富，规划壳需要主动发现学习机会：

1. 认知节点掌握度下降或进入复习窗口时，应建议复习。
2. 练习会话结束后，根据正确率与时长建议针对性练习或横向拓展。
3. 闪卡复习困难、目标创建等场景也应触发计划项建议。

同时，用户要求所有主动生成的计划项必须经过秘书编排器中转，并且默认需要用户确认，以保证秘书对学习的统一编排权。

## 决策

### 1. 规划壳主动建议必须通过秘书中转

- 规划壳不直接创建 plan item，而是发布 `PlanItemSuggested` 事件。
- 秘书编排器订阅 `PlanItemSuggested`，基于疲劳度、pending confirmation 上限、去重等策略决策后，再发布 `PlanItemRequested`。
- `PlanItemRequested` 扩展 `metadata` 字段，用于回传原始 `suggestion_id`，支持端到端追踪。

**理由**：
- 保持秘书作为学习编排中枢的单一责任。
- 避免规划壳直接写入 plan_items 导致策略分散。
- 事件契约清晰区分"建议"（suggestion）与"请求"（request）两个阶段。

### 2. 用户确认使用独立 `plan_item_confirmations` 表

- 新增 `plan_item_confirmations` 表存储 pending/accepted/dismissed/expired 状态的确认请求。
- `PlanningEventHandler` 收到 `requires_user_confirmation=True` 的 `PlanItemRequested` 时，写入 confirmation 表而非直接创建 plan item。
- 提供 `/api/planning/confirmations`（列出）、`/api/planning/confirmations/{id}/accept`（接受并创建 plan item）、`/api/planning/confirmations/{id}/dismiss`（忽略）三个端点。

**理由**：
- pending confirmation 不是正式计划项，与 `plan_items` 分离更灵活。
- 便于前端展示确认卡片、过期清理与用户操作审计。
- 接受时幂等：同一 `request_id` 重复接受只创建一个 plan item。

### 3. 幂等键设计

- `PlanItemSuggested.suggestion_id`：规划壳生成的建议幂等键。
- `PlanItemRequested.request_id`：秘书生成的请求幂等键。中转时固定为 `req_{suggestion_id}`，确保同一建议不会重复产生 confirmation。
- `plan_items.metadata->>'request_id'`：已创建计划项的幂等键。
- `plan_item_confirmations` 上建立 `(user_id, request_id)` 与 `(user_id, suggestion_id)` 索引支持去重。

**理由**：
- 多层幂等防止事件重放、handler 重试、秘书重复中转导致数据重复。
- `request_id` 与 `suggestion_id` 绑定，简化链路追踪。

### 4. 主动生成规则 v1

`PlanningProactiveGenerator` 订阅以下事件：

- `CognitiveNodeMetadataChanged`：当变更字段包含 belief/scheduling 且节点掌握度 < 0.5 或进入复习窗口时，生成 `target_type=review` 建议。
- `SessionCompleted`：
  - 正确率 < 0.5 → 生成针对性练习建议。
  - 正确率 ≥ 0.8 且时长 ≥ 20 分钟 → 生成横向拓展建议。

**理由**：
- 从已有学习事实事件出发，避免额外定时扫描。
- 规则简单可解释，便于后续升级为基于认知画像的策略。

### 5. 秘书策略过滤

秘书在处理 `PlanItemSuggested` 时执行：

- 疲劳过滤：高疲劳时跳过 priority ≥ 3 的非紧急建议。
- pending 上限：pending confirmation 数量 ≥ 20 时暂停新建议。
- suggestion_id 去重：已存在对应 confirmation 时直接跳过。

**理由**：
- 防止主动规则产生过多建议打扰用户。
- 策略集中放在秘书层，规划壳只负责"发现机会"。

## 影响

- **新增模块/文件**：
  - `backend/app/api/planning/proactive_generator.py`
  - `backend/tests/test_phase5_planning_proactive_generation.py`

- **修改模块/文件**：
  - `backend/shared/events.py`：新增 `PlanItemSuggested`，`PlanItemRequested` 扩展 `metadata`。
  - `backend/app/infrastructure/db/planning_schema.sql`：新增 `plan_item_confirmations` 表与索引。
  - `backend/app/api/planning/service.py`：新增 confirmation CRUD、幂等查询与计数。
  - `backend/app/api/planning/routes.py`：新增 confirmation 三个 API 端点。
  - `backend/app/api/planning/schemas.py`：新增 `PlanItemConfirmationResponse`。
  - `backend/app/api/planning/event_handler.py`：支持 confirmation 模式与 `suggestion_id` 透传。
  - `backend/app/domain/secretary/engines/secretary_event_handler.py`：订阅 `PlanItemSuggested` 并中转为 `PlanItemRequested`。
  - `backend/app/main.py`：注册 `PlanningProactiveGenerator`。
  - `backend/tests/test_planning_e2e_full.py`：更新端点数量为 21。

- **事件协议更新**：
  - 新增 `PlanItemSuggested`。
  - `PlanItemRequested` 新增 `metadata` 字段。

## 替代方案

- **方案 A（规划壳直接创建 plan item）**：规划壳感知机会后直接写入 `plan_items`（`source_module=planning`）。rejected，违背秘书统一编排的设计，且无法统一做疲劳/限流策略。
- **方案 B（规划壳直接发布 PlanItemRequested）**：跳过 `PlanItemSuggested` 阶段。rejected，秘书失去对计划项创建的统一把关能力，且 `PlanItemRequested` 语义被稀释。
- **方案 C（将 confirmation 与 plan_items 合并）**：用 `plan_items.status='pending_confirmation'` 表示待确认。rejected，pending confirmation 不是正式计划项，合并后状态机复杂且影响现有视图查询。

## 相关文档

- `docs/temp/task0027-planning-proactive-generation-design.md`
- `docs/adr/0006-planning-module.md`
- `docs/adr/0009-secretary-module.md`
- `docs/adr/0019-secretary-orchestrator-phase4.md`
