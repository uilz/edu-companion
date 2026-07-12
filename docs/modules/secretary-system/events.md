# 秘书系统 - 事件矩阵 (Task #83 / Task #168)

> 秘书域与跨模块事件完整定义，含触发位置、消费逻辑、字段、版本兼容性。
> Task #168 更新：路由层业务逻辑下沉后，事件触发位置同步迁移到 `app/services/secretary/`。

---

## 1. 秘书域发布事件

### 1.1 `ProposalAccepted`

- **触发位置**: `POST /api/secretary/proposals/{id}/accept`
- **触发代码**: `backend/app/services/secretary/proposal_actions.py:_publish_accepted_event`
- **字段**:
  - `user_id: str` — 用户 ID
  - `source_module: str` — 固定为 `secretary`
  - `proposal_id: str` — 提案 ID
  - `action_type: str` — review/practice/rest/explore/exam_prep
  - `target_module: str` — 目标模块
  - `target_ref_id: str` — 关联节点/知识点 ID（从 payload 的 `target_ref_id / target_node_id / parent_id / kp_id` 提取）
  - `linked_node_ids: list[str]` — 关联节点列表
  - `accepted_at: datetime` — 采纳时间
- **消费者**:
  - 跨模块监听：Planning / Knowledge 等壳可根据 `target_ref_id` 调整计划或节点状态
  - `secretary_plan_bridge.on_proposal_accepted` 同步调用（失败不影响返回）
- **使用场景**: 用户采纳秘书提案后的跨模块联动

### 1.2 `MoodStressPrefsUpdated`

- **触发位置**: `PUT /api/secretary/mood-stress/prefs`
- **触发代码**: `backend/app/api/secretary/mood_stress.py:317-320`
- **字段**:
  - `user_id: str` — 用户 ID
  - `changed_fields: list[str]` — 变更的字段名列表
- **消费者**:
  - 前端 Zustand store (`notification-preferences`) 同步
  - MoodStress 模块内部一致性
- **使用场景**: 用户心情压力偏好变化时联动 UI 状态

### 1.3 `UserPreferencesUpdated`

- **触发位置**: `POST /api/secretary/agent/preferences`
- **触发代码**: `backend/app/api/system/secretary.py:set_agent_preferences`
- **字段**:
  - `user_id: str`
  - `changed_keys: list[str]` — 变更的 key 路径
  - `source: str` — 触发源（如 `secretary_api`）
- **消费者**:
  - 全局 `user-preferences` 监听器
  - 跨模块用户配置同步
- **使用场景**: Agent 偏好变化时同步 UI 状态

### 1.4 `MoodStressRuleTriggered`

- **触发位置**: MoodStress 模块 `run_check()` 评估到规则命中
- **触发代码**: `backend/app/services/secretary/modules/mood_stress.py:165-171`
- **字段**:
  - `user_id: str`
  - `rule_id: str`
  - `trigger_metric: str` — pressure_score / energy_score / emotion_tag
  - `trigger_value: Any`
  - `action: str`
- **消费者**:
  - Planning 壳（当 `output_to_planning=true` 时可在规划侧标记）
  - 事件流持久化供 Dashboard 时间线展示
- **使用场景**: 心情压力规则命中后提示或联动规划

### 1.5 `ProposalGenerated`

- **触发位置**: `SecretaryEventHandler._save_and_publish_proposal`
- **触发代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py:120-135`
- **字段**:
  - `user_id: str`
  - `source_module: str` — 固定为 `secretary`
  - `proposal_id: str`
  - `action_type: str`
  - `target_module: str`
  - `target_ref_id: str`
  - `title: str`
  - `description: str`
  - `priority: int`
  - `insight_source: str`
  - `linked_node_ids: list[str]`
  - `payload: dict`
  - `caused_by_event_id: str | None`
- **消费者**:
  - 事件流持久化
  - 学习活动流聚合（SOURCE_AUTHORITY=secretary）
- **使用场景**: 秘书生成提案后的审计与联动

### 1.6 `PlanItemRequested`

- **触发位置**: `SecretaryEventHandler._request_plan_item`
- **触发代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py:168-182`
- **字段**:
  - `user_id: str`
  - `source_module: str` — 固定为 `secretary`
  - `request_id: str`
  - `target_type: str`
  - `target_ref_id: str`
  - `title: str`
  - `description: str`
  - `priority: int`
  - `linked_node_ids: list[str]`
  - `requires_user_confirmation: bool`
  - `estimated_minutes: int`
  - `proposed_scheduled_for: Any | None`
  - `metadata: dict` — 包含 `requested_by: secretary`
- **消费者**:
  - Planning 壳（生成 PlanItemSuggestion / Confirmation）
