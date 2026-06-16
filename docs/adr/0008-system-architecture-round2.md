# ADR 0008: 系统架构全景 (Round 2 起点)

> 生成日期: 2026-06-14 | 状态: Draft — 理解文档, 非最终决策
> 用途: Round 2 优化重构前完整摸底, 识别重构信号
> Round 1 已完成: ADR 0001-0006 (认证隔离/数据隔离/WS代理/事件表/目录节点/Store简化)

---

## 1. 数据存储全景

### 1.1 PostgreSQL 表

| 表 | 用途 | 关键字段 | 所属模块 |
|----|------|----------|----------|
| `conversation_user_meta` | 统一 JSONB 存储: 目录节点/消息/文件/秘书偏好 | `user_id` PK, `data` JSONB | conversation |
| `cognitive_nodes` | 认知节点, 每行一个知识点, 20+ 子系统全在 JSONB | `id`+`user_id` PK, `level`, `activation`/`belief`/`trend`/... JSONB | cognitive |
| `events` | 通用事件记录 (取代 cognitive_events) | `id` PK, `event_type`, `source_type`, `payload` JSONB, `updated_ats`[] | events |
| `knowledge_edges` | 知识图谱边 | `source_node_id`, `target_node_id`, `edge_type`, `strength` | cognitive |
| `conversation_node_links` | 会话-节点关联 | `conversation_id`, `node_id`, `is_primary` | conversation |
| `questions` | 题库 | `question_id` PK, `skill_id`, `content` JSONB, `bloom_level`, `difficulty` | practice |
| `practice_sessions` | 练习会话 | `session_id` PK, `user_id`, `planned_skills` JSONB, `status` | practice |
| `practice_attempts` | 答题记录 | `id` PK, `user_id`, `question_id`, `is_correct`, `response_time_ms` | practice |
| `error_book` | 错题本 | `id` PK, `user_id`, `question_id`, `resolved` | practice |
| `materials` | 资料索引 | `material_id` PK, `user_id`, `file_name`, `status`, `storage_path` | files |
| `material_chunks` | 资料分块 (含向量) | `chunk_id` PK, `user_id`, `material_id`, `text`, `embedding`[] | files |
| `material_toc` | 资料目录树 | `toc_id` PK, `material_id`, `heading`, `level` | files |
| `secretary_proposals` | 秘书提案 | `id` PK, `user_id`, `module_id`, `status`, `content` JSONB | secretary |
| `user_notes` | 笔记 | `id` PK, `user_id`, `node_id`, `type`, `content` | learning |
| `learning_goals` | 学习目标 | `id` PK, `user_id`, `title`, `deadline`, `status` | learning |
| `exploration_projects` | 探索项目 | `id` PK, `user_id`, `topic`, `status` | learning |
| `plan_task_completions` | 计划任务完成 | `id` PK, `user_id`, `task_id`, `completed_at` | learning |
| `login_events` | 登录事件追踪 | `user_id`, `ip_address`, `device_type`, `login_time` | auth |
| `user_llm_configs` | 用户自定义 LLM 配置 | `user_id` PK, `api_key` (加密), `api_base`, `model` | auth |

### 1.2 Redis

用途: 秘书系统临时状态存储 (黑板模式)
键格式: `bb:secretary:{session_id}`
TTL: 300s

### 1.3 内存状态

- `EventBus._handlers`: 事件订阅器映射 (异步内存总线)
- `LearnerModel`: 用户学习画像顶层模型 (shared/learner_model.py)
- `DataRepository (storage)`: 对话/目录/消息数据内存缓存 (services/common/storage.py)
- `ToolRepository._tools`: LLM 工具注册表 (infrastructure/llm/tool_repository.py)
- `CognitiveOperationRegistry._operations`: 认知操作注册表 (domain/cognitive/operation_registry.py)
- `ModuleRegistry._modules`: 秘书模块注册表 (domain/secretary/engines/module_registry.py)

### 1.4 数据流路径

