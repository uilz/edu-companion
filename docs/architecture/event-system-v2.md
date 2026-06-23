# 事件系统 v2 — 架构设计文档

> 版本: 2.0 | 日期: 2026-06-22 | 状态: 实现中

## 一、设计目标

将事件系统从"消息通知总线"升级为"系统记忆中枢"。

**核心理念**: 所有用户能感知到的系统操作，都作为不可变事件写入 EventStore，形成用户学习旅程的完整时间线。AI 通过查询这段记忆来理解上下文、做出决策。

## 二、当前问题诊断

| 问题 | 现状 | 影响 |
|------|------|------|
| 双路径并存 | `event_bus.publish()` + `EventService.emit()` 两条路径 | 无单一真相源，事件分散 |
| 事件无归属 | events 表有 `source_type`/`source_id` 但无流式查询 | 无法回答"这个对话里发生过什么" |
| 无记忆层级 | LLM 上下文只注入当前认知快照 | AI 是"瞎子"，不知道刚才发生了什么 |
| 无聚合能力 | SessionCompleted 存在但无聚合机制 | 无法生成"本周学习报告" |
| 认知域孤岛 | `cognitive/events.py` 独立于主事件系统 | 认知事件不进入事件总线 |
| 三份 embedding 代码 | `files/embedding.py`, `llm/embedding_engine.py`, `embedding_utils.py` | 代码重复，pooling 策略不一致 |

## 三、架构设计

### 3.1 从 EventBus 到 EventStore 的思维升级

| 维度 | EventBus (old) | EventStore (new) |
|------|---------------|-----------------|
| 定位 | 消息通知 | 系统记忆 |
| 数据流 | 发布→订阅→丢弃 | 发布→存储→索引→查询→聚合 |
| 查询 | 不支持 | 按时间/实体/类型/语义多维查询 |
| 聚合 | 不支持 | 消息→对话→日→周自动聚合 |
| 记忆 | 不支持 | 短期/工作/长期/情节四级记忆 |
| AI 上下文 | 无事件注入 | 注入事件时间线 + 语义搜索 |

### 3.2 组件架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Unified Event Store                           │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐  │
│  │  EventWriter    │  │  EventReader   │  │   EventAggregator      │  │
│  │  append(event)  │  │  query(filters)│  │   消息→对话→日→周聚合    │  │
│  │  publish(event) │  │  stream(ent)   │  │   AI摘要自动生成         │  │
│  └───────┬────────┘  └───────┬────────┘  └──────────┬─────────────┘  │
│          │                   │                       │                │
│          ▼                   ▼                       ▼                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │               events 表 (PostgreSQL)                            │  │
│  │  + JSONB payload  + pgvector embedding(384)  + 多维索引          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    EventMemory (四级记忆)                        │  │
│  │  ShortTerm  │  Working  │  LongTerm   │  Episodic               │  │
│  │  最近N条事件 │  当前会话  │  pgvector   │  里程碑事件              │  │
│  │  RingBuffer │  Session  │  语义搜索   │  "第一次掌握"等           │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 数据模型

```python
EventRecord:
  event_id: str          # 唯一标识 (12位)
  user_id: str           # 所属用户
  stream_type: str       # conversation | practice | knowledge | secretary | system
  stream_id: str         # 流内实体ID
  event_type: str        # 事件类型名
  parent_event_id: str   # 因果链 (哪个事件触发了这个)
  correlation_id: str    # 跨域关联 (同一用户操作链)
  source_type: str       # 来源系统 (保留兼容)
  source_id: str         # 来源实体ID (保留兼容)
  payload: dict          # 完整事件数据
  summary: str           # AI生成摘要 (用于长期记忆检索)
  importance: float      # 0~1 重要性评分 (用于记忆淘汰)
  embedding: list[float] # 384维向量 (语义搜索)
  created_at: datetime   # 发生时间
  status: str            # pending | done | failed
```

### 3.4 事件流 (Stream) 概念

| Stream | 包含的事件 | 查询场景 |
|--------|----------|---------|
| `conversation:{cid}` | 消息、分类、情绪、工具调用 | "这个对话里发生了什么" |
| `practice:{sid}` | 开始、答题、纠错、完成 | "这次练习的完整轨迹" |
| `knowledge:{nid}` | 创建、更新、掌握、遗忘 | "这个知识点的演变历史" |
| `user:{uid}` | 所有事件 | "用户今天做了什么" |

### 3.5 事件聚合链

```
MessageSent × N  →  ConversationDigest  (每N条消息自动聚合)
                  →  ConversationSummary (对话结束时)

AnswerSubmitted × N  →  PracticeSessionSummary  (会话结束时)
                      →  DailyPracticeDigest    (每日)

DailyDigest × 7  →  WeeklyLearningReport  (每周)
```

### 3.6 四级记忆系统

| 层级 | 存储 | 容量 | 查询方式 | 用途 |
|------|------|------|---------|------|
| ShortTerm | 内存 RingBuffer | 100条/用户 | 时间顺序 | 当前对话上下文 |
| Working | 内存 Session 列表 | 当前会话 | 属性过滤 | 当前会话内事件 |
| LongTerm | DB + pgvector | 全量 | 语义搜索 | 跨会话回忆 |
| Episodic | DB (importance>0.7) | 精选 | 重要性排序 | 里程碑/突破点 |

## 四、四系统增强

### 4.1 对话系统
- 短期记忆注入 LLM context: "最近10条事件" → AI 知道刚才发生了什么
- 长期记忆语义搜索: 跨会话语义查询 → "上次你问过类似的问题"
- 情绪追踪: EmotionDetected 事件 → 情绪变化曲线 → 自适应回复策略
- 知识覆盖: 自动检测对话涉及的知识点 → ConversationKnowledgeMap

### 4.2 练习系统
- 完整轨迹: 每道题、每次犹豫、每次纠错，全量记录
- 错误模式: ErrorRecorded 聚合 → 错误聚类 → 薄弱点诊断
- 进步曲线: AnswerSubmitted 时间线 → 掌握度变化 → 可视化
- 智能复习: 事件时间线 + 遗忘曲线 → 精确复习时机

### 4.3 知识树系统
- 知识演化: 完整生命周期（创建→更新→掌握→遗忘）
- 关联发现: 跨事件流分析 → 隐含依赖关系
- 学习路径: 事件流重建 → 优化知识树结构

### 4.4 秘书系统
- 上下文感知: 查询事件流 → 知道用户刚才在做什么
- 智能时机: 事件重要性 + 用户状态 → 决策是否打扰
- 个性化建议: 长期事件记忆 → "你上次在这里卡住了"
- 自动化报告: 日/周报告由事件聚合自动生成

## 五、与现有基础设施的关系

- **Embedding**: 使用现有 `granite-embedding-97m` (OpenVINO, 384维, mean pooling + L2 norm)
- **pgvector**: 已有 HNSW 索引 (`m=16, ef_construction=200`)，复用 `vector_cosine_ops`
- **LLM**: 使用现有 `llm_service` 进行事件摘要生成
- **EventBus**: 保留，作为 EventStore 的实时通知层；EventStore 是唯一写入入口

## 六、技术决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 向量维度 | 384 | 与现有 embedding 模型一致 |
| 向量索引 | HNSW | 已有成熟实现，查询快 |
| 聚合触发 | 实时+N条触发 | 避免定时任务，即时反馈 |
| 长期记忆容量 | 全量+重要性过滤 | 全部保留，查询时按重要性排序 |
| 迁移策略 | 增量 ALTER | 保留现有 events 数据 |