- **使用场景**: 秘书主动向规划壳请求计划项

---

## 2. 秘书订阅事件

### 2.1 `SessionCompleted`

- **订阅位置**: `SecretaryEventHandler._on_session_completed`
- **触发方**: Practice 模块（会话结束时）
- **字段**: `user_id, session_id, total_questions, correct_count, accuracy, duration_minutes`
- **行为**:
  - 低正确率（<0.4）+ 长时间（>30 min）→ 疲劳管理提案
  - 行为触发器生成会话完成反思提案
  - 调度静默任务：生成每日简报、计算诊断
- **代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py:188`

### 2.2 `AnswerSubmitted`

- **订阅位置**: `SecretaryEventHandler._on_answer_submitted`
- **触发方**: Practice 模块（每次答题）
- **字段**: `user_id, question_id, is_correct, session_id, ...`
- **行为**:
  - 更新认知负荷与薄弱点统计
  - 触发复习或强化提案
- **代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py`（`_on_answer_submitted`）

### 2.3 `CognitiveNodeMetadataChanged`

- **订阅位置**: `SecretaryEventHandler._on_cognitive_metadata_changed`
- **触发方**: Cognitive 模块（节点元数据变化）
- **字段**: `user_id, node_id, changes`
- **行为**:
  - 触发学习路径调整（plan_bridge）
  - 生成节点掌握/停滞相关提案
- **代码**: `backend/app/domain/secretary/engines/secretary_event_handler.py`

### 2.4 `ConversationNoteCreatedAsFlashcard`

- **订阅位置**: `SecretaryEventHandler._on_conversation_note_created_as_flashcard`
- **触发方**: Conversation 模块
- **字段**: `user_id, note_id, flashcard_id, ...`
- **行为**:
  - 记录学习活动
  - 可选生成复习提案

### 2.5 `PracticeAnswerBehaviorRecorded`

- **订阅位置**: `SecretaryEventHandler._on_practice_behavior_recorded`
- **触发方**: Practice 模块（答题行为记录）
- **字段**: `user_id, behavior_type, ...`
- **行为**:
  - 行为模式分析
  - 疲劳/专注度信号更新

### 2.6 `PlanItemSuggested`

- **订阅位置**: `SecretaryEventHandler._on_plan_item_suggested`
- **触发方**: Planning 模块
- **字段**: `user_id, suggestion_id, title, ...`
- **行为**:
  - 将规划建议转化为秘书待处理流展示
  - 避免与秘书自身提案重复

---

## 3. 跨模块联动矩阵

| 源模块 | 事件 | 秘书作用 | 代码位置 |
|--------|------|----------|----------|
| Practice | `SessionCompleted` | 疲劳检查 + 行为触发提案 + 静默任务 | `secretary_event_handler.py:_on_session_completed` |
| Practice | `AnswerSubmitted` | 更新认知状态、生成复习提案 | `secretary_event_handler.py:_on_answer_submitted` |
| Cognitive | `CognitiveNodeMetadataChanged` | plan_bridge 路径调整 + 提案 | `secretary_event_handler.py:_on_cognitive_metadata_changed` |
| Conversation | `ConversationNoteCreatedAsFlashcard` | 学习活动记录 + 提案 | `secretary_event_handler.py` |
| Planning | `PlanItemSuggested` | 纳入秘书待处理流 | `secretary_event_handler.py` |
| Secretary | `ProposalAccepted` | plan_bridge 联动 + 跨模块事件 | `proposal_actions.py` |
| Secretary | `MoodStressRuleTriggered` | 供 Planning/Conversation 订阅 | `modules/mood_stress.py` |

---

## 4. 事件流持久化

- 所有事件统一通过 `PersistentEventBus` 持久化到 `events` 表
- 提供 8 个查询端点 (`/api/secretary/events/*`) 用于时间线展示
- 支持父子聚合 (`{event_id}/children` + `{event_id}/ancestors` via CTE)
- 支持维度聚合 (`top-level?dimension=topic|type`)

---

## 5. 事件 Schema 版本控制

- 所有事件定义在 `shared/events.py` (v6)
- Task #168 后，秘书事件触发点分布：
  - `app/services/secretary/proposal_actions.py` — `ProposalAccepted`
  - `app/services/secretary/modules/mood_stress.py` — `MoodStressRuleTriggered`
  - `app/api/secretary/mood_stress.py` — `MoodStressPrefsUpdated`
  - `app/api/system/secretary.py` — `UserPreferencesUpdated`
  - `app/domain/secretary/engines/secretary_event_handler.py` — `ProposalGenerated`, `PlanItemRequested`
- 兼容性：旧客户端可通过 `event.event_type` 字符串判断事件类型