```
前端 API 调用
  → api/ 路由层 (请求验证/响应序列化)
    → domain/ 领域服务 (业务规则/领域模型)
      → services/ 应用服务 (用例编排/外部调用)
        → infrastructure/db/ 仓储 (SQL/JSONB)
          → PostgreSQL
```

事件驱动路径:
```
domain/service 业务操作
  → EventBus.publish(event)
    → 多个 handler 并行 (analytics/habits/knowledge/conversation)
      → 各自更新 DB 或触发下游
```

---

## 2. 后端模块职责与接口

### 2.1 模块分层

```
api/     (表示层: HTTP 路由, WS, SSE)
   ↓
domain/  (领域层: 业务规则, 领域模型)
   ↓
services/ (应用层: 服务实现, 用例编排)
   ↓
infrastructure/ (基础设施: DB/LLM/Media 适配)
   |
shared/ (无依赖: Protocol 接口, 事件定义, 常量)
```

### 2.2 各模块详情

#### 2.2.1 对话模块 (conversation)

**职责**: 对话树 CRUD + 流式 AI 回复 + 子分支 + 消息管理

**文件组织**:
```
api/conversation/
  ├── conversation.py      # 路由 (目录树 CRUD)
  ├── conversation_routes.py # 路由 (SSE 流式回复)
  └── stream_sse.py        # SSE 连接管理

domain/conversation/
  ├── service.py            # ConversationServiceImpl (协议实现)
  ├── reply_pipeline.py     # 回复管线 (7阶段深模块)
  ├── llm.py                # LLM 对话核心 (消息构造/工具调度)
  ├── conversation_processor.py # 对话处理 (存消息/组织)
  ├── tree_store.py         # 目录树操作的读写锁
  └── sync_hook.py          # 同步钩子 (文件→目录关联)

services/conversation/
  ├── context_pipeline.py   # 上下文管线 (6个 Provider)
  ├── context_builder.py    # 上下文构建 (旧, 向管线迁移中)
  ├── message_repository.py # 消息仓储
  ├── branch_summarizer.py  # 分支摘要
  ├── context_trigger.py    # 主动上下文触发
  ├── active_stream.py      # 活跃流管理
  └── token_buffer.py       # Token 缓冲区 (SSE 替代 WS)
```

**暴露接口** (Protocol: `shared/protocols/conversation.py`):
- `send_message()` → LLM 回复
- `send_and_reply_stream()` → SSE 流式回复
- `inject_practice_context()` → 练习上下文注入
- 事件监听: `on_session_completed()`, `on_knowledge_updated()`

**使用其他模块**: LLMService, PracticeService, DataRepository, CognitiveSync

**数据存储**: `conversation_user_meta` (JSONB), `events` (操作事件化)

#### 2.2.2 认知引擎 (cognitive)

**职责**: CognitiveNode CRUD + 子系统更新 + 事件化认知操作

**文件组织**:
```
domain/cognitive/
  ├── models.py             # CognitiveNode + 20+ 子系统 Pydantic 模型
  ├── operation_registry.py # CognitiveOperationRegistry (装饰器注册)
  ├── writer.py             # 认知节点写入 (子系统原子更新)
  ├── growth_engine.py      # 成长引擎 (ZPD 推进)
  ├── events.py             # 认知事件处理器
  ├── constants.py          # 认知常量
  ├── edge_models.py        # 边模型
  ├── memory_repository.py  # 记忆仓储接口
  └── operations/
      ├── belief_operations.py  # 贝叶斯信念操作
      └── trend_operations.py   # 趋势操作

infrastructure/db/
  ├── cognitive_repository.py    # PgCognitiveNodeRepository
  ├── cognitive_storage.py       # 认知存储 (旧, 向 repo 迁移)
  ├── cognitive_edge_storage.py  # 边存储
  └── cognitive_link_storage.py  # 链接存储
```

**暴露接口**: `CognitiveOperationRegistry` (认知操作按名注册/派发)

