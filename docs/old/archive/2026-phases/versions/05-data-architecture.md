# Edu-Companion 数据架构设计

> 版本: 2.0 | 日期: 2026-06-24
> 基于全量代码审计 + 运行时分析产出

---

## 目录

1. [审计现状](#1-审计现状)
2. [核心问题诊断](#2-核心问题诊断)
3. [统一数据架构](#3-统一数据架构)
4. [数据域定义与归属](#4-数据域定义与归属)
5. [事件总线状态](#5-事件总线状态)
6. [API 表面分析](#6-api-表面分析)
7. [清理计划](#7-清理计划)

---

## 1. 审计现状

### 1.1 表清单（19 张）

| # | 表名 | 所有者模块 | 行数级 | 状态 |
|---|------|-----------|--------|------|
| 1 | `knowledge_states` | db/database.py | ~500 | 🔴 **待废弃** — BKT旧模型 |
| 2 | `questions` | db/database.py | ~100 | ✅ 正常 |
| 3 | `practice_sessions` | db/database.py | ~50 | ✅ 正常 |
| 4 | `attempts` | db/database.py | ~500 | ✅ 正常 |
| 5 | `error_book` | db/database.py | ~100 | ✅ 正常 |
| 6 | `materials` | db/database.py | ~10 | ✅ 正常 |
| 7 | `material_chunks` | db/database.py | ~50 | ✅ 正常 |
| 8 | `cognitive_nodes` | cognitive_schema.sql | ~200 | ✅ **核心表** |
| 9 | `cognitive_events` | cognitive_schema.sql | ~5000 | ✅ 正常 |
| 10 | `knowledge_edges` | phase8_schema.sql | ~30 | ✅ 正常 |
| 11 | `conversation_partitions` | conversation_schema.sql | ~10 | ✅ 正常 |
| 12 | `conversation_branches` | conversation_schema.sql | ~30 | ✅ 正常 |
| 13 | `conversation_nodes` | conversation_schema.sql | ~500 | ✅ 正常 |
| 14 | `conversation_response_blocks` | conversation_schema.sql | ~500 | ✅ 正常 |
| 15 | `conversation_link_nodes` | conversation_schema.sql | ~5 | ✅ 正常 |
| 16 | `conversation_user_meta` | conversation_schema.sql | 1 | 🟡 **臃肿** — 8个冗余JSONB列 |
| 17 | `conversation_node_links` | phase8_schema.sql | ~100 | ✅ 正常 |
| 18 | `secretary_proposals` | secretary.py inline | ~20 | 🟡 **双重定义** |
| 19 | `plan_snapshots` | adaptive_planner.py | ~10 | ✅ 正常 |

### 1.2 事件总线状态

| 指标 | 数值 |
|------|------|
| 定义的事件类型 | **11** |
| 实际发布的事件类型 | **10**（1个废弃孤儿: KnowledgeStateUpdated） |
| 注册的订阅 | **22** |
| 实际活跃的处理器 | **22**（0个死处理器，全部有实际逻辑） |
| 事件链 | AnswerSubmitted→CognitiveNodeUpdated→ZPD/Practice, AssistantReplied→Multimedia/Secretary |

### 1.3 API 表面

| 指标 | 数值 |
|------|------|
| 后端端点总数 | 待统计 |
| 有前端调用的 | 待统计 |
| 无前端消费者的 | **0** — 所有后端端点均有前端消费者 |
| 前端调用不存在端点的 | **4**（僵尸调用，运行时 404） |
| 僵尸调用路径 | `/api/knowledge/judge-answer`, `/api/search/media`, `/api/conversations/tree/partition`, `/api/conversations/tree/topic` |

---

## 2. 核心问题诊断

### 问题 1：双知识状态源 🔴

```
knowledge_states (BKT: p_known/p_learned/p_guess/p_slip/p_transit)
        ↕  不同步
cognitive_nodes (Beta: belief.alpha/beta + 15子系统)
```

**症状**：练习更新 BKT，CognitiveNode 由事件链异步更新，两者可能不一致。adaptive_planner 读 BKT，secretary 读 CognitiveNode，看到的是不同的掌握度。

### 2.2 问题 2：conversation_user_meta 膨胀 🔴

```sql
-- Phase 6.5 通过 ALTER TABLE 添加的 8 个 JSONB 列
conversation_user_meta.knowledge_states   -- 复制 knowledge_states
conversation_user_meta.practice_sessions  -- 复制 practice_sessions
conversation_user_meta.error_book         -- 复制 error_book
conversation_user_meta.event_log          -- 复制 cognitive_events
conversation_user_meta.domains            -- 冗余
conversation_user_meta.topics             -- 冗余
conversation_user_meta.files              -- 冗余
conversation_user_meta.background_jobs    -- 冗余
```

**症状**：同一份数据两个写入点，不知道哪个是最新的。这是过渡期的"JSONB 垃圾场"。

### 2.3 问题 3：旧四层模型与 DirectoryNode 双模型并行 🟡

系统当前处于从旧四层模型（Partition/Domain/Topic/Conversation）向统一 DirectoryNode 模型的迁移过程中。

**遗留代码路径**：

| 文件 | 遗留代码 | 影响 |
|------|---------|------|
| [context_pipeline.py](file:///home/deploy/edu-companion/backend/app/domain/conversation/context_pipeline.py#L147-L174) | `ConversationLocation` provider 通过 `data.partitions`/`data.conversations`/`data.topics` 读取旧模型 | 对话上下文构建依赖旧模型 |
| [practice_integrator.py](file:///home/deploy/edu-companion/backend/app/services/practice/practice_integrator.py#L36-L84) | `data.conversations.get()`、`data.partitions.get()`、`branch.practice_sessions` 等旧字段 | 练习结果写入依赖旧模型 |
| [schemas/conversation.py](file:///home/deploy/edu-companion/backend/app/schemas/conversation.py#L260-L281) | `UserData` 的合成属性从 DirectoryNodes 重建旧模型视图 | 兼容层增加复杂性和心智负担 |
| [tree_sub_branch.py](file:///home/deploy/edu-companion/backend/app/services/knowledge/tree_sub_branch.py#L24-L27) | 回退逻辑同时尝试新旧模型 | 子分支操作有歧义路径 |

**决策**：完全弃用旧模型，DirectoryNode 为唯一模型。不考虑与其他模块的兼容性。

### 2.4 问题 4：adaptive_planner 忽略认知层 🟡

```python
# adaptive_planner.py 当前逻辑
p_known = knowledge_state.get('p_known', 0.5)  # 只读 BKT
urgency = (1 - p_known) * 1.0                   # 单维度决策

# 未读取的 CognitiveNode 数据：
# - belief.proficiency_mean + proficiency_precision
# - trend.direction + stagnation_days
# - scheduling.urgency + next_review
# - error_clusters（错误模式）
# - cognitive_load（认知负荷）
# - metacognition.calibration_error（元认知偏差）
```

### 2.5 问题 5：PostProcessor 静默失败 🟡

PostProcessor 链中的 [CognitiveSyncHook](file:///home/deploy/edu-companion/backend/app/domain/conversation/reply_pipeline.py#L205-L218) 和 [KnowledgeEvidenceHook](file:///home/deploy/edu-companion/backend/app/domain/conversation/reply_pipeline.py#L221-L231) 在异常时仅记录 debug 日志。失败会导致：
- 认知节点不同步（用户无感知）
- 对话知识证据丢失

**决策**：建立管理员报错系统，PostProcessor 失败上报到 admin 通知通道。

### 2.6 问题 6：内联练习与独立练习分离 🟡

| 维度 | 内联练习（对话中） | 独立练习（/api/practice） |
|------|-------------------|-------------------------|
| 知识状态更新 | 写 CognitiveNode | 写 knowledge_states |
| 事件触发 | 无 | AnswerSubmitted |
| 错题记录 | 不写 | 写 error_book |
| 秘书感知 | 不感知 | 诊断+建议 |
| 记忆写入 | 不写 | 不写 |

---

## 3. 统一数据架构

### 3.1 设计哲学

**CognitiveNode 是唯一的知识状态源。** 所有子系统通过读写 CognitiveNode 获取/更新知识状态。不再有 BKT 并行路径。

**DirectoryNode 是唯一的对话模型。** 不再有 Partition/Domain/Topic/Conversation 四层模型。所有对话以 DirectoryNode（`node_type="conv"`）表示，组织在 DirectoryNode 树（`node_type="dir"`）中。

### 3.2 架构全景

```
                    ┌─────────────────────────────────────┐
                    │          用户输入层                  │
                    │  (对话 / 练习作答 / 自评 / 语音)    │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       对话引擎 (Conversation)       │
                    │  DirectoryNode 树 + MessageNode      │
                    │  → 唯一的用户交互记录源              │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌────────────────┐  ┌────────────────┐
    │  练习子系统      │  │ 知识图谱子系统  │  │ 多媒体子系统    │
    │  questions       │  │ cognitive_     │  │ (TTS/图片)      │
    │  attempts        │  │   nodes  ★     │  │                │
    │  error_book      │  │ knowledge_     │  │                │
    │  practice_sessions│  │   edges        │  │                │
    └────────┬────────┘  └───────┬────────┘  └────────────────┘
             │                   │
             │    ┌──────────────┘
             ▼    ▼
    ┌──────────────────────────────────────────┐
    │       ★ CognitiveNode（唯一知识状态源）★  │
    │                                          │
    │  belief: {alpha, beta, proficiency_mean} │
    │  trend:  {direction, stagnation_days}    │
    │  scheduling: {urgency, next_review}      │
    │  error_clusters: [{pattern, count}]      │
    │  metacognition: {calibration_error}      │
    │  practice_summary: {attempts, accuracy}  │
    │  engagement: {xp, streak}                │
    │  dialogue_contexts: [{session, branch}]  │
    └────────┬──────────┬──────────┬───────────┘
             │          │          │
    ┌────────▼───┐ ┌────▼────┐ ┌──▼──────────┐
    │ 秘书系统    │ │ 自适应   │ │ 行为分析     │
    │ secretary   │ │ 规划器   │ │ analytics   │
    │ proposals   │ │ adaptive │ │ habits      │
    │             │ │ planner  │ │             │
    └────────────┘ └─────────┘ └─────────────┘
```

### 3.3 数据流规则

| # | 规则 | 说明 |
|---|------|------|
| R1 | **CognitiveNode 是唯一真相源** | `knowledge_states` 表废弃，BKT 字段迁移到 `belief` |
| R2 | **DirectoryNode 树是唯一交互记录** | `conversation_user_meta` 的 8 个 JSONB 列全部废弃 |
| R3 | **子系统通过事件更新 CognitiveNode** | 不直接改 CognitiveNode（除了练习的同步路径） |
| R4 | **EventBus 是唯一跨模块通信机制** | 消灭直接函数调用（`_compute_partition_progress_cognitive` 等） |
| R5 | **conversation_node_links 是对话↔知识的唯一桥梁** | 一次对话关联哪些知识点，通过此表查询 |

---

## 4. 数据域定义与归属

### 4.1 六大数据域

| 数据域 | 核心表 | 所有者 | 读者 |
|--------|--------|--------|------|
| **知识状态** | `cognitive_nodes` | cognitive/storage.py | secretary, planner, analytics, conversation |
| **知识结构** | `cognitive_nodes`（结构字段）+ `knowledge_edges` | cognitive/edge_service.py | 前端图谱可视化 |
| **练习记录** | `questions` + `attempts` + `practice_sessions` + `error_book` | domain/practice/service.py | secretary, planner, analytics |
| **对话记录** | `conversation_user_meta`（DirectoryNode JSONB） | domain/conversation/service.py | secretary（上下文） |
| **规划状态** | `plan_snapshots` | services/adaptive_planner.py | conversation（建议） |
| **主动建议** | `secretary_proposals` | domain/secretary/service.py | 前端 UI |

### 4.2 CognitiveNode 字段 → 消费者映射

| CognitiveNode 字段组 | 写入者 | 读取者 | 更新频率 |
|---------------------|--------|--------|---------|
| `belief` (alpha/beta/proficiency) | 练习事件链 | 秘书/规划器/图谱 | 每次作答 |
| `trend` (direction/stagnation) | 练习事件链 | 秘书(停滞检测)/规划器 | 每次作答 |
| `scheduling` (urgency/next_review) | 练习事件链→ZPD | 规划器(日程排序) | 每次作答 |
| `error_clusters` | 练习事件链 | 秘书(错误诊断)/对话(精准答疑) | 答错时 |
| `practice_summary` | 练习事件链 | 前端(统计卡片)/规划器 | 每次作答 |
| `engagement` (xp/streak) | 练习事件链 | 前端(游戏化) | 每次作答 |
| `dialogue_contexts` | 对话系统 | 规划器(deep_processing选择) | 每次AI回复 |
| `cognitive_load` | 练习事件链(计算) | 规划器(负荷调节) | 每次作答 |
| `metacognition` | 自评事件 | 秘书(偏差校准) | 自评时 |
| `activation` | 练习事件链(ACT-R) | 对话(记忆检索) | 每次作答 |

---

## 5. 事件总线状态

### 5.1 当前事件一览

| 事件类型 | 发布位置 | 订阅者 | 状态 |
|---------|---------|--------|------|
| `AnswerSubmitted` | practice/service.py | analytics, habit, knowledge (3) | ✅ 活跃 |
| `ErrorRecorded` | practice/service.py | knowledge, media (2) | ✅ 活跃 |
| `SessionCompleted` | practice/service.py | session_bridge, planning, zpd, event_memory, secretary (5) | ✅ 活跃 |
| `KnowledgeStateUpdated` | 无 | 无 | ❌ **已废弃** — 待删除 |
| `AssistantReplied` | conversation_processor.py | multimedia, secretary, event_memory, sync_hook (4) | ✅ 活跃 |
| `MessageClassified` | cognitive API | cascade + proposal (1) | ✅ 活跃 |
| `PracticeSubmitted` | practice/service.py | 信念更新, secretary (2) | ✅ 活跃 |
| `NodeCreated` | knowledge_node_service | 波纹边检测 (1) | ✅ 活跃 |
| `ProposalAccepted` | secretary API | 执行动作 (1) | ✅ 活跃 |
| `PendingCrossTopic` | classifier_service | 关联提案 (1) | ✅ 活跃 |
| `CognitiveNodeUpdated` | cognitive_storage, practice_service | planning+zpd, practice, secretary (3) | ✅ 活跃 |

**总计**：11 个事件类型，10 个活跃发布，22 个订阅处理器，0 个死处理器。

### 5.2 唯一待清理项

- **`KnowledgeStateUpdated`** — 已标记 `DEPRECATED`（events.py L98），仍留在 `EVENT_TYPES` 注册表中。删除即可。

### 5.3 事件流全图

```
用户作答
  │
  ├─→ [同步] 练习系统写入 CognitiveNode (18步更新链)
  │         ├─→ publish(AnswerSubmitted)
  │         │     ├─→ analytics.on_answer     → 行为日志 + 疲劳
  │         │     ├─→ secretary.on_answer     → 诊断 + 建议
  │         │     └─→ knowledge.on_answer     → 知识图谱更新
  │         │
  │         ├─→ publish(ErrorRecorded)  (答错时)
  │         │     ├─→ knowledge.on_error       → error_clusters
  │         │     └─→ media.on_error           → 视频推荐
  │         │
  │         └─→ publish(PracticeSubmitted)
  │               └─→ 信念更新 → CognitiveNodeUpdated
  │                     ├─→ planning+zpd       → 排期更新
  │                     ├─→ practice           → 难度调整
  │                     └─→ secretary          → 主动建议
  │
AI回复
  │
  ├─→ [同步] 对话系统写入 MessageNode
  │
  └─→ publish(AssistantReplied)
        ├─→ multimedia.on_reply   → TTS + 图片
        ├─→ secretary             → 记录交互
        ├─→ event_memory          → 工作记忆写入
        └─→ sync_hook             → 知识节点同步
```

---

## 6. API 表面分析

### 6.1 实际状况

| 指标 | 之前声称 | 实际审计结果 |
|------|---------|-------------|
| 后端端点无前端消费 | ~95（61%） | **0** — 所有端点均有消费者 |
| 前端调用不存在端点 | 2 | **4**（僵尸调用，运行时 404） |

### 6.2 前端僵尸调用

| 路径 | 所在文件 | 问题 |
|------|---------|------|
| `POST /api/knowledge/judge-answer` | 知识组件 | 端点不存在 → 404 |
| `GET /api/search/media` | 媒体搜索组件 | 端点不存在 → 404 |
| `GET /api/conversations/tree/partition` | 对话树组件 | 旧版端点已移除 → 404 |
| `GET /api/conversations/tree/topic` | 对话树组件 | 旧版端点已移除 → 404 |

### 6.3 建议动作

1. 修复 2 个运行时错误端点（`judge-answer`, `search/media`）
2. 清理 2 个废弃前端代码路径（`tree/partition`, `tree/topic`）
3. 其余后端端点全部有消费者，无需缩减

---

## 7. 清理计划

### 7.1 任务 A：文档更新 ✅（已完成）

更新架构文档以反映当前真实状态。

### 7.2 任务 B：清理旧四层模型遗留代码

| 文件 | 改动内容 |
|------|---------|
| `context_pipeline.py` | 重写 `ConversationLocation` provider，从 DirectoryNode 模型读取对话层级 |
| `practice_integrator.py` | 改用 DirectoryNode API 写入练习结果 |
| `schemas/conversation.py` | 移除 `UserData` 中的旧模型合成属性 |
| `schemas/directory_node.py` | 移除向后兼容字段 |
| `tree_sub_branch.py` | 移除回退逻辑，仅使用 DirectoryNode |

### 7.3 任务 C：构建管理员报错系统

| 组件 | 说明 |
|------|------|
| Admin 错误通道 | PostProcessor 失败时写入 admin 可见的错误日志表 |
| 错误聚合 | 按类型/时间聚合相同错误，避免刷屏 |
| 通知机制 | 通过 SSE 或 WebSocket 推送到管理面板 |

### 7.4 任务 D：修复前端僵尸调用

| 路径 | 动作 |
|------|------|
| `/api/knowledge/judge-answer` | 补充端点或清理前端调用 |
| `/api/search/media` | 补充端点或清理前端调用 |
| `/api/conversations/tree/partition` | 清理前端废弃代码 |
| `/api/conversations/tree/topic` | 清理前端废弃代码 |

### 7.5 搁置项

| 项 | 原因 |
|----|------|
| 对话摘要缓存策略 | 暂时搁置 |
| 练习-对话模块双向集成 | 待其他清理完成后整体重做 |

### 7.6 验收标准

| # | 验收项 | 验证方法 |
|---|--------|---------|
| ✅-1 | `data.partitions`/`data.conversations`/`data.topics` 不再被任何代码读取 | `grep -r "data\.(partitions\|conversations\|topics)" backend/` 无命中 |
| ✅-2 | `UserData` 无旧模型合成属性 | `grep -r "def partitions\|def conversations\|def topics" backend/app/schemas/` 无命中 |
| ✅-3 | PostProcessor 失败写入 admin 错误表 | 触发 CognitiveSyncHook 异常后，admin 错误表有记录 |
| ✅-4 | `KnowledgeStateUpdated` 从 events.py 删除 | `grep -r "KnowledgeStateUpdated" backend/shared/` 无命中 |
| ✅-5 | 前端无 404 端点调用 | 浏览器 Network 面板零 404 |

---

## 附录：遗留决策记录

| # | 决策 | 理由 | 时间 |
|---|------|------|------|
| D1 | MongoDB → PostgreSQL JSONB | 单用户 MVP 不需要分布式 | Phase 1 |
| D2 | Kafka → asyncio EventBus | 单进程不需要消息队列 | Phase 1 |
| D3 | Redis → 内存 dict + PG | 会话状态通过 PG 持久化 | Phase 1 |
| D4 | BKT → Beta belief | 更丰富的不确定性建模 | Phase 6 |
| D5 | 独立练习 session (MVP) | 过渡方案，最终回归对话树 | Phase 3 |
| D6 | conversation_user_meta JSONB 扩展 | 过渡方案，Phase A 清理 | Phase 6.5 |
| D7 | 旧四层模型 → DirectoryNode | 统一数据模型，消除双模型并行 | Phase 8 |
| D8 | PostProcessor 静默失败 → Admin 报错系统 | 失败可见性，替代静默降级 | Phase 8 |
