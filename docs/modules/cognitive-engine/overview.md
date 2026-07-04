# Cognitive Engine 概览

## 1. 模块定位

Cognitive Engine 是 AI 伴学系统的**核心认知层**，负责：

- **统一认知量子实体** — `CognitiveNode`（partition / domain / topic / concept / atom 5 层级）
- **贝叶斯信念** — Beta(α, β) 分布表达掌握度
- **认知图谱** — 前置 / 解锁 / 联想边
- **事件驱动的全链路更新** — 练习 / 对话 / 评估三类事件统一更新
- **跨模块联动** — 通过 `EventBus` 解耦秘书 / 实践 / 对话 / 学习计划

## 2. 架构图

```
┌────────────────────────────────────────────────────────────────┐
│                     应用层 (FastAPI Routes)                     │
└──────────────────┬──────────────────────────┬──────────────────┘
                   │                          │
                   ▼                          ▼
┌─────────────────────────────────┐  ┌──────────────────────────┐
│   Practice / Conversation /     │  │  Adaptive Planner /      │
│   Secretary 调用方              │  │  Secretary / Insights    │
└──────────┬──────────────────────┘  └────────────┬─────────────┘
           │ publish events                      │ subscribe
           ▼                                     ▲
┌────────────────────────────────────────────────────────────────┐
│                EventBus / PersistentEventBus                    │
│  - 内存分发 (并行 handler)                                       │
│  - 持久化到 events 表 (单一写入路径)                              │
│  - 短期记忆 (EventMemory) → AI 上下文注入                         │
│  - 递归深度保护 (修复 B4)                                         │
└──────────────────┬─────────────────────────────────────────────┘
                   │ dispatch
                   ▼
┌────────────────────────────────────────────────────────────────┐
│              CognitiveEventHandlers (本模块)                    │
│  - handle_practice_response        (18 步全链路)                 │
│  - handle_dialogue_context_update  (对话上下文追加)              │
│  - handle_conversation_assessment  (对话评估轻量更新)            │
└──────────────────┬─────────────────────────────────────────────┘
                   │ 调用 Registry
                   ▼
┌────────────────────────────────────────────────────────────────┐
│             CognitiveOperationRegistry                          │
│  - update_belief_from_evidence (Beta 更新)                       │
│  - decay_belief (遗忘衰减)                                       │
│  - update_trend (趋势 EWMA)                                      │
└──────────────────┬─────────────────────────────────────────────┘
                   │ 写回
                   ▼
┌────────────────────────────────────────────────────────────────┐
│                  CognitiveNodeRepository                        │
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

`CognitiveNode` 是 5 层级共用同一种结构的统一量子实体。详见 `belief-model.md`。

### 3.2 Beta 分布信念

`Belief(alpha, beta, proficiency_mean, proficiency_precision)` — 详见 `belief-model.md`。

### 3.3 ZPD 调度

基于 Vygotsky 最近发展区选择最佳难度的题目。详见 `zpd-scheduler.md`。

### 3.4 事件总线

3 个核心类：`EventBus` (内存) / `PersistentEventBus` (持久化) / `EventMemory` (4 级记忆)。详见 `event-bus.md`。

## 4. 模块文件结构

```
backend/app/domain/cognitive/
├── __init__.py                  # get_repo() 入口
├── constants.py                 # 阈值 + 工具函数 (统一 mastery level)
├── models.py                    # CognitiveNode + 30+ 子模型
├── profiles.py                  # MasteryAtom / PracticeProfile / PlanningProfile / DiagnosisProfile
├── events.py                    # legacy 事件处理器 (practice/dialogue/assessment)
├── events_repository.py         # CognitiveEventsAdapter (修复 B7/B8)
├── operation_registry.py        # 操作注册/派发中心
├── growth_engine.py             # ensure_ancestors / suggest_lateral_expansion
├── writer.py                    # CognitiveNodeWriter (幂等创建)
├── edge_models.py               # KnowledgeEdge
├── memory_repository.py         # MemoryCognitiveNodeRepository (测试 fake)
└── operations/
    ├── belief_operations.py     # Beta 分布 + 衰减
    └── trend_operations.py      # EWMA + 趋势
```

## 5. 调用方

| 调用方 | 调用方式 | 触发的事件 |
|--------|---------|-----------|
| `practice_service.submit_answer` | `submit_practice()` (sync) | CognitiveNodeUpdated |
| `cognitive_sync._cognify_dialogue_context` | `submit_dialogue_context()` (sync) | CognitiveNodeUpdated |
| `cognitive_storage.sync_from_practice_event` | `event_bus.publish()` (async) | CognitiveNodeUpdated |
| `adaptive_planner.on_knowledge_updated` | event subscriber | (重算 plan) |

## 6. 设计决策

详见 `docs/adr/0010-cognitive-engine.md`。