**使用其他模块**: EventsRepository (事件记录)

**数据存储**: `cognitive_nodes` (主表), `knowledge_edges` (边), `events` (操作审计)

#### 2.2.3 练习模块 (practice)

**职责**: 题库管理 + 练习会话 + 错题本 + 自适应选题 + 考试模式 + 统计

**文件组织**:
```
api/practice/
  ├── practice.py              # 路由 (CRUD)
  ├── explain_cards.py         # 解释卡片路由
  ├── references.py            # 参考资料路由
  └── practice_routes/         # v7 重构路由
      ├── banks.py             # 题库
      ├── sessions.py          # 会话
      ├── generation.py        # AI 出题
      ├── errors.py            # 错题
      ├── stats.py             # 统计
      └── misc.py              # 杂项

domain/practice/
  ├── service.py               # PracticeServiceImpl (协议实现)
  └── __init__.py

services/practice/
  ├── practice_service.py          # 核心服务 (认知更新/答案校验)
  ├── practice_session.py          # 会话管理
  ├── session_repository.py        # 会话仓储
  ├── session_engine.py            # 会话引擎
  ├── practice_adaptive.py         # 自适应选题
  ├── adaptive_scorer.py           # 自适应评分
  ├── practice_question_gen.py     # AI 出题
  ├── question_formatter.py        # 题目格式化
  ├── practice_question_crud.py    # 题目 CRUD
  ├── practice_question_bank.py    # 题库管理
  ├── practice_error_book.py       # 错题本
  ├── practice_scheduler.py        # 复习调度
  ├── practice_exam.py             # 考试模式
  ├── practice_stats.py            # 统计
  ├── practice_recall.py           # 回顾
  ├── practice_conversation.py     # 对话内练习
  ├── practice_secretary_integration.py # 秘书联动
  ├── practice_integrator.py       # 综合集成
  └── practice_import/             # 题目导入
      ├── service.py
      └── parser.py
```

**暴露接口** (Protocol: `shared/protocols/practice.py`):
- `generate_questions()`, `create_session()`, `submit_answer()`
- `get_knowledge_state()`, `get_errors()`, `get_stats()`
- `update_cognitive_after_practice()`, `check_answer()`
- 事件发布: `AnswerSubmitted`, `ErrorRecorded`, `SessionCompleted`

**使用其他模块**: CognitiveRepository (掌握度更新), EventBus (事件发布), ConversationService (上下文注入)

**数据存储**: `questions`, `practice_sessions`, `practice_attempts`, `error_book`

#### 2.2.4 秘书模块 (secretary)

**职责**: 诊断引擎 + 提案生成 + 策略引擎 + 主动检查 + 事件消费 + LLM Agent

**文件组织**:
```
api/system/secretary.py      # 路由 (提案 CRUD + Agent SSE)

domain/secretary/
  ├── secretary_service.py   # SecretaryServiceImpl
  ├── analysis.py            # 学情分析
  ├── agent_llm.py           # Agent LLM 调用
  ├── models.py              # 秘书模型
  └── engines/
      ├── module_registry.py          # 模块注册表 (discover_builtin)
      ├── proposal_service.py         # 提案服务
      ├── diagnosis.py                # 诊断引擎
      ├── context_engine.py           # 上下文引擎
      ├── llm_proposal_generator.py   # LLM 提案生成
      ├── policy_engine.py            # 策略引擎
      ├── behavior_trigger.py         # 行为触发器
      ├── active_checker.py           # 主动检查器 (定时轮询)
      ├── secretary_event_handler.py  # 事件处理器
      ├── secretary_plan_bridge.py    # 规划桥接
      ├── return_user_detection.py    # 回访用户检测
      ├── meta_cognitive_prompt.py    # 元认知提示
      ├── builtin_daily_brief.py      # 内置: 日报模块
      ├── builtin_review.py           # 内置: 复习模块
      └── builtin_housekeeping.py     # 内置: 整理模块
  └── tools/
      ├── tool_registry.py            # 秘书工具注册
      ├── base.py                     # 工具基类
      ├── learning_tools.py           # 学习工具
      ├── practice_tools.py           # 练习工具
      ├── knowledge_tree_tools.py     # 知识树工具
      └── navigation_tools.py         # 导航工具

services/secretary/tool_handler.py  # 工具执行处理器
```

