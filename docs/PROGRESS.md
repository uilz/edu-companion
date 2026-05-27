# 智能伴学系统 — 项目进度

> 最后更新: 2026-05-26 (Phase 16 S14-S17 完成)

---

## 总体进度

```
Phase 1 MVP:   █████████████████████  完成
Phase 2 画像:  █████████████████████  完成
Phase 3 路由:  █████████████████████  完成
Phase 4 对话:  █████████████████████  完成
Phase 5 事件:  █████████████████████  完成
Phase 6 认知:  █████████████████████  完成
Phase 7 秘书:  █████████████████████  完成 ✅
Phase 8 图谱:  █████████████████████  完成 ✅
Phase 9 同步:  █████████████████████  完成 ✅
Phase 10 调度: █████████████████████  完成 ✅
Phase 11 填充: █████████████████████  完成 ✅
Phase 12 看板: █████████████████████  完成 ✅
Phase 13 讲解: █████████████████████  完成 ✅
Phase 14 心智: █████████████████████  完成 ✅
Phase 15 多模态:█████████████████████  完成 ✅
Phase 16 整合: █████████████████████  完成 ✅
```

---

## Phase 14 · 伴学心智系统（行为分析 + 心理陪伴 + 习惯养成 + 创造扩展）

| 模块 | 状态 | 说明 |
|------|:----:|------|
| 情感分析 API | ✅ | `POST /api/v2/emotion/analyze` + `GET /api/v2/emotion/trend/{user_id}` |
| 情感对话集成 | ✅ | `context_builder.py` 自动注入情绪上下文，`conversation_llm.py` 自动分类 |
| 情绪看板前端 | ✅ | `EmotionCard.tsx` — 情绪标签 + 平衡条 + 最近记录 |
| 智能创造扩展 | ✅ | `knowledge_expander.py` — 知识拓展/变式题/关联发现 |
| 创造扩展 API | ✅ | `POST /api/v2/expand/knowledge/variant/discover` |
| 创造扩展前端 | ✅ | `ExpandPanel.tsx` — 拓展面板 + 变式题交互 |
| habits 空壳填充 | ✅ | `domain/habits/service.py` 事件驱动完整实现 |
| analytics 空壳填充 | ✅ | `domain/analytics/service.py` 行为分析完整实现 |

---

## Phase 15 · 多模态输入 + 图谱可视化

| 模块 | 状态 | 说明 |
|------|:----:|------|
| 视觉理解 API | ✅ | `POST /api/v2/vision/{ocr,understand-problem,analyze,chat-image}` |
| 视觉理解服务 | ✅ | `vision_service.py` — LiteLLM 视觉模型 OCR + 拍题理解 + 通用分析 |
| 对话图片上传 | ✅ | `ChatInput.tsx` 已有完整图片上传流程（File → FormData → workspace/upload） |
| 图谱独立路由页 | ✅ | `/graph` 路由 + 全屏力导向布局（基于现有 GraphTab 644行） |
| 48h 临时对话清理 | ✅ | `scripts/cleanup_temp_convs.py` + 每日午夜 cron |
| Classify 确认 UI | ✅ | `ClassifyConfirmPopover.tsx` — 浮窗确认/搜索/8s 自动隐藏 |

---

## Phase 16 · 系统整合与质量提升 (全部完成 ✅)

| S | 模块 | 状态 | 说明 |
|:-:|------|:----:|------|
| S1 | DB 迁移链修复 | ✅ | `database.py` → `conversation_schema.sql` → `cognitive_schema.sql` 链式执行保障 |
| S2 | 事件总线统一 | ✅ | 移除重复的 in-memory bus，统一使用 `infra/event_bus.py` |
| S3 | Cognitive 管线精简 | ✅ | 事件处理去重，ZPD 调度与 TargetSelector 合并 |
| S4 | 后端债务清理 | ✅ | 移除废弃 renderers，API 响应统一，`domain/practice/service.py` 空壳 stubs 清理 |
| S5 | 前端债务清理 | ✅ | `useRenderedContent.ts`, `dashboard` 页加载顺序优化 |
| S6 | `default_user` 硬编码替换 | ✅ | ~100 处 → `DEFAULT_USER_ID` 常量，36 文件，165 tests 通 |
| S7 | `progress.py` 切换 cognitive_nodes | ✅ | `get_progress`/`get_stats`/`get_profile` 数据源从 `learner_engine` 切到 `cognitive_nodes` 表 |
| S8a | `AnalyticsTab.tsx` 拆分 | ✅ | 1083→353 行，拆为 6 子模块（utils/TrendChart/HeatmapGrid/HabitTab/RetentionPanel/DailySummaryCard） |
| S8b | `useConversation.ts` 拆分 | ✅ | 954→808 行，拆为 3 文件（ws.ts/api.ts/useMediaQuery.ts） |
| S9 | `@/types` 路径解析 | ✅ | 验证通过，所有 10 处 `@/types` 导入正确解析 |
| S10 | 修复 broken imports | ✅ | `shared/protocols/__init__.py` 中 `shared.schemas.*` → `app.schemas.*` |
| S11 | 清理 duplicate 表定义 | ✅ | `migrate_materials.py` 标记为 DEPRECATED (no-op)，`database.py` 为 canonical 源 |
| S12 | 同步 secretary_schema.sql | ✅ | SQL 参考文件更新为匹配 `secretary.py` 的 inline schema |
| S13 | 标记废弃迁移脚本 | ✅ | `migrate_to_cognitive.py` 添加 `DEPRECATED` 头 |
| S14 | 修复 TODO stubs | ✅ | `domain/practice/service.py` 3 个 TODO 填充实现（generate_questions/get_stats/get_behavior_report） |
| S15 | 合并 duplicate KnowledgeState | ✅ | `learner.py` 的 `KnowledgeState` 改为 re-export `practice.py` 多维版 |
| S16 | 清理死目录 | ✅ | 移除 `app/domain/data/` 空壳目录 |
| S17 | 修复重叠路由 | ✅ | `practice_quality.py` `/{question_id}` → `/quality/detail/{question_id}`，同步前端 2 文件 |

