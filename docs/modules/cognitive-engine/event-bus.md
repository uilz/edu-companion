# 事件总线

## 1. 三层架构

```
┌─────────────────────────────────────────────┐
│              Application Code               │
│  (publish DomainEvent / subscribe handler)  │
└──────────┬──────────────────────┬───────────┘
           │                      │
           ▼                      ▼
┌────────────────────┐  ┌────────────────────┐
│     EventBus       │  │ PersistentEventBus │
│  (内存异步分发)      │  │  (持久化 + dispatch)│
│                    │  │                    │
│ - subscribe()      │  │ - subscribe()      │
│ - publish()        │  │ - publish()        │
│ - unsubscribe()    │  │ - poll_once()      │
└────────────────────┘  └────────┬───────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │   EventStore (统一写入)   │
                    │  append → events 表      │
                    └────────┬─────────────────┘
                             │
                             ▼
                    ┌──────────────────────────┐
                    │     EventMemory          │
                    │  - ShortTerm (deque)     │
                    │  - Working (session)     │
                    │  - LongTerm (pgvector)   │
                    │  - Episodic (importance) │
                    └──────────────────────────┘
```

## 2. EventBus (内存)

`backend/app/infrastructure/event_bus.py`

```python
async def publish(event: DomainEvent) -> None:
    # 1. 递归深度检查 (修复 B4)
    depth = self._depth_var.get()
    if depth >= self._max_recursion_depth:  # 默认 8
        return  # 阻断

    # 2. 并行 dispatch
    handlers = self._handlers.get(event_type, [])
    token = self._depth_var.set(depth + 1)
    try:
        tasks = [asyncio.create_task(safe_invoke(h)) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        self._depth_var.reset(token)
```

**保护机制**：
- handler 超时（5s 默认）— 异常隔离
- 异常隔离 — 单个失败不影响其他
- 递归深度保护 — 防止 handler 嵌套 publish 导致栈溢出 (修复 B4)

## 3. PersistentEventBus (持久化)

`backend/app/infrastructure/persistent_event_bus.py`

```python
async def publish(event: DomainEvent) -> str:
    # 1. 递归深度保护 (修复 B4)
    if self._depth >= self._max_depth:
        return ""

    # 2. 单一写入路径: EventStore.append() (修复 B1)
    event_id = await store.append(event, stream_type=..., stream_id=...)

    # 3. 短期记忆
    memory.remember(user_id, record)

    # 4. 立即 dispatch
    await self._dispatch_to_handlers(event_type, event)

    return event_id
```

**修复 (B1)**：原本 `EventStore.append() + EventsRepository.insert()` 双写会产生重复行，现统一走 `EventStore.append()` 单一路径。

## 4. EventStore (统一存储)

`backend/app/infrastructure/event_store.py`

```python
async def append(
    event: DomainEvent,
    stream_type: str = "",
    stream_id: str = "",
    parent_event_id: str = "",
    correlation_id: str = "",
    summary: str = "",
    importance: float = 0.0,
    compute_embedding: bool = False,
) -> str:
    """写入事件 → 返回 event_id

    单一写入路径: 直接调用 EventsRepository.insert(Event(...))
    """
    repo = self._get_repo()  # EventsRepository
    db_event = Event(
        user_id=...,
        event_type=...,
        stream_type=stream_type or source_type,
        source_type=...,
        payload=asdict(event),
        ...
    )
    repo.insert(db_event)
    return db_event.id
```

## 5. EventMemory (4 级记忆)

`backend/app/infrastructure/event_memory.py`

| 级别 | 存储 | 用途 |
|------|------|------|
| ShortTerm | deque(maxlen=100) per user | 最近事件 → LLM 上下文 |
| Working | list per (user, session) | 当前会话事件 |
| LongTerm | pgvector embedding | 跨会话语义搜索 |
| Episodic | importance ≥ 0.7 | 里程碑 / 突破点 |

## 6. CognitiveEventsAdapter (领域层)

`backend/app/domain/cognitive/events_repository.py`

为 cognitive 子系统提供 `CognitiveEventRecord` ↔ `Event` 适配：

```python
class CognitiveEventsAdapter:
    def insert(self, event: CognitiveEventRecord):
        # 1. 内存索引
        self._by_id[event.id] = event
        # 2. DB 持久化 (单一路径)
        Event(...).insert(...)

    def mark_status(self, event_id, status, msg):
        # 内存 + DB
        ...
```

**修复 (B7/B8)**：原本 `_get_repo()` 回退到 `container.event_bus`，但 EventBus 没有 `insert` 方法导致 `submit_practice` 静默失败。现统一用 adapter 包装 `EventsRepository`。

## 7. 事件清单

10 个领域事件 (Phase 4 引入)，详见 `shared/events.py`：

| 事件 | source_type | 订阅者 |
|------|-------------|--------|
| AnswerSubmitted | practice | analytics, habits, knowledge, secretary |
| ErrorRecorded | practice | errorbook, secretary |
| SessionCompleted | practice | secretary, planning |
| AssistantReplied | conversation | media, cognitive_sync, secretary |
| CognitiveNodeUpdated | cognitive/practice/secretary | adaptive_planner, secretary |
| MessageClassified | conversation | cognitive_sync |
| PracticeSubmitted | practice | cognitive_sync |
| NodeCreated | knowledge | secretary |
| ProposalAccepted | secretary | knowledge |
| PendingCrossTopic | conversation | (rejected candidates → 关联提案) |

## 8. 已知限制

- 无 DLQ（失败事件不重试）— 待办
- 无事件溯源快照（replay 只取时间范围）— 已有 `EventStore.replay()`
- EventMemory 是进程内，重启后丢失（除 LongTerm）— 设计如此

## 9. 测试覆盖

- `tests/test_contract_event_bus.py` — 10 个
- `tests/test_contract_events.py` — 11 个
- `tests/test_phase9_cognitive_sync.py::TestEventBusChain` — 4 个
- `tests/test_cognitive_e2e_full.py::TestEventBusCore` — 6 个
- `tests/test_cognitive_e2e_full.py::TestEventLoopGuard` — 3 个
- `tests/test_cognitive_e2e_full.py::TestCognitiveEventsAdapter` — 5 个
- `tests/test_cognitive_e2e_full.py::TestCrossModuleEventChain` — 2 个
- `tests/test_cognitive_e2e_full.py::TestPerformance` — 2 个

## 10. 修复日志

- **B1 (2026-07-04)**：PersistentEventBus 去双写
- **B4 (2026-07-04)**：EventBus / PersistentEventBus 加递归深度保护
- **B7 (2026-07-04)**：process_event 类型注解修复 (Event → CognitiveEventRecord)
- **B8 (2026-07-04)**：dialogue_context_update 变量名 _repo → _get_repo()
