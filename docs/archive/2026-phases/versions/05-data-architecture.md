# Edu-Companion 数据架构设计

> 版本: 1.0 | 日期: 2026-05-27
> 基于全量代码审计（19张表、155端点、15事件类型）产出

---

## 目录

1. [审计现状](#1-审计现状)
2. [核心问题诊断](#2-核心问题诊断)
3. [统一数据架构](#3-统一数据架构)
4. [数据域定义与归属](#4-数据域定义与归属)
5. [事件总线清理](#5-事件总线清理)
6. [API 表面缩减](#6-api-表面缩减)
7. [迁移路径](#7-迁移路径)

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
| 定义的事件类型 | 15 |
| 实际发布的事件类型 | **8**（7个孤儿） |
| 注册的订阅 | 20 |
| 实际活跃的处理器 | **11**（9个死处理器） |
| 事件链 | AnswerSubmitted→CognitiveNodeUpdated→ZPD, AssistantReplied→Audio/Image |

### 1.3 API 表面

| 指标 | 数值 |
|------|------|
| 后端端点总数 | **155** |
| 有前端调用的 | ~60（39%） |
| 无前端消费者的 | **~95（61%）** |
| 前端调用不存在端点 | 2 |
| v1/v2 重叠 | 3 |

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

### 2.3 问题 3：事件总线空转 🟡

**7 个孤儿事件**（定义了但从未发布）：

| 事件 | 订阅者 | 发布者 | 诊断 |
|------|--------|--------|------|
| HintRequested | 无 | 无 | 设计遗留，从未实现 |
| WeaknessDetected | 无 | 无 | 应由 secretary 发布 |
| StudyPlanGenerated | conversation_service | 无 | 应由 adaptive_planner 发布 |
| DailyGoalAchieved | conversation_service | 无 | 应由 analytics 发布 |
| AchievementUnlocked | 无 | 无 | 游戏化模块未实现 |
| MaterialUploaded | 无 | 无 | 前端已传文件但未触发事件 |
| MaterialIndexed | material_service | 无 | 索引完成但未发布 |

**9 个死处理器**（注册了但只写 log）：

| 处理器 | 本应做什么 |
|--------|-----------|
| analytics.on_answer_submitted | 行为分析 → 行为报告 |
| knowledge.on_answer_submitted | 知识图谱更新 |
| knowledge.on_error_recorded | 迷思概念图谱 |
| media.on_error_recorded | 相关视频/材料推荐 |
| conversation.on_session_completed | 会话摘要更新 |
| planning.on_session_completed | 练习后规划调整 |
| conversation.on_knowledge_updated | 知识状态→对话上下文 |
| material.on_indexed | 材料→自动出题 |
| PlanningServiceImpl.on_answer_submitted | 定义了但**从未订阅** |

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

### 2.5 问题 5：内联练习与独立练习分离 🟡

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

**对话是交互的唯一入口。** 所有用户交互（对话、练习、复习）都挂载在对话树上。不存在"独立练习 session"——练习通过对话分支产生和记录。

### 3.2 架构全景

```
                    ┌─────────────────────────────────────┐
                    │          用户输入层                  │
                    │  (对话 / 练习作答 / 自评 / 语音)    │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       对话引擎 (Conversation)       │
                    │  conversation_partitions/branches/  │
                    │  nodes + response_blocks            │
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
| R2 | **对话树是唯一交互记录** | `conversation_user_meta` 的 8 个 JSONB 列全部废弃 |
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
| **对话记录** | `conversation_*`（7张表） | domain/conversation/service.py | secretary（上下文） |
| **规划状态** | `plan_snapshots` | services/adaptive_planner.py | conversation（建议） |
| **主动建议** | `secretary_proposals` | domain/secretary/service.py | 前端 UI |

### 4.2 跨域数据共享规则

```
知识状态域:
  写入者: 练习系统 (AnswerSubmitted 事件链)
          对话系统 (dialogue_context_update 事件)
          诊断系统 (diagnostic_result 事件)
  读取者: 秘书 (诊断+建议)
          规划器 (难度+紧迫度)
          图谱 (可视化)
          对话 (上下文感知)

练习记录域:
  写入者: 练习系统 (同步写入)
  读取者: 知识状态 (更新 belief)
          秘书 (错误模式)
          分析 (学习行为)

对话记录域:
  写入者: 对话系统 (同步写入)
  读取者: 知识状态 (dialogue_contexts)
          秘书 (会话摘要)
          多媒体 (响应后处理)
```

### 4.3 CognitiveNode 字段 → 消费者映射

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

## 5. 事件总线清理

### 5.1 废弃事件（7个）

```diff
- HintRequested        → 从未发布/订阅，删除
- WeaknessDetected     → 合并到 AnswerSubmitted（弱项检测在处理链中完成）
- MaterialUploaded     → 合并到 MaterialIndexed（上传→索引是同步的）
- MaterialIndexed      → 保留但补全发布者
- StudyPlanGenerated   → 保留但补全发布者（adaptive_planner）
- DailyGoalAchieved    → 保留但补全发布者（analytics）
- AchievementUnlocked  → 游戏化未实现，暂标记 stub
```

### 5.2 必须激活的死处理器（按优先级）

| # | 处理器 | 激活后做什么 | P |
|---|--------|-------------|---|
| 1 | `media.on_error_recorded` | 根据 error_type 推荐相关视频/材料 | P0 |
| 2 | `knowledge.on_error_recorded` | 更新 error_clusters 到 CognitiveNode | P0 |
| 3 | `analytics.on_answer_submitted` | 写入学习行为日志 + 疲劳检测 | P1 |
| 4 | `planning.on_session_completed` | 练习结束后触发规划器重评估 | P1 |
| 5 | `conversation.on_knowledge_updated` | 将新掌握的知识点推送到对话上下文 | P1 |
| 6 | `material.on_indexed` | 索引完成后自动生成配套练习题 | P2 |

### 5.3 事件流清理后全图

```
用户作答
  │
  ├─→ [同步] 练习系统写入 CognitiveNode (18步更新链)
  │         ├─→ publish(AnswerSubmitted)
  │         │     ├─→ analytics.on_answer     → 行为日志 + 疲劳
  │         │     ├─→ secretary.on_answer     → 诊断 + 建议
  │         │     ├─→ cognitive.on_answer      → CognitiveNodeUpdated
  │         │     │     └─→ zpd.on_cognitive   → 排期更新
  │         │     └─→ media.on_answer          → 多媒体推荐
  │         │
  │         ├─→ publish(ErrorRecorded)  (答错时)
  │         │     ├─→ knowledge.on_error       → error_clusters
  │         │     └─→ media.on_error           → 视频推荐
  │         │
  │         └─→ publish(KnowledgeStateUpdated) (掌握度变化时)
  │               ├─→ planning.on_knowledge    → 重规划
  │               └─→ secretary.on_knowledge   → 主动建议
  │
AI回复
  │
  ├─→ [同步] 对话系统写入 conversation_nodes
  │
  └─→ publish(AssistantReplied)
        ├─→ multimedia.on_reply → TTS + 图片
        │     ├─→ publish(AudioSynthesized) → WS推送
        │     └─→ publish(ImageRendered)    → WS推送
        └─→ cognitive.on_reply → dialogue_context_update
```

---

## 6. API 表面缩减

### 6.1 当前 155 端点 → 目标 50 端点

| 模块 | 当前端点数 | 目标 | 动作 |
|------|-----------|------|------|
| conversation | 28 | 12 | 删除 v1 重叠端点 |
| practice | 22 | 10 | 合并独立+内联，删除 v1 |
| knowledge/graph | 15 | 5 | 删除旧 knowledge_graph.py 路由 |
| cognitive | 18 | 8 | 合并重复查询端点 |
| secretary | 8 | 4 | 简化查询接口 |
| adaptive_planner | 6 | 3 | 合并 generate + adjust |
| analytics | 12 | 4 | 删除未消费端点 |
| multimedia | 5 | 3 | 保留核心 |
| materials | 8 | 3 | 前端只用 upload |
| content | 4 | 0 | 完全未使用，删除 |
| learning_events | 2 | 0 | 完全未使用，删除 |
| workspace | 3 | 1 | 保留 upload |
| **合计** | **155** | **56** | **减 64%** |

### 6.2 删除的端点类别

1. **v1/v2 重叠**：保留 v2，废弃 v1
2. **无前端消费者**：标记 `deprecated`，3个月后删除
3. **空实现**：返回 stub 数据的端点，直接删除
4. **内部调试**：只在开发中使用的端点，移除路由

---

## 7. 迁移路径

### 7.1 Phase A：数据层统一（1周）

| 任务 | 文件改动 | 验证 |
|------|---------|------|
| A1: 废弃 `knowledge_states` | 迁移 belief 字段到 cognitive_nodes，删除读写代码 | `psql -c "SELECT count(*) FROM knowledge_states"` 后不再访问 |
| A2: 清理 `conversation_user_meta` | 删除 8 个 JSONB 列，确认无代码读取 | 全量 grep `knowledge_states.*JSONB` |
| A3: 统一 secretary_proposals | 删除 secretary_schema.sql 中的重复定义 | 建表由 secretary.py 统一管理 |
| A4: 确认 CognitiveNode 为唯一真相源 | 删除 `_compute_partition_progress_cognitive` + `_legacy` 双路径 | API 返回值一致 |

### 7.2 Phase B：事件总线修复（1周）

| 任务 | 文件改动 | 验证 |
|------|---------|------|
| B1: 删除 7 个孤儿事件定义 | shared/events.py | 编译通过 |
| B2: 激活 6 个死处理器 | 各 handler 文件 | 事件触发后 DB 有新记录 |
| B3: 消除 AnswerSubmitted 双发布 | practice.py legacy 路径 | 事件只触发一次 |
| B4: adaptive_planner 读取 CognitiveNode | adaptive_planner.py | `plan_snapshots.changes_json` 包含 trend/urgency |

### 7.3 Phase C：API 瘦身（1周）

| 任务 | 文件改动 | 验证 |
|------|---------|------|
| C1: 标记 95 个未使用端点为 deprecated | 各 api/*.py | Swagger UI 显示 deprecated 标记 |
| C2: 删除 content + learning_events 模块 | 删除 api/content.py, api/learning_events.py | tsc + 编译通过 |
| C3: 修复前端 2 个错误端点调用 | GraphTab.tsx, OverviewTab.tsx | API 返回正确数据 |

### 7.4 Phase D：内联练习统一（1周）

| 任务 | 文件改动 | 验证 |
|------|---------|------|
| D1: 内联练习走事件链 | 对话内 inline practice → AnswerSubmitted 事件 | 秘书能感知内联练习 |
| D2: 内联练习写 error_book | AnswerSubmitted handler 补充 | error_book 有内联练习记录 |
| D3: 删除 conversation_user_meta 中的练习字段 | ALTER TABLE DROP COLUMN | 无代码引用 |

### 7.5 验收标准

| # | 验收项 | 验证方法 |
|---|--------|---------|
| ✅-1 | knowledge_states 表不再被任何代码读写 | `grep -r "knowledge_states" backend/` 无命中 |
| ✅-2 | CognitiveNode 是唯一知识状态源 | 18步更新链在每次作答后完整执行 |
| ✅-3 | 事件处理器零死代码 | 所有 `on_*` handler 有实际逻辑（非 log-only） |
| ✅-4 | 内联练习与独立练习走同一路径 | 两种练习都触发 AnswerSubmitted 事件 |
| ✅-5 | adaptive_planner 读取 CognitiveNode | plan_snapshots 包含 trend.direction + urgency |
| ✅-6 | 前端无 404 端点调用 | 浏览器 Network 面板零 404 |
| ✅-7 | secretary 能感知所有练习事件 | 两种练习都产生 secretary_proposals |

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