---

## Phase 8 · 知识图谱树 + 分类器 + 融合会话

| 模块 | 状态 | 说明 |
|------|:----:|------|
| 知识图谱数据迁移 | ✅ | 10节点从旧 JSON 迁至 cognitive_nodes 表 |
| DB 列迁移 (path_id/node_type/is_visible) | ✅ | 与 Phase 6 老字段共存 |
| 序列化修复 | ✅ | path_id/node_type 不再双序列化 |
| WebSocket asyncio 补丁 | ✅ | conversation.py 缺 import asyncio |
| Phase8Sidebar 替换 PartitionSidebar | ✅ | 知识图谱树 + 会话混合展示，替代旧的 partition→domain→topic 硬编码 |
| Classify 自动归类 | ✅ | 发消息时 fire-and-forget /api/v2/classify |
| 旧代码清理 | ✅ | PartitionSidebar.tsx (705 行) 删除 |
| 蓝线闪现修复 | ✅ | 非会话节点不设 borderLeft |
| 后端 API 健康 | ✅ | Phase 8 API 正常返回图节点 |
| 远端部署 | ✅ | 双 VM 构建 → 部署 → 验证通过 |

<!-- 所有遗留待办已在 Phase 15 解决 -->

---

## Phase 7 · 秘书系统 (Secretary) ✅

| 模块 | 状态 | 说明 |
|------|:----:|------|
| 诊断引擎 DiagnosisEngine | ✅ | 薄弱点检测、错误模式分类、趋势分析 |
| 提案生成器 ProposalGenerator | ✅ | 模板优先 + LLM 润色，多选项协商式提案 |
| 策略引擎 PolicyEngine | ✅ | 勿扰时段 / 去重 / 每日上限 / 关系记忆 |
| 事件总线集成 | ✅ | 订阅 AnswerSubmitted/SessionCompleted/KnowledgeStateUpdated |
| 模块扩展框架 | ✅ | 7 个内置模块（复习/疲劳/简报/备考/回归/元认知/静默） |
| 冷启动引导 | ✅ | 3 步学习风格探测对话 |
| 隐私合规 | ✅ | 全数据导出 + 遗忘权删除 |
| 前端秘书主页 | ✅ | 实时快照、待处理提案、设置页 |
| SecretaryBellBadge | ✅ | 导航栏铃铛红点，60s 轮询 |
| SecretarySuggestionsBlock | ✅ | 对话内嵌提案卡片，支持采纳/忽略 |
| 后端系统 | ✅ | 9 模块 + 18 路由 + 主动检查 |

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

## 旧文档归档

```
docs/
├── architecture-v3.md    ← 系统架构设计 v3
├── PROGRESS.md           ← 本文件
├── README.md             ← 文档总入口
├── phase1/               ← MVP 设计 (已归档)
├── phase2/               ← 学习画像设计 (已归档)
├── phase3/               ← 智能路由设计 (已归档)
├── phase4/               ← 对话系统设计 (已归档)
├── phase5/               ← 认知事件设计 (已归档)
├── phase6/               ← CognitiveNode 设计 (已归档)
├── phase7/               ← 秘书系统设计 (已归档)
└── phase8/               ← 知识图谱树+分类器设计 (已归档)
```

> 除 `architecture-v3.md`、`PROGRESS.md` 和 `README.md` 外，所有旧设计文档已按 Phase 归档。
