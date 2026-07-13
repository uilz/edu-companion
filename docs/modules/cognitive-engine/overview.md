# Cognitive Engine 概览

## 1. 模块定位

Cognitive Engine 是 AI 学习助手工具系统的**核心认知层**，负责：

- **统一认知量子实体** — `CognitiveNode`（partition / domain / topic / concept / atom 5 层级）
- **概率信念表示** — 每个节点维护 `Beta(α, β)` 后验分布，显式表达掌握度与不确定性
- **图传播** — 练习/评估信号沿认知边有界传播，表达知识点之间的结构关系
- **时间衰减** — 模拟遗忘，保持均值的同时降低信念精度
- **事件驱动的全链路更新** — 练习 / 对话 / 评估三类事件统一更新
- **跨模块联动** — 通过 `EventBus` 解耦秘书 / 实践 / 对话 / 学习计划

## 2. 架构图

```
┌────────────────────────────────────────────────────────────────┐
│                     应用层 (FastAPI Routes)                     │
│  /api/trees  /api/practice  /api/conversations  /api/secretary  │
└──────────────────┬──────────────────────────┬──────────────────┘
                   │                          │
                   │ publish events           │ query projections
                   ▼                          ▲
┌────────────────────────────────────────────────────────────────┐
│                EventBus / PersistentEventBus                    │
│  - 内存分发 (并行 handler)                                       │
│  - 持久化到 events 表 (单一写入路径)                              │
│  - 递归深度保护                                                   │
│  - 幂等去重 (idempotency_key)                                    │
└──────────────────┬─────────────────────────────────────────────┘
                   │ dispatch
                   ▼
┌────────────────────────────────────────────────────────────────┐
│              CognitiveEventHandlers                              │
│  - handle_answer_submitted      (练习答案 → Beta 更新 + 传播)    │
│  - handle_dialogue_context_update (对话上下文追加)               │
│  - handle_conversation_assessment (对话评估轻量更新)             │
└──────────────────┬─────────────────────────────────────────────┘
                   │ 调用 CognitiveOperationRegistry
                   ▼
┌────────────────────────────────────────────────────────────────┐
│             CognitiveOperationRegistry (DSL)                     │
│  - belief_update            (Beta-二项更新 + 信息增益)           │
│  - graph_propagate          (有界 BFS 结构传播)                  │
│  - decay_belief             (指数时间衰减)                       │
│  - shrinkage_prior          (子节点向父节点收缩)                 │
│  - schedule_review          (基于不确定性计算复习间隔)           │
│  - update_trend             (EWMA 趋势)                          │
└──────────────────┬─────────────────────────────────────────────┘
                   │ 写回
                   ▼
┌────────────────────────────────────────────────────────────────┐
│                  CognitiveNodeRepository                         │
│  - PgCognitiveNodeRepository (生产)                              │
│  - MemoryCognitiveNodeRepository (测试)                          │
└──────────────────┬─────────────────────────────────────────────┘
                   │ SQL
                   ▼
┌────────────────────────────────────────────────────────────────┐
│                PostgreSQL knowledge_nodes 表                     │
└────────────────────────────────────────────────────────────────┘
```

## 3. 核心概念

### 3.1 CognitiveNode

`CognitiveNode` 是 5 层级共用同一种结构的统一量子实体。详见 [`belief-model.md`](./belief-model.md)。

### 3.2 Beta 分布信念

每个认知节点维护 `Beta(α, β)` 后验分布：

- **掌握度** `proficiency = α / (α + β)`
- **不确定性** `uncertainty = sqrt(αβ / ((α+β)²(α+β+1)))`
- **信息增益** `IG = H(Beta_before) - H(Beta_after)`

信念更新根据题目难度调制 α/β 增量。详见 [`belief-model.md`](./belief-model.md) 与 ADR 0015。

### 3.3 图传播

当节点收到练习信号时，更新量沿认知边有界传播：

- 默认最多 2 跳
- 传播因子 = 边权重 × 距离衰减 × 方向因子 × 目标独立证据权重
- prerequisite 仅 forward；hierarchy 双向但 parent→child 更强；co_occurrence/chunk 双向对称

### 3.4 时间衰减

模拟遗忘，保持均值不变，降低精度：

```
effective_rate = forgetting_rate * (1 - stability_factor)
total_decayed = (α + β) * exp(-effective_rate * Δt_days)
α_new = max(α_min, total_decayed * p)
β_new = max(β_min, total_decayed * (1 - p))
```

### 3.5 收缩先验

子节点数据稀疏时，其有效信念向父节点收缩：

```
λ = shrinkage_strength / (shrinkage_strength + evidence_count)
α_effective = λ * α_parent + (1 - λ) * α_child
β_effective = λ * β_parent + (1 - λ) * β_child
```

### 3.6 事件总线

`PersistentEventBus` 保证事件不丢失：内存分发后立即持久化到 `events` 表；进程重启后按序恢复投递。3 个核心类：`EventBus` / `PersistentEventBus` / `EventMemory`。详见 [`event-bus.md`](./event-bus.md)。

