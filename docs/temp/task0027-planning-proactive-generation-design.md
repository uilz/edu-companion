# Task 0027: Phase 5 — 规划壳主动生成计划项

## 1. 目标

实现规划壳从「被动响应秘书请求」升级为「主动发现学习机会 + 通过秘书中转创建计划项」，并补齐需要用户确认时的 pending confirmation 流程。

## 2. 范围

- 新增 `PlanItemSuggested` 事件：规划壳向秘书编排器建议创建计划项。
- 秘书编排器订阅 `PlanItemSuggested`，决策后发布 `PlanItemRequested`。
- 扩展 `PlanningEventHandler`：
  - `requires_user_confirmation=False` → 直接创建 plan item（已存在）。
  - `requires_user_confirmation=True` → 写入 `plan_item_confirmations` 表，供前端展示。
- 新增 API：列出待确认、接受、忽略 plan item 确认请求。
- 新增 PlanningProactiveGenerator：订阅学习事件，基于规则生成 `PlanItemSuggested`。
- 新增集成测试覆盖上述流程。

## 3. 关键决策

### 3.1 规划壳主动发现机会后如何通知秘书？

**方案 A：规划壳直接发布 PlanItemRequested（source_module=planning）**
- 优点：链路短，实现简单。
- 缺点：违背 `PlanItemRequested` 当前注释中 "source_module 固定为 secretary" 的语义；秘书编排器失去对计划项创建的统一把关能力。

**方案 B：规划壳发布 PlanItemSuggested → 秘书评估后发布 PlanItemRequested**
- 优点：秘书仍是学习编排中枢，可基于用户画像、疲劳度、信任度等统一决策；与现有架构一致。
- 缺点：多一次事件跳转，延迟略高。

**推荐：方案 B**（符合用户「必须经过秘书中转」的决策）。

### 3.2 Pending Confirmation 存储在哪里？

- 新建 `plan_item_confirmations` 表，与 `plan_items` 分离。
- 理由：pending confirmation 不是正式计划项，单独表更灵活，便于过期清理和展示。

### 3.3 主动生成的触发源

- `CognitiveNodeMetadataChanged`：掌握度变化、节点进入复习窗口。
- `SessionCompleted`：会话结束后根据表现生成复习/练习计划。
- `FlashCardReviewed`：闪卡复习后判断是否需要再次复习。
- `PlanGoalCreated` / `PlanGoalUpdated`：目标变化时拆解计划项。
- 定时调度（daily brief 后）：每日生成整体学习计划。

## 4. 事件 Schema

### 4.1 PlanItemSuggested（新增）

```python
@dataclass(frozen=True)
class PlanItemSuggested(DomainEvent):
    """规划壳向秘书建议创建计划项。

    规划壳基于自身算法发现学习机会，但不直接创建计划项，
    而是交由秘书编排器统一决策是否发起 PlanItemRequested。
    """
    user_id: str
    source_module: str = "planning"
    suggestion_id: str = ""           # 幂等键
    trigger_event_type: str = ""      # 触发来源事件类型，如 "SessionCompleted"
    trigger_event_id: str = ""
    target_type: str = ""             # flashcard / practice / review / reading 等
    target_ref_id: str = ""
    title: str = ""
    description: str = ""
    priority: int = 0
    estimated_minutes: int = 10
    linked_node_ids: list[str] = field(default_factory=list)
    proposed_scheduled_for: datetime | None = None
    reason: str = ""                  # 生成原因，如 "mastery_dropped"
    suggested_at: datetime = field(default_factory=_now)
```

### 4.2 PlanItemRequested（已存在，扩展语义）

保持现有字段。source_module 不再强制 "secretary"，也可以是 "secretary_on_behalf_of_planning"。
但为简化，秘书发布时仍写 "secretary"，metadata 中记录原始 suggestion_id。

## 5. 数据表 Schema

### 5.1 plan_item_confirmations

```sql
CREATE TABLE IF NOT EXISTS plan_item_confirmations (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    request_id      TEXT NOT NULL,     -- PlanItemRequested.request_id
    suggestion_id   TEXT,              -- PlanItemSuggested.suggestion_id
    source_module   VARCHAR(30) NOT NULL DEFAULT 'secretary',
    target_type     VARCHAR(30) NOT NULL,
    target_ref_id   TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    priority        SMALLINT DEFAULT 0,
    estimated_minutes INT DEFAULT 10,
    linked_node_ids JSONB DEFAULT '[]'::jsonb,
    proposed_scheduled_for TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'pending',  -- pending / accepted / dismissed / expired
    expires_at      TIMESTAMPTZ,
    accepted_at     TIMESTAMPTZ,
    dismissed_at    TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_item_confirmations_user_status
    ON plan_item_confirmations(user_id, status);
CREATE INDEX IF NOT EXISTS idx_plan_item_confirmations_request_id
    ON plan_item_confirmations(user_id, request_id);
CREATE INDEX IF NOT EXISTS idx_plan_item_confirmations_suggestion_id
    ON plan_item_confirmations(user_id, suggestion_id);
```

