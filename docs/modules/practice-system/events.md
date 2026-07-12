# Practice 事件

> Practice 模块产生和消费的事件定义、边界与路由。

**相关 ADR**：
- [`docs/adr/0025-practice-shell-migration.md`](../../adr/0025-practice-shell-migration.md) — Phase 5 服务下沉

---

## 1. 事件总览

### 1.1 Practice 发布的事件

| 事件 | 触发时机 | 发布者 |
|------|---------|--------|
| `AnswerSubmitted` | 用户提交答案（练习、考试、独立答题、内联练习、错题复习） | `engine.publish_practice_events`、`inline.submit_inline_answer`、`standalone.submit_standalone_answer`、`practice_error_book.review_error_question` |
| `ErrorRecorded` | 答错时，伴随 `AnswerSubmitted` 发布 | `engine.publish_practice_events` |
| `SessionCompleted` | 练习会话或考试完成 | `practice_session.complete_session`、`practice_exam` |
| `PracticeAnswerBehaviorRecorded` | 答题行为遥测被记录 | `telemetry_service.record_telemetry` |

### 1.2 Practice 消费的事件

当前 Practice 壳**不直接消费其他模块事件**。跨模块协作通过以下方式实现：

- 认知更新：由 `app.domain.cognitive` 订阅 `AnswerSubmitted` 处理
- 秘书提案：由 `app.domain.secretary` 订阅 `AnswerSubmitted` / `SessionCompleted` 处理
- 学习活动：由 `app.application.handlers.learning_activity_handler` 订阅 Practice 事件处理
- 计划建议：由 `app.api.planning.proactive_generator` 订阅 `SessionCompleted` / `CognitiveNodeMetadataChanged` 处理

> 设计原则：Practice 壳是答题事实的单一发布源，不反向依赖认知/秘书/规划模块的内部状态。

### 1.3 声明但未由 Practice 发布的事件

以下事件在 `shared.events` 中已定义，但当前版本**不由 Practice 壳发布**，仅作为下游订阅契约：

- `ErrorBookEntryReviewed` — 由 FlashCard 复习路径发布
- `ErrorBookEntryResolved` — 由 FlashCard 复习路径发布
- `PracticeSubmitted` — 已弃用，由 `AnswerSubmitted` 统一替代

---

## 2. Schema

### 2.1 AnswerSubmitted

答题提交事件 — 练习模块与认知中心、秘书系统、错题本之间的单一事实源。

```python
@dataclass(frozen=True)
class AnswerSubmitted(DomainEvent):
    user_id: str
    source_module: str       # 固定为 "practice"
    attempt_id: str
    session_id: str
    question_id: str
    skill_id: str
    is_correct: bool
    answer: list[str]
    correct_answer: list[str]
    response_time_seconds: float
    hints_used: int
    confidence_before: int | None
    difficulty: float | None
    cognitive_node_ids: list[str]
    submitted_at: datetime
```

**约束**：
- `source_module` 应设为 `"practice"`
- `source_id` 应设为 `attempt_id`
- `cognitive_node_ids` 必填，用于认知中心定位节点
- `answer` / `correct_answer` 均为 `list[str]`，单选也统一用单元素列表
- `p_known_*` 等派生状态不在本事件中携带，改由 `CognitiveNodeMetadataChanged` / `CognitiveStateChanged` 发布

### 2.2 ErrorRecorded

错题记录事件 — 答错时发布，驱动错题本与多媒体讲解。

```python
@dataclass(frozen=True)
class ErrorRecorded(DomainEvent):
    user_id: str
    source_module: str       # 固定为 "practice"
    question_id: str
    skill_id: str
    error_type: str          # 如 careless / conceptual / procedural / computation
    user_answer: str
    correct_answer: str
```

**约束**：
- `caused_by_event_id` 指向对应的 `AnswerSubmitted.event_id`
- `error_type` 由 `session_engine.classify_error` 根据答案与错因分类

### 2.3 SessionCompleted

练习/考试会话完成事件。

```python
@dataclass(frozen=True)
class SessionCompleted(DomainEvent):
    user_id: str
    session_id: str
    session_type: Literal["practice", "exam", "review"]
    total_questions: int
    correct_count: int
    accuracy: float
    duration_minutes: float
    score: float | None
    passing_score: float | None
```

### 2.4 PracticeAnswerBehaviorRecorded

答题行为遥测记录。

```python
@dataclass(frozen=True)
class PracticeAnswerBehaviorRecorded(DomainEvent):
    user_id: str
    telemetry_id: str
    session_id: str
    question_id: str
    attempt_id: str
    time_on_question_ms: int
    hesitation_ms: int
    answer_change_count: int
    total_hover_ms: int
    avg_text_pause_ms: float
    hint_count: int
    recorded_at: datetime
```

**约束**：
- 遥测详情（悬停、选择、输入停顿等）单独存储，本事件携带 `telemetry_id` 引用，避免事件体积过大。

---

## 3. 事件链路

### 3.1 答题链路

```
POST /api/practice/sessions/{id}/submit
    │
    ▼
session_engine.submit_answer
    │
    ▼
engine.publish_practice_events
    │
    ├─► AnswerSubmitted
    │       ├─► cognitive —— 更新 CognitiveNode belief
    │       ├─► secretary —— 生成复习/练习提案
    │       ├─► learning_activity_handler —— 写入 learning_activities
    │       └─► planning.proactive_generator —— 建议计划项
    │
    └─► ErrorRecorded（答错时）
            └─► error_book / multimedia / secretary
```

### 3.2 会话完成链路

```
POST /api/practice/sessions/{id}/complete
    │
    ▼
practice_session.complete_session
    │
    ▼
SessionCompleted
    │
    ├─► learning_activity_handler
    ├─► secretary
    └─► planning.proactive_generator
```

### 3.3 遥测链路

```
POST /api/practice/telemetry
    │
    ▼
telemetry_service.record_telemetry
    │
    ▼
PracticeAnswerBehaviorRecorded
    │
    └─► analytics / learning_activity_handler
```

---

## 4. 边界原则

1. **单一事实源**：所有答题结果统一通过 `AnswerSubmitted` 发布，不单独发布 `CognitiveNodeUpdated` 或其他掌握度事件。
2. **Practice 不反向依赖**：Practice 服务层不订阅 cognitive / secretary / planning 事件，只通过事件总线发布事实。
3. **事件幂等**：同一 `attempt_id` 的重复 `AnswerSubmitted` 由消费者自行去重。
4. **错误聚合**：`ErrorRecorded` 与 `AnswerSubmitted` 成对出现，错题本可基于两者构建，无需额外事件。