## 4. 模块文件结构

```
backend/app/domain/cognitive/
├── __init__.py                  # get_repo() 入口
├── constants.py                 # 阈值 + 工具函数 (统一 mastery level)
├── models.py                    # CognitiveNode + 30+ 子模型
├── profiles.py                  # MasteryAtom / PracticeProfile / PlanningProfile / DiagnosisProfile
├── events.py                    # 事件处理器 (answer_submitted / dialogue / assessment)
├── events_repository.py         # CognitiveEventsAdapter
├── operation_registry.py        # 操作注册/派发中心
├── growth_engine.py             # ensure_ancestors / suggest_lateral_expansion
├── writer.py                    # CognitiveNodeWriter (幂等创建)
├── edge_models.py               # KnowledgeEdge
├── memory_repository.py         # MemoryCognitiveNodeRepository (测试 fake)
└── operations/
    ├── __init__.py
    ├── belief_operations.py     # Beta 分布更新 + 信息增益
    ├── graph_propagation_operations.py  # 有界图传播
    ├── scheduling_operations.py # 复习调度
    └── trend_operations.py      # EWMA + 趋势

backend/app/infrastructure/db/
├── projection_builder.py        # 认知投影构建
├── cognitive_view_mapper.py     # 认知视图映射
├── cognitive_event_repository.py # 认知事件幂等存储
└── models/cognitive.py          # ORM 模型
```

## 5. 数据流

### 5.1 练习答案提交

```
POST /api/practice/sessions/{id}/submit
    │
    ▼
practice engine.publish_practice_events
    │
    ▼
AnswerSubmitted ──► PersistentEventBus
    │
    ▼
CognitiveEventHandler.handle_answer_submitted
    │
    ├─► operation_registry.dispatch("belief_update")
    │       ├─► 更新当前节点 α/β
    │       └─► 计算 information_gain
    │
    ├─► operation_registry.dispatch("graph_propagate")
    │       └─► 沿边更新邻居节点（最多 2 跳）
    │
    ├─► projection_builder.refresh_projection
    │       └─► 写回 cognitive_node_projections
    │
    └─► 发布 CognitiveNodeMetadataChanged / CognitiveStateChanged
            ├─► secretary（生成复习/练习提案）
            ├─► planning.proactive_generator（建议计划项）
            └─► learning_activity（写入学习活动）
```

### 5.2 对话评估

```
对话评估完成
    │
    ▼
handle_conversation_assessment
    │
    ▼
belief_update（轻量权重）
    │
    ▼
CognitiveNodeMetadataChanged
```

## 6. 调用方与事件

| 调用方 | 触发事件 | 说明 |
|--------|---------|------|
| `app.services.practice.engine` | `AnswerSubmitted` | 练习答案提交 |
| `app.domain.conversation.context_pipeline` | `DialogueContextUpdated` | 对话上下文更新 |
| `app.services.conversation.assessment` | `ConversationAssessmentCompleted` | 对话评估完成 |

## 7. 消费方

| 消费者 | 订阅事件 | 行为 |
|--------|---------|------|
| `secretary` | `CognitiveNodeMetadataChanged` | 生成复习/练习提案 |
| `planning.proactive_generator` | `CognitiveNodeMetadataChanged` / `SessionCompleted` | 建议计划项 |
| `learning_activity_handler` | `AnswerSubmitted` / `SessionCompleted` / ... | 写入学习活动 |
| `knowledge-tree` | `CognitiveStateChanged` | 刷新认知视图 |

## 8. 设计决策

| # | 决策点 | 方案 |
|---|--------|------|
| 1 | 信念模型 | Beta-二项后验（ADR 0015） |
| 2 | 结构传播 | 有界 BFS，最多 2 跳，方向性与距离衰减 |
| 3 | 遗忘模型 | 指数衰减精度，保持均值 |
| 4 | 稀疏数据处理 | shrinkage prior 向父节点收缩 |
| 5 | 复习调度 | 基于 Beta 方差（不确定性） |
| 6 | 事件持久化 | PersistentEventBus 写入 events 表 |
| 7 | 幂等去重 | SHA-256 短哈希 idempotency_key |

## 9. 相关文档

| 文档 | 说明 |
|------|------|
| [belief-model.md](./belief-model.md) | Beta 信念模型细节 |
| [zpd-scheduler.md](./zpd-scheduler.md) | ZPD 选题调度 |
| [event-bus.md](./event-bus.md) | 事件总线架构 |
| [activation-belief.md](./activation-belief.md) | 激活信念机制 |
| [docs/adr/0010-cognitive-engine.md](../../adr/0010-cognitive-engine.md) | Cognitive Engine 架构决策 |
| [docs/adr/0015-cognitive-probabilistic-graph.md](../../adr/0015-cognitive-probabilistic-graph.md) | 图上的概率动态系统 |