## 6. 核心流程

### 6.1 规划壳主动建议 → 秘书中转 → 创建/确认

```
CognitiveNodeMetadataChanged / SessionCompleted / FlashCardReviewed / 定时调度
  │
  ▼
PlanningProactiveGenerator
  │ 评估是否需要建项
  ▼
publish(PlanItemSuggested)
  │
  ▼
SecretaryEventHandler / policy_engine
  │ 基于用户画像、疲劳度、信任度、去重、限流决策
  ▼
publish(PlanItemRequested)
  │ requires_user_confirmation = ?
  ├─ False ──► PlanningEventHandler 直接创建 plan item
  │
  └─ True ───► PlanningEventHandler 写入 plan_item_confirmations
                │
                ▼
            前端展示确认卡片
                │
                ├─ 用户接受 ──► POST /planning/confirmations/{id}/accept
                │                 创建 plan item，更新 status=accepted
                │
                └─ 用户忽略 ──► POST /planning/confirmations/{id}/dismiss
                                  更新 status=dismissed
```

### 6.2 过期清理

- `expires_at` 默认创建后 7 天。
- 定时任务或查询时过滤 `status='pending' AND expires_at < NOW()` 为 expired。

## 7. API 设计

### 7.1 列出待确认计划项

```
GET /planning/confirmations?status=pending
Response: list[PlanItemConfirmationResponse]
```

### 7.2 接受确认

```
POST /planning/confirmations/{confirmation_id}/accept
Response: PlanItemResponse
```

### 7.3 忽略确认

```
POST /planning/confirmations/{confirmation_id}/dismiss
Response: PlanItemConfirmationResponse
```

## 8. 主动生成规则（v1）

### 8.1 基于 CognitiveNodeMetadataChanged

- 当节点掌握度（mastery）下降超过 0.15 时，建议复习。
- 当节点进入复习窗口（next_review_at <= now）时，建议复习。

### 8.2 基于 SessionCompleted

- 正确率 < 0.5 且存在薄弱节点 → 建议针对性练习。
- 会话时长 > 30min 且正确率 > 0.8 → 建议横向拓展。

### 8.3 基于 FlashCardReviewed

- 当闪卡 review 结果为 "hard" 或 "again" 时，建议再次复习。

### 8.4 基于目标拆解

- `PlanGoalCreated` 时，根据 target_metric 拆解为多个 plan item 建议。

## 9. 测试策略

1. `PlanItemSuggested` 事件序列化/反序列化契约测试。
2. PlanningProactiveGenerator 基于 CognitiveNodeMetadataChanged 生成建议。
3. 秘书策略引擎将 `PlanItemSuggested` 转为 `PlanItemRequested`。
4. `PlanItemRequested` requires_user_confirmation=True 时写入 confirmation 表。
5. 接受 confirmation 后创建 plan item 并幂等。
6. 忽略 confirmation 后不再创建。
7. rebuild.sh 端到端验证。

## 10. 风险

- 主动规则可能产生过多建议，需依赖秘书 policy_engine 限流。
- 多一次事件跳转可能引入延迟，handler 超时需合理设置。
- `PlanItemSuggested` 与现有 `PlanItemRequested` 语义需清晰区分，避免循环。

## 11. 验收条件

- [x] `PlanItemSuggested` 事件在 `shared/events.py` 中定义并注册。
- [x] `PlanItemRequested` 扩展 `metadata` 字段用于传递 `suggestion_id`。
- [x] `plan_item_confirmations` 表创建。
- [x] `PlanningEventHandler` 支持确认模式写入 confirmation 表，并保留 `suggestion_id` 到 confirmation metadata。
- [x] 新增 `/planning/confirmations` API（列出/接受/忽略）。
- [x] `PlanningProactiveGenerator` 实现 CognitiveNodeMetadataChanged 和 SessionCompleted 两种触发源。
- [x] 秘书编排器订阅 `PlanItemSuggested` 并发布 `PlanItemRequested`（含疲劳过滤、pending 上限、幂等去重）。
- [x] 新增集成测试 `backend/tests/test_phase5_planning_proactive_generation.py` 覆盖完整链路。
- [x] rebuild.sh 端到端验证通过：Phase 5 测试 15/15 通过，Planning E2E 96/96 通过，Phase 4 回归 6/6 通过。
- [x] 创建 ADR `docs/adr/0020-planning-proactive-generation.md`。
