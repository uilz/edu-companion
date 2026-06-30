# 事件系统 v2 — 实现计划与进度

> 创建: 2026-06-22 | 状态: 已完成

## 开发目标

将事件系统从"消息通知总线"升级为"系统记忆中枢"，实现：
1. 统一事件存储（单一真相源）
2. 四级事件记忆（ShortTerm/Working/LongTerm/Episodic）
3. 多级事件聚合（消息→对话→日→周）
4. pgvector 语义索引
5. 消除双路径，统一入口

## 实现进度

### Phase 1: 数据库迁移
- [x] 迁移 SQL: events 表新增字段 (stream_type, stream_id, parent_event_id, correlation_id, summary, importance, embedding)
- [x] pgvector HNSW 索引
- [x] 更新 events_schema.sql

### Phase 2: 核心组件
- [x] EventStore — 统一 append/query/stream/replay 接口
- [x] EventMemory — 四级记忆系统
- [x] EventAggregator — 事件聚合引擎
- [x] 统一 embedding 模块 (复用现有 granite-embedding-97m)

### Phase 3: 系统整合
- [x] DI 装配 — EventStore/EventMemory/EventAggregator 注入 AppContainer
- [x] PersistentEventBus 集成 — publish 同时写入 EventStore + EventMemory
- [x] 事件聚合触发器 — AssistantReplied→ConversationDigest, SessionCompleted→PracticeSessionSummary
- [x] 工作记忆生命周期 — SessionCompleted 自动结束工作记忆

## 文件清单

### 新建
| 文件 | 说明 | 行数 |
|------|------|------|
| `docs/architecture/event-system-v2.md` | 设计文档 | ~200 |
| `docs/roadmaps/event-system-v2-plan.md` | 本文件 | ~100 |
| `app/infrastructure/event_store.py` | EventStore 核心 (append/query/stream/replay/search) | ~280 |
| `app/infrastructure/event_memory.py` | 四级记忆 (ShortTerm/Working/LongTerm/Episodic) | ~190 |
| `app/infrastructure/event_aggregator.py` | 事件聚合 (ConversationDigest/PracticeSessionSummary/DailyDigest) | ~230 |
| `app/infrastructure/db/event_store_migration.sql` | 迁移 SQL (ALTER TABLE + 新索引) | ~50 |

### 修改
| 文件 | 变更 |
|------|------|
| `app/infrastructure/db/events_schema.sql` | 新增 7 个字段 + 4 个索引 |
| `app/infrastructure/db/events_repository.py` | Event 模型 + insert 支持新字段 |
| `app/infrastructure/persistent_event_bus.py` | publish 集成 EventStore + EventMemory |
| `app/application/di.py` | 装配 EventStore/EventMemory/EventAggregator + 聚合触发器 |
| `app/main.py` | 启动日志 |

## API 设计

### EventStore
```python
store = get_event_store()

# 写入
await store.append(event, stream_type="conversation", stream_id="c1", compute_embedding=True)

# 查询
await store.query(user_id, stream_type="conversation", limit=50)
await store.stream("conversation", "c1", limit=100)
await store.replay(user_id, since_ts, until_ts)

# 因果链
await store.get_parent_chain(event_id)
await store.get_correlated(correlation_id)

# 语义搜索
await store.search_similar("三角函数", user_id="u1", limit=10)
```

### EventMemory
```python
memory = get_event_memory()

# 短期记忆 (自动写入)
recent = memory.short_term(user_id, limit=20)

# 工作记忆
memory.working_start(user_id, session_id)
events = memory.working_events(user_id, session_id)
memory.working_end(user_id, session_id)

# 长期记忆 (语义搜索)
await memory.search(user_id, "三角函数", limit=10)

# 情节记忆 (里程碑)
await memory.episodic(user_id, limit=20)

# AI 上下文
context = memory.build_context(user_id, session_id)
```

### EventAggregator
```python
aggregator = get_event_aggregator()

# 自动触发 (通过 EventBus 订阅)
# 手动触发
await aggregator.aggregate_conversation_digest(user_id, conversation_id)
await aggregator.aggregate_practice_session(user_id, session_id)
await aggregator.aggregate_daily(user_id, "2026-06-22")
```

## 数据流

```
DomainEvent
    │
    ▼
PersistentEventBus.publish()
    ├──▶ EventStore.append()          — 统一存储 (DB)
    ├──▶ EventMemory.remember()       — 短期记忆 (内存)
    ├──▶ EventMemory.working_event()  — 工作记忆 (会话)
    ├──▶ 立即 dispatch 到 handlers   — 实时通知
    └──▶ EventsRepository.mark_done() — 标记完成

EventBus 订阅:
    ├── AssistantReplied → EventAggregator.on_event()
    │   └── 每6条消息 → ConversationDigest → EventStore
    └── SessionCompleted → EventMemory.working_end()
        └── EventAggregator.aggregate_practice_session()
            └── PracticeSessionSummary → EventStore
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 事件存储 | PostgreSQL + JSONB |
| 向量嵌入 | granite-embedding-97m (OpenVINO, 384维) |
| 向量索引 | pgvector HNSW (m=16, ef_construction=200) |
| AI 摘要 | 现有 LLM (gpt-4o-mini) |
| 短期记忆 | 内存 RingBuffer (deque, maxlen=100) |
| 工作记忆 | 内存 dict (session-scoped) |