**暴露接口**: 提案 CRUD API, Agent SSE (流式回复)
**使用其他模块**: EventBus (事件订阅), PracticeService, ConversationService, KnowledgeQueryService
**数据存储**: `secretary_proposals`, `conversation_user_meta` (策略记忆), Redis 黑板

#### 2.2.5 知识图谱 (knowledge)

**职责**: 图谱 CRUD + 力导向布局 + AI 解释 + ZPD 调度 + 认知同步 + 树操作

**文件组织**:
```
api/knowledge/
  ├── knowledge.py          # 路由 (图谱/AI 解释)
  └── knowledge_routes.py   # 路由 (v2 图谱)

domain/knowledge/
  ├── prerequisites.py      # 前置条件检查
  └── checker.py            # 知识检查器

services/knowledge/
  ├── knowledge_graph_service.py # KnowledgeGraphServiceImpl
  ├── knowledge_query_service.py # KnowledgeQueryServiceImpl
  ├── knowledge_state.py     # 知识状态查询
  ├── tree_ops.py            # 树操作
  ├── tree_service.py        # 目录树服务
  ├── tree_directory.py      # 目录节点读写
  ├── tree_messages.py       # 树消息
  ├── tree_sub_branch.py     # 子分支
  ├── cognitive_queries.py   # 认知查询
  ├── cognitive_sync.py      # 认知同步 (对话→CognitiveNode)
  ├── knowledge_expander.py  # 知识展开
  └── zpd_scheduler.py       # ZPD 调度器
```

**暴露接口** (Protocol: `shared/protocols/knowledge_query.py`):
- `query_relevant_nodes()`, `get_path_context()`, `search_nodes()`

**使用其他模块**: CognitiveRepository, PracticeService (掌握度), EventBus

#### 2.2.6 分析模块 (analytics)

**职责**: 行为分析 + 情绪分析 + 习惯养成 + 成就系统 + 质量分析 + 适应性规划

**文件组织**:
```
services/analytics/
  ├── behavior_analyzer.py    # 学习行为分析
  ├── emotion_analyzer.py     # 情绪分析
  ├── habit_formation.py      # 习惯养成
  ├── achievement_service.py  # 成就服务 (查询)
  ├── achievement_engine.py   # 成就引擎
  ├── error_attribution.py    # 错因归因
  ├── learning_events.py      # 学习事件
  ├── meta_history.py         # 元历史
  ├── adaptive_planner.py     # 自适应规划
  ├── adaptive_selector.py    # 自适应选题
  ├── spaced_repetition.py    # 间隔重复
  └── quality_analyzer.py     # 质量分析
```

**暴露接口** (Protocol: `shared/protocols/__init__.py`):
- `compute_streak()`, `find_best_hours()`, `compute_regularity()`
- 事件监听: `on_answer_submitted()`

#### 2.2.7 LLM 基础设施 (infrastructure/llm)

**职责**: LLM 统一调用 + 工具发现/派发 + 提示词管理 + 嵌入

```
infrastructure/llm/
  ├── llm_core.py           # LLM 核心 (LiteLLM 封装)
  ├── llm_service.py        # LLM 服务 (模型路由/用户配置/重试)
  ├── tool_repository.py    # 工具仓库 (发现/注册/派发)
  ├── tool_dispatch.py      # 工具调度 (LLM→工具执行)
  ├── tool_executor.py      # 工具执行器
  ├── prompts.py            # 提示词模板
  ├── question_generator.py # 题目生成器
  └── embedding_engine.py   # 嵌入引擎

infrastructure/llm_client.py # 旧 LLM 客户端 (向 llm_core 迁移)
```

