# Phase 9 · 全链路集成 & 债务清理实施方案

> **版本**: v1.0  
> **工期**: 4 周  
> **目标**: 打通 Phase 1–8 的所有断裂，建立测试安全网，消除双存储分叉，使认知数据真正流动  
> **原则**: 不新增任何功能需求，只做整合、修复和优化

---

## 目录

1. [深度审计发现](#1-深度审计发现)
2. [全局断裂地图](#2-全局断裂地图)
3. [执行方案](#3-执行方案)
   - [子阶段 A：事件总线 & 认知链路打通（Week 1-2）](#a-事件总线--认知链路打通)
   - [子阶段 B：存储统一 & 旧表归档（Week 2-3）](#b-存储统一--旧表归档)
   - [子阶段 C：测试安全网 & 废弃代码清理（Week 3）](#c-测试安全网--废弃代码清理)
   - [子阶段 D：前端集成 & 可观测性（Week 4）](#d-前端集成--可观测性)
4. [风险矩阵](#4-风险矩阵)
5. [验收标准](#5-验收标准)

---

## 1. 深度审计发现

### 1.1 最严重：两个 EventBus 共存，handler 全是空壳

| 文件 | EventBus 来源 | 角色 |
|------|:-------------:|:----:|
| `backend/app/application/di.py` | `from infra.event_bus import EventBus` → **新 bus** | 注册 15 个 handler |
| `backend/app/api/practice.py` | `container.event_bus` → **新 bus** | 发布 AnswerSubmitted / SessionCompleted |
| `backend/app/api/conversation.py` | `container.event_bus` → **新 bus** | 发布 AssistantReplied / AudioSynthesized / ImageRendered |
| `backend/domain/knowledge/service.py` | **新 bus** 订阅者 | `on_answer_submitted` = `pass` 🚫 |
| `backend/domain/analytics/service.py` | **新 bus** 订阅者 | `on_answer_submitted` 写数据库 ✅ |
| `backend/domain/habits/service.py` | **新 bus** 订阅者 | `on_answer_submitted` = `pass` 🚫 |
| `backend/domain/multimedia/service.py` | **新 bus** 订阅者 | `on_assistant_replied` 有实现 ✅ |
| `backend/app/domain/secretary/engines/secretary_event_handler.py` | `from app.infra.event_bus import EventBus` → **旧 bus** | `subscribe()` **从未被调用** 🚫 |

**结论**：
- events 确实发布到新 bus
- 但 3 个关键 handler（knowledge, habits, secretary）是空壳或未注册
- CognitiveNode **完全不在事件链中**

### 1.2 双存储分叉（读写路径混乱）

| 写路径 | 读路径 | 状态 |
|--------|--------|:----:|
| `knowledge_trace.py` → `data.knowledge_states` (JSON) | `learner_model.py` → `data.knowledge_states` | 🔴 旧 JSON，对应不上 cognitive_nodes |
| `practice.py` submit_answer → `bkt_engine.update()` | `partition_progress.py` → BOTH `cognitive_nodes` AND old `knowledge_states` | 🔴 双源不一致 |
| `domain/practice/service.py` → event → `_ks.save()` | — | 🟡 新路径有事件但无 cognitive 写入 |
| `cognitive/storage.py` CRUD 正常 | `api/phase8.py` 使用 cognitive_nodes | ✅ 但仅 Phase 8 在用 |

### 1.3 19 个 API 模块零测试覆盖

```
achievements, chat, content, conversation, knowledge, 
knowledge_graph, learning_events, material, multimodal,
partition_progress, phase8, practice, practice_analytics,
practice_errors, practice_quality, progress, search, secretary, study
→ 全部无专属测试文件
```

### 1.4 Service → API 层反转

```
services/conversation_llm.py → app.api.knowledge_graph  (违反分层)
services/conversation_llm.py → app.api.learning_events  (违反分层)
```

### 1.5 classify 无 embedding pipeline

`POST /api/v2/classify` — 前端传 `embedding` 为空 → 返回 `mode: 3`（不操作）。  
原因是 **前端没有 embedding 生成逻辑**，后端也未提供降级方案。

### 1.6 Secretary `subscribe()` 永远不调用

`secretary_event_handler.subscribe(bus)` 方法存在但 `di.py` 的 `_wire_events()` 和 `main.py` 的 `lifespan` 中均无此调用。

### 1.7 知识状态不写入 CognitiveNode

`learner_model.py` 更新 `knowledge_states`（旧 JSON），BKT 更新 `knowledge_states` 表（旧 PG 表），但 `cognitive_nodes` 的 `belief` 字段从未被更新。

---

## 2. 全局断裂地图

```
                           用户
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         练习页面        对话页面       Dashboard
              │             │             │
              ▼             ▼             ▼
      ┌────────────┐ ┌────────────┐ ┌────────────┐
      │ practice.py│ │conversation│ │ progress   │
      │ (REST)     │ │ (WS+REST)  │ │ (多种API)  │
      └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
             │              │              │
             ▼              ▼              │
      ┌────────────┐ ┌────────────┐        │
      │ BKT Engine │ │ LLM Engine │        │
      │ (旧)       │ │ (旧classi- │        │
      │            │ │ fier)      │        │
      └──────┬─────┘ └──────┬─────┘        │
             │              │              │
             ▼              ▼              ▼
      ┌────────────┐ ┌────────────┐ ┌────────────┐
      │knowledge_st│ │data.topics │ │BOTH:       │
      │ates(JSON)  │ │data.domains│ │cog_nodes   │
      │knowledge_st│ │(旧结构)    │ │+ knowledge_│
      │ates(PG)    │ │            │ │states(旧)  │
      └────────────┘ └────────────┘ └────────────┘
             │              │              │
             │       🔴 不互通 │             │
             ▼              ▼              ▼
      ┌─────────────────────────────────────────┐
      │         cognitive_nodes (Phase 6/8)     │
      │         数据源统一目标，但无人写入       │
      │     belief 始终为默认值 0.5             │
      └─────────────────────────────────────────┘
             ▲              ▲
             │     🔴 无事件联动    │
      ┌──────┴──────┐  ┌───────────┴──────┐
      │ event_bus   │  │  secretary       │
      │ (handler 空 │  │  (subscribe 死)   │
      │  壳)        │  │                   │
      └─────────────┘  └───────────────────┘
```

**核心断裂点编号**（共 7 个，按修复顺序）：

| # | 断裂 | 影响 | 优先级 |
|:-:|:-----|:----:|:------:|
| B1 | EventBus handler 是空壳或死注册 | 练习→认知、对话→认知、秘书响应 全线断裂 | **P0** |
| B2 | CognitiveNode belief 永不更新 | 知识图谱永远显示默认掌握度 | **P0** |
| B3 | 双存储分叉 | partition_progress 数据不一致 | **P0** |
| B4 | classify 无 embedding | 对话不归入知识树 | **P1** |
| B5 | 19 API 零测试覆盖 | 无安全网，改什么怕什么 | **P1** |
| B6 | Secretary subscribe 死代码 | 秘书离线 | **P1** |
| B7 | 前端→API 断层 | classify UI 缺失，秘书链路不通 | **P2** |

---

## 3. 执行方案

### A. 事件总线 & 认知链路打通（Week 1-2）

#### A.1 修复 EventBus handler 空壳（第 1-2 天）

**目标**：让 `KnowledgeGraphServiceImpl` 和 `HabitServiceImpl` 的 handler 真正干活。

**文件改动**：

| 文件 | 改动 | 工作量 |
|------|------|:------:|
| `backend/domain/knowledge/service.py` | `on_answer_submitted`: 调用 `cognitive/storage.py` 的 `sync_from_practice()` | 4h |
| `backend/domain/knowledge/service.py` | `on_error_recorded`: 更新 cognitive_nodes 的 `error_clusters` | 2h |
| `backend/domain/habits/service.py` | `on_answer_submitted`: 写入习惯数据到 `cognitive_nodes.subsystems.habits` | 2h |

**代码设计**：

```python
# domain/knowledge/service.py — on_answer_submitted 实现
async def on_answer_submitted(self, event: AnswerSubmitted) -> None:
    """答题事件 → 更新 cognitive_nodes 的 belief（Beta 分布后验）"""
    node = find_node_by_label(event.skill_id, event.user_id)
    if not node:
        logger.warning(f"No cognitive node for skill: {event.skill_id}")
        return
    
    # Beta 分布后验：alpha += correct_count, beta += incorrect_count
    new_alpha = node.belief.alpha + (1 if event.is_correct else 0)
    new_beta = node.belief.beta + (0 if event.is_correct else 1)
    node.belief.alpha = new_alpha
    node.belief.beta = new_beta
    node.belief.proficiency_mean = new_alpha / (new_alpha + new_beta)
    node.belief.proficiency_precision = new_alpha + new_beta
    node.belief.last_updated = time.time()
    
    # 更新 practice_summary
    node.practice_summary.total_attempts += 1
    node.practice_summary.correct_attempts += (1 if event.is_correct else 0)
    
    upsert_node(node, event.user_id)
```

**验证**：
```bash
# 做一道题
curl -X POST http://localhost:8000/api/practice/sessions/xxx/answer -d '...'
# 查 cognitive_nodes 表 belief 字段
psql -d edu_companion -c "SELECT id, belief->>'proficiency_mean' FROM cognitive_nodes WHERE label LIKE '%极限%';"
# → 期望: proficiency_mean 从 0.5 变化
```

#### A.2 注册 Secretary 到 EventBus（第 3 天）

**目标**：让 `secretary_event_handler.subscribe()` 真正被调用。

**文件改动**：

| 文件 | 改动 | 工作量 |
|------|------|:------:|
| `backend/app/main.py` lifespan | 调用 `secretary_event_handler.subscribe(container.event_bus)` | 1h |
| `backend/app/domain/secretary/engines/secretary_event_handler.py` | 将导入从 `app.infra.event_bus` 改为 `infra.event_bus`（与新 bus 对齐） | 1h |

**验证**：
```bash
# 连续答错 2 题
curl -X POST http://localhost:8000/api/practice/sessions/xxx/answer -d '{"answer":"错","...":...}'
# 查 Secretary 提案表
psql -d edu_companion -c "SELECT * FROM secretary_proposals ORDER BY created_at DESC LIMIT 5;"
# → 期望: 有新的诊断提案
```

#### A.3 添加 CognitiveNode 事件发布（第 4-5 天）

**目标**：CognitiveNode 变更时也发布事件，让其他模块感知。

**文件改动**：

| 文件 | 改动 | 工作量 |
|------|------|:------:|
| `backend/app/cognitive/storage.py` | `upsert_node()` 末尾发布 `CognitiveNodeUpdated` 事件 | 4h |
| `backend/app/shared/events.py` | 新增 `CognitiveNodeUpdated` 事件类型 | 1h |
| `backend/app/application/di.py` | 注册 `CognitiveNodeUpdated` 的订阅者 | 2h |
| `backend/app/services/zpd_scheduler.py` | 订阅 `CognitiveNodeUpdated` 重新计算 ZPD | 2h |

**验证**：
```bash
# 做一道题 → cognitive_nodes 更新
# → 触发 CognitiveNodeUpdated 事件
# → ZPD Scheduler 打印重新计算日志
tail -f backend/logs/app.log | grep "ZPD"
```

#### A.4 建立 embedding 降级 pipeline（第 6-7 天）

**目标**：classify 在无 embedding 时不返回 mode 3。

**文件改动**：

| 文件 | 改动 | 工作量 |
|------|------|:------:|
| `backend/app/services/phase8_classifier.py` | `classify()` 中 `embedding` 为空时降级为 LLM 关键词提取或 KEYWORD_WEIGHTS 匹配 | 4h |
| `backend/app/services/classifier.py` | 标记 `classify_partition` / `classify_full` 为 deprecated，转发到 phase8 | 1h |
| `backend/app/services/context_builder.py` | 切换到 phase8_classifier | 2h |

**验证**：
```bash
curl -X POST http://localhost:8000/api/v2/classify \
  -H "Content-Type: application/json" \
  -d '{"user_id":"default_user","text":"导数的定义是什么"}'
# → 期望 mode=1, candidates 包含 "高等数学.微积分.导数"
```

---

### B. 存储统一 & 旧表归档（Week 2-3）

#### B.1 CognitiveNode 成为知识状态唯一源（第 8-10 天）

**目标**：`learner_model.py` 和 `knowledge_trace.py` 从旧表切换到 CognitiveNode。

**文件改动**：

| 文件 | 改动 | 工作量 |
|------|------|:------:|
| `backend/app/core/learner_model.py` | `update_knowledge()` 先读 CognitiveNode，后写 CognitiveNode；旧 `knowledge_states` 只读不回写 | 1d |
| `backend/app/core/knowledge_trace.py` | BKT 更新后调用 `cognitive/storage.sync_from_practice()` | 1d |
| `backend/app/core/orchestrator.py` | `_build_context()` 从 CognitiveNode 读取掌握度替代 `profile.knowledge_states` | 4h |

**验证**：
```bash
# 做一套练习
# 查 partition_progress — 应该只从 cognitive_nodes 读取
curl http://localhost:8000/api/partition-progress?partition_id=数学
# → 数字应与 cognitive_nodes 的 belief 聚合结果一致
```

#### B.2 PartitionProgress 统一数据源（第 11-12 天）

**目标**：`_compute_partition_progress_legacy()` 废弃，只用 CognitiveNode。

**文件改动**：

| 文件 | 改动 | 工作量 |
|------|------|:------:|
| `backend/app/api/partition_progress.py` | `get_partition_progress()` 移除备降逻辑，只走 CognitiveNode 路径 | 1d |
| `backend/app/api/partition_progress.py` | 删除 `_compute_partition_progress_legacy()` 和所有 `_legacy_*` 函数 | 2h |

#### B.3 旧表只读标记（第 13 天）

| 文件 | 改动 | 工作量 |
|------|------|:------:|
| `backend/app/db/conversation_schema.sql` | 注释 `knowledge_states` 为「只读历史表，不再写入」 | 1h |
| `backend/app/core/learner_model.py` | 删掉向 `data.knowledge_states` 写入的代码 | 2h |

---

### C. 测试安全网 & 废弃代码清理（Week 3）

#### C.1 测试基础设施（第 14 天）

| 文件 | 内容 | 工作量 |
|------|------|:------:|
| `backend/tests/conftest.py` | pytest fixture：测试用 DB、FastAPI test client、mock EventBus | 1d |
| `backend/tests/factories.py` | 测试数据工厂（CognitiveNode、事件、节点树） | 4h |

#### C.2 核心模块测试（第 15-17 天）

| 测试文件 | 覆盖 | 用例数 | 工作量 |
|---------|------|:------:|:------:|
| `tests/test_cognitive_storage.py` | CRUD, sync_from_practice, vector_search, edge_ops | 10 | 1d |
| `tests/test_phase8_classifier.py` | classify 3 种模式, embedding 降级 | 6 | 4h |
| `tests/test_secretary_service.py` | 诊断生成, 提案创建, 事件响应 | 8 | 1d |
| `tests/test_growth_engine.py` | ensure_ancestors, 节点创建 | 5 | 4h |

#### C.3 废弃代码清理（第 18-19 天）

| 文件/函数 | 处理方式 | 工作量 |
|-----------|:--------:|:------:|
| `backend/app/services/classifier.py` 中的 `classify_partition` / `classify_full` | 标记 `@deprecated`, 转发到 phase8 | 2h |
| `backend/app/services/classifier.py` 中的 `KEYWORD_WEIGHTS` | 保留作为 phase8 降级源 | — |
| `backend/app/services/context_builder.py` 中的旧 classifier 调用 | 切换到 phase8_classifier | 2h |
| `backend/app/core/learner_model.py` 中的旧 `knowledge_states` 引用 | 清理 | 2h |
| `backend/app/infra/event_bus.py`（旧 bus） | 标记为 deprecated，与 `backend/infra/event_bus.py` 合并 | 4h |
| `backend/scripts/migrate_old_data.py` | 标记为 historical, 不删除 | 1h |

---

### D. 前端集成 & 可观测性（Week 4）

#### D.1 Classify 前端确认 UI（第 20-21 天）

| 组件 | 改动 | 工作量 |
|:-----|:-----|:------:|
| `ConversationPanel.tsx` | 分类结果卡片展示：模式 1/2/3 分类卡片（复用已有的 SwitchBanner 逻辑） | 1d |
| `ClassifyConfirmModal.tsx` (新) | 用户确认/选择知识归属的弹窗 | 1d |

#### D.2 Secretary 前端链路验证（第 22 天）

| 组件 | 改动 | 工作量 |
|:-----|:-----|:------:|
| `SecretarySuggestionsBlock.tsx` | 接入真实 API `/api/secretary/proposals` | 4h |
| `SecretaryBellBadge.tsx` | 轮询改为订阅式，验证红点逻辑 | 2h |

#### D.3 性能 & 可观测性（第 23-24 天）

| 任务 | 改动 | 工作量 |
|:-----|:-----|:------:|
| `storage.load()` 热点 | 改为按需加载（只加载指定 partition 的节点，不加载全量） | 1d |
| 请求追踪中间件 | 在 `main.py` 添加 `TraceMiddleware`（复用 `app/infra/tracing.py`） | 4h |
| DB 连接池监控 | 在 `healthz` 端点暴露连接池统计 | 2h |
| 密码硬编码 | `config.py` 中的 DB 密码从 `.env` 读取，移除 fallback | 1h |

#### D.4 Phase 9 全链路 E2E 测试（第 25-26 天）

| 测试场景 | 步骤 | 验证点 |
|:---------|:-----|:-------|
| 练习→认知同步 | 做 1 道题 → 查 CognitiveNode belief | belief 变化 |
| 秘书事件响应 | 连续答错 3 题 → 查 proposal 表 | 有新提案 |
| 对话 classify | 发"导数定义" → 查 classify API | mode=1, path 含导数 |
| 前端分类确认 | 收到 classify 结果 → 点击确认 → 查 link 表 | link 创建 |
| 旧表不再写入 | 做练习 → 查 old knowledge_states | 无新记录 |

---

## 4. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|:-----|:----:|:----:|:-----|
| `cognitive/storage.py` 的 `sync_from_practice` 导致性能下降 | 中 | 中 | 异步 fire-and-forget，不阻塞 submit_answer 返回 |
| 旧表不准删除 | 高 | 低 | 只做只读标记，不 DROP TABLE，设只读视图 |
| 前端兼容性破坏 | 低 | 高 | 所有 API 改动用 v2 前缀；旧 endpoint 保持兼容 |
| `secretary_event_handler` 导入路径修改导致循环依赖 | 中 | 中 | 先导入测试，确认无循环引用链 |
| `conftest.py` 需要真实 DB | 高 | 低 | 用 mock DB 或用测试专用 DB 连接 |

---

## 5. 验收标准

| # | 验收项 | 验证方法 | 阶段 |
|:-:|:-------|:---------|:----:|
| ✅-1 | 做 1 道练习 → CognitiveNode.belief.proficiency_mean 变化 | `psql` 查表 | A |
| ✅-2 | 连续答错 2 题 → Secretary 生成诊断提案 | API `/api/secretary/proposals` | A |
| ✅-3 | 发"导数的定义" → classify API 返回 mode=1 + path | `curl` 测试 | A |
| ✅-4 | PartitionProgress 只读 CognitiveNode, 不取旧表 | 代码审查 + 日志 | B |
| ✅-5 | 旧 `knowledge_states` 表停止写入新记录 | DB 监控 | B |
| ✅-6 | `cognitive/storage.py` CRUD 全部通过单元测试 | `pytest` | C |
| ✅-7 | `phase8_classifier` 3 种模式全部测试通过 | `pytest` | C |
| ✅-8 | 前端 classify 确认弹窗可交互 | 肉眼验证 | D |
| ✅-9 | 全链路 E2E 测试通过 | `python3 tests/test_e2e.py` | D |

---

## 附录：文件变更清单总表

| 阶段 | 文件 | 操作 | 风险等级 |
|:----:|:-----|:----:|:--------:|
| A | `backend/domain/knowledge/service.py` | 修改 | 🟡 |
| A | `backend/domain/habits/service.py` | 修改 | 🟢 |
| A | `backend/app/main.py` | 修改 | 🟡 |
| A | `backend/app/domain/secretary/engines/secretary_event_handler.py` | 修改 | 🟡 |
| A | `backend/app/cognitive/storage.py` | 修改 | 🔴 |
| A | `backend/app/shared/events.py` | 修改 | 🟢 |
| A | `backend/app/application/di.py` | 修改 | 🟡 |
| A | `backend/app/services/phase8_classifier.py` | 修改 | 🟡 |
| A | `backend/app/services/context_builder.py` | 修改 | 🟡 |
| B | `backend/app/core/learner_model.py` | 修改 | 🔴 |
| B | `backend/app/core/knowledge_trace.py` | 修改 | 🔴 |
| B | `backend/app/core/orchestrator.py` | 修改 | 🟡 |
| B | `backend/app/api/partition_progress.py` | 修改 | 🟡 |
| C | `backend/tests/conftest.py` | 新建 | 🟢 |
| C | `backend/tests/factories.py` | 新建 | 🟢 |
| C | `backend/tests/test_cognitive_storage.py` | 新建 | 🟢 |
| C | `backend/tests/test_phase8_classifier.py` | 新建 | 🟢 |
| C | `backend/tests/test_secretary_service.py` | 新建 | 🟢 |
| C | `backend/tests/test_growth_engine.py` | 新建 | 🟢 |
| D | `frontend/src/components/conversation/ConversationPanel.tsx` | 修改 | 🟡 |
| D | `frontend/src/components/conversation/SecretarySuggestionsBlock.tsx` | 修改 | 🟡 |
| D | `frontend/src/components/conversation/ClassifyConfirmModal.tsx` | 新建 | 🟡 |
| D | `backend/app/main.py` | 修改（tracing） | 🟢 |
| D | `backend/tests/test_e2e.py` | 修改 | 🟢 |

---

> **文档状态**: 初始方案  
> **待用户确认**: 阶段划分、优先级顺序、风险偏好
