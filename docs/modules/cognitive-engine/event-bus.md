# 认知引擎 · 事件总线

> 事件总线是模块间异步通信的核心机制，基于内存异步发布-订阅模式。
>
> 源码：[backend/infra/event_bus.py](../../../backend/infra/event_bus.py) + [backend/shared/events.py](../../../backend/shared/events.py)

---

## 设计原则

1. **松耦合**：生产者和消费者不直接依赖
2. **事件驱动**：状态变更通过事件广播
3. **异步处理**：所有 handler 通过 `asyncio.create_task` 并发执行
4. **容错**：`asyncio.gather(*tasks, return_exceptions=True)` 确保单 handler 异常不影响其他

## EventBus 核心 API

```python
class EventBus:
    def __init__(self, handler_timeout: float = 5.0):
        self._handlers: dict[str, list[EventHandler]] = {}
        self._timeout = handler_timeout

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅事件类型"""

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅"""

    async def publish(self, event: DomainEvent) -> None:
        """发布事件，所有 handler 并发执行"""
```

## 领域事件基类

```python
@dataclass(frozen=True)
class DomainEvent:
    event_id: str          # 自动生成 12 位 UUID
    occurred_at: datetime  # UTC 时间戳
```

所有领域事件继承 `DomainEvent`，是不可变数据类（`frozen=True`），只定义数据不包含行为。

## 核心事件列表

### 练习域

| 事件类 | event_type | 关键字段 | 说明 |
|--------|------------|----------|------|
| `AnswerSubmitted` | AnswerSubmitted | user_id, session_id, question_id, skill_id, is_correct, p_known_before/after | 答题提交 |
| `ErrorRecorded` | ErrorRecorded | user_id, question_id, skill_id, error_type | 错题记录 |
| `SessionCompleted` | SessionCompleted | user_id, session_id, total_questions, accuracy | 练习会话完成 |

### 知识域

| 事件类 | event_type | 关键字段 | 说明 |
|--------|------------|----------|------|
| `KnowledgeStateUpdated` | KnowledgeStateUpdated | user_id, skill_id, old_mastery, new_mastery, p_known_before/after | BKT 掌握度变化 |

### 对话域

| 事件类 | event_type | 关键字段 | 说明 |
|--------|------------|----------|------|
| `AssistantReplied` | AssistantReplied | user_id, partition_id, conversation_id, message_id, skill_ids | AI 回复完成 |

### 认知域

| 事件类 | event_type | 关键字段 | 说明 |
|--------|------------|----------|------|
| `CognitiveNodeUpdated` | CognitiveNodeUpdated | user_id, node_id, proficiency_before/after, update_type | CognitiveNode 更新 |

### 业务域 (v6 Phase 4)

| 事件类 | event_type | 关键字段 | 说明 |
|--------|------------|----------|------|
| `MessageClassified` | MessageClassified | user_id, message_id, topic_node_ids, atom_node_ids | 消息分类确认 |
| `PracticeSubmitted` | PracticeSubmitted | user_id, atom_node_ids, correctness, latency_ms | 练习提交 |
| `NodeCreated` | NodeCreated | user_id, node_id, parent_id, level | 知识点创建 |
| `ProposalAccepted` | ProposalAccepted | user_id, proposal_id, action_type, target_node_id | 秘书提案采纳 |

## 事件类型注册表

```python
EVENT_TYPES: dict[str, type[DomainEvent]] = {
    "AnswerSubmitted": AnswerSubmitted,
    "ErrorRecorded": ErrorRecorded,
    "SessionCompleted": SessionCompleted,
    "KnowledgeStateUpdated": KnowledgeStateUpdated,
    "AssistantReplied": AssistantReplied,
    "CognitiveNodeUpdated": CognitiveNodeUpdated,
    "MessageClassified": MessageClassified,
    "PracticeSubmitted": PracticeSubmitted,
    "NodeCreated": NodeCreated,
    "ProposalAccepted": ProposalAccepted,
}
```

## 使用示例

```python
# 练习系统产出事件
await event_bus.publish(AnswerSubmitted(
    user_id="u1",
    session_id="s1",
    question_id="q1",
    skill_id="sk1",
    is_correct=True,
    p_known_before=0.5,
    p_known_after=0.7
))

# 秘书系统消费
event_bus.subscribe("AnswerSubmitted", secretary_handler)
event_bus.subscribe("CognitiveNodeUpdated", secretary_handler)
```
