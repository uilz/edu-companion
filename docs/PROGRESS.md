# 智能伴学系统 — 项目进度

> 最后更新: 2026-05-23 (模型路径修复 + gitignore + 文档清理)

---

## 总体进度

```
Phase 1 MVP:   █████████████████████  完成
Phase 2 画像:  █████████████████████  完成
Phase 3 路由:  █████████████████████  完成
Phase 4 对话:  █████████████████████  完成
Phase 5 事件:  █████████████████████  完成
Phase 6 认知:  █████████████████████  完成
Phase 7 秘书:  █░░░░░░░░░░░░░░░░░░░░  5%  ← 当前 (设计中)
```

---

## Phase 6 · 认知中枢数据模型 (CognitiveNode)

### 6.1 模型+方程+常量 ✅

| 交付物 | 文件 | 说明 |
|--------|------|------|
| CognitiveNode (31 列 JSONB) | `models.py` | 15 子系统全量化建模 |
| 22 个数学方程 | `equations.py` | 信念 Beta 分布 / ACT‑R 激活 / 遗忘衰减 / EWMA 趋势 / 统一调度 / 激励 / 疲劳 |
| 22 个全局参数 | `constants.py` | 全部可学习默认值 |

### 6.2 PG 存储+CRUD ✅

| 交付物 | 状态 |
|--------|:--:|
| `cognitive_nodes` 表 (31 列) | ✅ |
| `cognitive_events` 表 (8 列) | ✅ |
| `upsert_node()` / `get_node()` / `get_children()` / `get_subtree()` | ✅ |
| `delete_node()` (级联) / `search_nodes()` / `get_urgent_nodes()` | ✅ |
| `append_event()` / `get_unprocessed_events()` / `mark_event_processed()` | ✅ |

### 6.3 事件处理器+对话联动 ✅

| Step | 功能 | 状态 |
|:----:|------|:--:|
| 1-4 | 加载节点 / 信念更新 / 信度衰减 | ✅ |
| 5-7 | 激活计算 / 趋势更新 / 道路检测 | ✅ |
| 8-11 | 疲劳更新 / FP 检测 / 激励计算 / 自评校准 | ✅ |
| 12-15 | 目标对齐 / 组合传播 / 深度触发 / 对话写入 | ✅ |
| 16-18 | 存储 / 事件入库 / 返回摘要 | ✅ |
| — | `conversation_llm.py` 自动 `submit_dialogue_context` | ✅ 非流式+流式双路径 |

### 6.4 迁移+清理 ✅

| 内容 | 状态 |
|------|:--:|
| `migrate_to_cognitive.py` 迁移脚本 | ✅ BKT→Beta + 图谱层级 + 事件 |
| `partition_progress.py` 双源（CognitiveNode → 旧JSON） | ✅ |
| `knowledge_graph.py` 双源（CognitiveNode → BKT） | ✅ |
| `orchestrator.py` + `search.py` + `progress.py` CognitiveNode 支持 | ✅ |

### 6.5 PG 默认存储 ✅

| 内容 | 状态 |
|------|:--:|
| `USE_PG_STORAGE=true` 为默认 | ✅ (回滚: `USE_JSON_STORAGE=true`) |
| `pg_storage.py` v4 全字段持久化 | ✅ domains/topics/files/jobs/states/events |
| `default_user` JSON→PG 迁移 | ✅ (4 分区/2 对话/8 节点/3 领域/2 专题) |

### 全模块联动修复 ✅

| 断裂点 | 修复内容 | 状态 |
|--------|---------|:--:|
| 练习→CognitiveNode | `submit_practice()` 双写 | ✅ |
| 图谱→CognitiveNode | `_sync_graph_to_cognitive()` 三入口 | ✅ |
| ZPD 调度→CognitiveNode | `estimate_student_ability()` 优先读 | ✅ |
| 流式对话→CognitiveNode | `send_and_reply_stream` 追加联动 | ✅ |
| 知识 API→CognitiveNode | `_BKTKnowledgeAdapter` 主源 | ✅ |
| 学习计划→CognitiveNode | `study.py _Adapter` 主源 | ✅ |
| Agent→CognitiveNode | 通过 orchestrator 已实现 | ✅ |

---

## Phase 7 · 秘书系统 (Secretary) (设计中)

**目标**：基于 CognitiveNode 的数据洞察、提案协商与主动服务系统

| 模块 | 说明 | 优先级 |
|------|------|:------:|
| 知识总线 + 黑板 | 统一数据查询接口 + Redis 提案传递 | 🔴 P0 |
| 诊断引擎 | 薄弱点检测、错误模式分类、趋势分析 | 🔴 P0 |
| 提案生成器 | 模板优先+LLM润色，多选项协商式提案 | 🔴 P0 |
| 策略引擎 | 勿扰 / 去重 / 上限 / 优先级过滤 | 🔴 P0 |
| 情境引擎 | 意图预测、认知负荷估计、互动偏好学习 | 🟡 P1 |
| 扩展框架 | 复习提醒 / 疲劳管理 / 日简报 / 备考模式 / 冷启动引导 | 🟡 P1 |
| 前端秘书页 | 待处理建议、学习状态速览、偏好设置 | 🟡 P1 |
| 主动检查 | APScheduler 定时诊断 + WebSocket 推送 | 🟢 P2 |

---

## 旧文档归档

```
docs/
├── architecture-v3.md    ← 唯一最新设计文档
├── PROGRESS.md           ← 本文件
├── phase1/               ← MVP 设计 (已归档)
├── phase2/               ← 学习画像设计 (已归档)
├── phase3/               ← 智能路由设计 (已归档)
├── phase4/               ← 对话系统设计 (已归档)
├── phase5/               ← 认知事件设计 (已归档)
├── phase6/               ← CognitiveNode 设计 (已归档)
└── phase7/ (待建)        ← LearningTutor 设计
```

> 除 `architecture-v3.md` 和 `PROGRESS.md` 外，所有旧设计文档已按 Phase 归档。