**注意**: `llm_core` 和 `llm_client` 并行存在, 功能重叠, Round 2 需统一.

#### 2.2.8 媒体/文件模块 (media/files)

**职责**: 文件上传索引 + 多模态搜索 + B站搜索 + 资料解析 + TOC 提取

```
infrastructure/media/
  ├── material_indexer.py   # 资料索引
  ├── material_parser.py    # 资料解析
  ├── material_search.py    # 资料搜索 (向量)
  ├── material_toc_extractor.py # 目录提取
  ├── material_common.py    # 公共函数
  ├── materials_meta.py     # 元数据管理
  ├── media_search.py       # 媒体搜索
  └── bilibili_search.py    # B站搜索

api/system/files_routes.py       # 文件路由 (旧, 聚合路由)
api/system/files_routes/          # 文件路由 (v2 拆分)
  ├── upload.py                   # 上传
  ├── manage.py                   # 管理
  └── browse.py                   # 浏览
```

#### 2.2.9 认证模块 (auth)

**职责**: JWT 验证 + 用户 LLM 配置 + 登录事件追踪

```
domain/auth/
  ├── middleware.py         # AuthMiddleware (JWT 解码)
  ├── dependencies.py       # FastAPI Depends (current_user_id)
  ├── service.py            # 认证服务
  ├── api.py                # 路由 (登录历史/设置)
  ├── settings_api.py       # LLM 配置路由
  ├── repository.py         # 用户仓库
  ├── user_llm_repo.py      # LLM 配置仓库
  ├── login_event_repo.py   # 登录事件仓库
  └── ua_parser.py          # UA 解析
```

**外部依赖**: Auth Gateway (:18001, 独立进程 + 独立 DB) — JWT 签发/WS 代理

#### 2.2.10 组织服务 (organization)

**职责**: 对话/目录/消息的摘要生成与自动整理

```
services/common/
  ├── organization_service.py  # 组织服务 (organize_message/conversation/directory)
  ├── organization_detector.py # 组织检测器 (定时扫描 events 表)
  └── summary_service.py       # 摘要服务
```

---

## 3. 前端模块全景

### 3.1 页面路由

```
/learn                    # 对话学习主页 (Sidebar + Chat + Graph)
/learn/graph              # 学习页内嵌图谱
/graph                    # 知识图谱独立页
/knowledge-tree           # 知识树页
/analytics                # 分析仪表盘
/practice                 # 练习首页
/practice/banks           # 题库列表
/practice/banks/[id]      # 题库详情
/practice/sessions/[id]   # 练习会话
/practice/history         # 练习历史
/practice/errors          # 错题本
/practice/generate        # AI 出题
/practice/review/[qid]    # 复习
/exam                     # 考试模式
/study                    # 学习规划
/focus                    # 专注模式
/secretary                # 秘书面板
/secretary/settings       # 秘书偏好设置
/emotion                  # 情绪仪表盘
/achievements             # 成就系统
/calendar                 # 学习日历
/files                    # 文件管理
/files/[material_id]      # 资料详情
/resources                # 资源页
/import                   # 数据导入
/quality                  # 质量管理
/settings                 # 设置
/login                    # 登录
```

### 3.2 Zustand Store

| Store | 文件 | 职责 |
|-------|------|------|
| `conversation-store` | `store/conversation/conversation-store.ts` | UI 状态协调器: 选中节点/导航/目录/消息代理 |
| `tree-store` | `store/conversation/tree-store.ts` | 目录树 + 知识图谱节点数据 + 展开状态 |
| `message-store` | `store/conversation/message-store.ts` | 消息节点 + 响应块 |
| `agent-store` | `store/agent/agent-store.ts` | Agent 对话状态 + 工具调用 |
| `explain-store` | `store/explain/explain-store.ts` | 解释卡片 |
| `notification-store` | `store/notification/notification-store.ts` | 秘书通知 |
| `pipeline/index` | `store/pipeline/` | SSE 流式管线 (SSESource → StreamPipeline → 消费) |

