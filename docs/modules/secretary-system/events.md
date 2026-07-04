# 秘书系统 - 事件矩阵 (Task #83)

> 秘书域与跨模块事件完整定义，含触发位置、消费逻辑、字段、版本兼容性

---

## 1. 秘书域发布事件 (3 个)

### 1.1 `ProposalAccepted`

- **触发位置**: `POST /api/secretary/proposals/{id}/accept`
- **触发代码**: `backend/app/api/system/secretary.py:253`
- **字段**:
  - `user_id: str` — 用户 ID
  - `proposal_id: str` — 提案 ID
  - `action_type: str` — review/practice/rest/explore/exam_prep
  - `target_node_id: str` — 关联节点 ID (从 payload 提取)
- **消费者**:
  - Plan 调整 (secretary_plan_bridge.on_proposal_accepted) — 已废弃, 当前仅记录日志
- **使用场景**: 跨模块联动，触发 Plan 自动调整

### 1.2 `MoodStressPrefsUpdated`

- **触发位置**: `PUT /api/secretary/mood-stress/prefs`
- **触发代码**: `backend/app/api/secretary/mood_stress.py:308`
- **字段**:
  - `user_id: str` — 用户 ID
  - `changed_fields: list[str]` — 变更的字段名列表
- **消费者**:
  - 前端 Zustand store (`notification-preferences`) 同步
  - MoodStress 模块内部一致性
- **使用场景**: 用户偏好变化时联动 UI 状态

### 1.3 `UserPreferencesUpdated`

- **触发位置**: `POST /api/secretary/agent/preferences`
- **触发代码**: `backend/app/api/system/secretary.py:1046-1051` (Task #83 B-6 修复)
- **字段**:
  - `user_id: str`
  - `preferences: dict` — 变更的偏好
- **消费者**:
  - 全局 `user-preferences` 监听器
  - 跨模块用户配置同步
- **使用场景**: Agent 偏好变化时同步 UI 状态

---

## 2. 秘书订阅事件 (3 个)

### 2.1 `SessionCompleted`

- **订阅位置**: `SecretaryEventHandler._on_session_completed`
- **触发方**: Practice 模块 (会话结束时)
- **字段**: `user_id, session_id, total_questions, correct_count, accuracy, duration_minutes`
- **行为**:
  - 低正确率 (<0.5) + 长时间 (>30 min) → 疲劳管理提案
  - 高正确率 (>0.9) → 元认知反思提案
- **代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py:80`

### 2.2 `PracticeSubmitted`

- **订阅位置**: `SecretaryEventHandler._on_practice_submitted`
- **触发方**: Practice 模块 (每次答题)
- **字段**: `user_id, atom_node_ids, correctness, latency_ms`
- **行为**:
  - correctness < 0.5 → 生成复习提案
- **代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py:130`

### 2.3 `CognitiveNodeMetadataChanged`

- **订阅位置**: `SecretaryEventHandler._on_cognitive_metadata_changed`
- **触发方**: Cognitive 模块 (节点元数据变化)
- **字段**: `user_id, node_id, changes`
- **行为**:
  - 触发学习路径调整 (plan_bridge)
- **代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py:180`

---

## 3. 跨模块联动矩阵 (Task #83)

| 源模块 | 事件 | 秘书作用 | 代码位置 |
|--------|------|----------|----------|
| Conversation | `AssistantReplied` | 记录 `policy_engine.record_interaction("conversation_active")` | `di.py:468` |
| Cognitive | `NodeCreated` | 经 `KnowledgeNodeLinked` + 主题相关 → 跨主题候选 → 提案 | `di.py:283` |
| Cognitive | `CognitiveNodeLinked` | 边缘节点 → 跨主题探索提案 | `di.py:386` |
| Cognitive | `PendingCrossTopic` | 跨主题候选 → 提案生成 | `di.py:420` |
| Cognitive | `CognitiveNodeMetadataChanged` | 秘书 → plan_bridge 路径调整 | `secretary_event_handler.py:180` |
| Practice | `PracticeSubmitted` | 秘书 → behavior_trigger.on_practice_submitted | `secretary_event_handler.py:130` |
| Practice | `SessionCompleted` | 秘书 → fatigue_manager + behavior_trigger | `secretary_event_handler.py:80` |
| Secretary | `ProposalAccepted` | Plan (plan_bridge) 路径调整 | `secretary.py:253` |

---

## 4. 事件流持久化 (Task #83)

- 所有事件统一通过 `PersistentEventBus` 持久化到 `events` 表
- 提供 8 个查询端点 (`/api/secretary/events/*`) 用于时间线展示
- 支持父子聚合 (`{event_id}/children` + `{event_id}/ancestors` via CTE)
- 支持维度聚合 (`top-level?dimension=topic|type`)

---

## 5. 事件 Schema 版本控制

- 所有事件定义在 `shared/events.py` (v6)
- Task #83 新增: `UserPreferencesUpdated` 现在在 agent/preferences POST 触发
- 兼容性: 旧客户端可通过 `event.event_type` 字符串判断事件类型