### 3.3 关键组件结构

```
components/conversation/
  ├── core/          # ConversationPanel, MessageList, ChatInput, StreamingControls
  ├── blocks/        # TextBlock, PracticeBlock, MarkdownRenderer, ResponseBlockRenderer
  ├── cards/         # KnowledgeExplainCard, SelectionCard, NoteCard
  ├── tree/          # SidebarTreeNode, DirPicker, TreeBreadcrumb, NodePathBreadcrumb
  ├── panels/        # StudySidebar, GraphPanel, FocusModePanel, MobileBottomSheet
  ├── banners/       # SwitchBanner, ErrorBanner, SocraticFollowUpBar
  ├── input/         # VoiceRecorder, ResourcePicker, TextSelectionToolbar
  └── media/         # SpeakButton, VideoEmbed

components/graph/
  ├── graphs/        # ForceGraph, DAGGraph, FocusGraph, MindMapGraph
  ├── panels/        # TreeChatPanel, NodeDetailPanel, NoteSidebar, FloatingNodeCard
  └── modals/        # ExplainModal, GoalSettingModal, AggregateNotesModal

components/notification/   # SecretaryInlineBanner, NotificationDropdown, NavBellBadge
components/practice/       # QuestionCard, HintPanel, ExplanationPanel, SessionTimer
components/dashboard/      # DashboardShell, NodeDetailCard
components/ui/             # Card, Skeleton, EmptyState, ConfirmDialog
```

### 3.4 API 客户端

```
lib/api/
  ├── api.ts             # 统一入口: apiFetch + token 刷新 + 401 处理
  ├── auth.ts            # 认证 API (登录/注册)
  ├── learning-api.ts    # 学习 API (笔记/目标/项目)
  ├── practice-api.ts    # 练习 API
  └── graph-api.ts       # 图谱 API
```

---

## 4. 部署架构

```
Nginx :8080 (统一入口)
  ├── /api/auth/*       → Auth Gateway :18001 (登录/注册/JWT)
  ├── /api/conversations/ws → Auth Gateway :18001 (WS 代理 + JWT 注入)
  ├── /api/*             → Backend :8000 (FastAPI 业务)
  ├── /avatars/*         → Auth Gateway :18001 (头像静态文件)
  └── /*                 → Next.js :3000 (SSR)
```

### 4.1 认证体系

```
JWT 生命周期:
  登录 → Auth Gateway 签发 HS256 JWT → 前端 localStorage
  → 每个请求 headers.Authorization: Bearer <token>
  → Backend AuthMiddleware 本地解码 (共享 JWT_SECRET, ~0.01ms, 不调网关)
  → 401 → 自动刷新 (POST /api/auth/refresh) → 重试原请求

WS 认证:
  前端 WebSocket → Auth Gateway :18001
  → Gateway 从 cookie 解析 JWT → 注入 user_id query 参数
  → 转发到 Backend :8000/ws → Backend 从 query 读取 user_id
```

---

## 5. 事件系统运行时

### 5.1 EventBus

```
发布: EventBus.publish(event)
  1. 根据 event.__class__.__name__ 查找 handler 列表
  2. 所有 handler 并行 asyncio.create_task
  3. 每个 handler 5s 超时 (asyncio.wait_for)
  4. 单个 handler 失败不影响其他
  5. 等待所有完成后返回

订阅链 (DI 容器 wiring):
  AnswerSubmitted → analytics_service.on_answer_submitted
                  → habit_service.on_answer_submitted
                  → knowledge_service.on_answer_submitted
  ErrorRecorded   → knowledge_service.on_error_recorded
                  → media_service.on_error_recorded
  SessionCompleted → conversation_service.on_session_completed
                   → planning_service.on_session_completed
  AssistantReplied → multimedia_service.generate_media (TTS/SVG)
  CognitiveNodeUpdated → planning_service + secretary_event_handler
```

### 5.2 Events 表持久化

```
event_service.subscribe_persist(event_bus)
  → 订阅所有 DomainEvent 类型
  → 每个事件写入 events 表 (event_type/source_type/payload/status)
  → events 表不用于 handler 间通信, 纯审计 + 组织检测器消费
```

### 5.3 组织检测器 (OrganizationDetector)

```
定时轮询 events 表:
  按 source_type=conversation 聚合:
    新增 ≥6 条 → 触发 organize_conversation
  按 source_type=directory 聚合:
    子节点变更 ≥3  → 触发 organize_directory
  处理后标记 events.status=done
```

---

## 6. 对话流运行时

```
用户输入 → SSE POST /api/conversations/stream
  1. auto_resolve: 解析意图, 路由方向
  2. add_message: 存用户消息到 DB
  3. predict_tools: 预判 LLM 工具调用
  4. LLM probe: 初次 LLM 调用 (工具选择)
  5. assemble context: 6 个 ContextProvider 构建上下文
     (TutorPersona → ConversationLocation → LearnerEmotion
      → LearnerCognition → LearningActivity → TutorCapability)
  6. stream generation: SSE 流式生成
  7. post-process + sync:
     - 存助手消息
     - organize_message (LLM 生成 text_summary)
     - 发布 CognitiveUpdateEvent
     - summary_dirty=True
```

---

## 7. 秘书模块运行时

```
主动检查环 (active_checker):
  定时 (默认 5min) 轮询:
    1. return_user_detection: 检查用户回访
    2. behavior_trigger: 检查阈值触发
    3. diagnosis: 运行诊断引擎
    4. policy_engine: 策略匹配
    5. llm_proposal_generator: LLM 生成提案
    6. 写入 secretary_proposals 表

事件驱动:
  CognitiveNodeUpdated → secretary_event_handler
    → 评估是否需要生成提案
    → 如有需要 → 写入 secretary_proposals

前端轮询:
  NotificationDropdown 定时 GET /api/secretary/proposals
  → 展示未读提案 → 用户采纳/忽略
  → 采纳 → ProposalAccepted 事件 → 执行 action
```

---

## 8. 代码统计与文件组织

| 目录 | 文件数 | 行数 | 说明 |
|------|--------|------|------|
| `backend/app/api/` | ~15 | ~2K | 路由层 |
| `backend/app/domain/` | ~50 | ~10K | 领域逻辑 |
| `backend/app/services/` | ~60 | ~12K | 应用服务 |
| `backend/app/infrastructure/` | ~40 | ~8K | 基础设施 |
| `backend/shared/` | ~15 | ~2K | 协议/事件/常量 |
| `frontend/src/app/` | ~30 | ~3K | 页面路由 |
| `frontend/src/components/` | ~120 | ~9K | UI 组件 |
| `frontend/src/store/` | ~20 | ~3K | 状态管理 |
| `frontend/src/lib/` | ~15 | ~2K | 工具/API |
| `auth-gateway/` | ~10 | ~1K | 认证网关 |

---

## 9. Round 2 重构信号 (待决策处理)

1. **llm_core vs llm_client 共存** → 需统一
2. **context_pipeline vs context_builder 共存** → 管线化未完成
3. **storage (内存) + pg_storage (SQL) 共存** → 双写策略待明确
4. **cognitive_storage + cognitive_repository + cognitive_edge_storage 三套 DB 访问共存** → 需收敛
5. **旧 Partition/Domain/Topic JSONB 字段未清理** → ADR 0005 已标记废弃
6. **events 表 payload JSONB 无 schema 校验** → 类型安全缺失
7. **Testing 覆盖率低** — 只有 notification 少量测试 + 少量 vitest
8. **秘书主动检查器硬编码 5min 间隔** → 可配置化缺失
9. **前端 graph-types.ts 类型定义过大** (~300 行) → 拆分
10. **Auth Gateway 仍标记为"设计方案"阶段** → 需落地
