# Edu-Companion 当前系统架构 (v8.4.0)

> 生成日期: 2026-06-12 (债务清理完成: 2026-06-13)
> 用途: 重构优化前完整摸底

---

## 1. 项目全景

AI 驱动的个性化学习助手。用户通过对话式交互学习知识，系统跟踪认知状态、推荐练习、生成学习计划、提供学情分析。

**代码规模**: ~56K 行
- 后端: ~36K 行 (~208 文件)
- 前端: ~19K 行 (~185 文件)
- 认证网关: ~2K 行 (~15 文件, 设计方案阶段)

**部署方式**: Docker Compose (4 服务) 或裸机 (systemd user service)

---

## 2. 技术栈

### 2.1 后端

| 组件 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | 0.110+ |
| ASGI 服务器 | Uvicorn | - |
| 数据库 | PostgreSQL + pgvector | 14+/16 |
| 数据迁移 | Alembic (原生 SQL) | - |
| LLM 路由 | LiteLLM | - |
| LLM 提供商 | DeepSeek / OpenAI / 通义千问 / Anthropic | 100+ 模型 |
| 本地嵌入 | OpenVINO | - |
| 配置 | pydantic-settings + YAML | - |
| 认证 | JWT (HS256) + 本地解码 | - |
| 事件总线 | 自定义内存异步 EventBus | - |
| 加密 | Fernet (PBKDF2HMAC) | - |
| 缓存 | Redis (黑板模式) | - |
| TTS | Edge-TTS | - |
| 语音识别 | Whisper (via LiteLLM) | - |
| 结构化日志 | 自定义 JSON 日志 | - |

### 2.2 前端

| 组件 | 技术 | 版本 |
|------|------|------|
| 框架 | Next.js (App Router) | 14.2 |
| UI | React | 18.3 |
| 语言 | TypeScript (strict) | 5.7 |
| 样式 | Tailwind CSS | 3.4 |
| 状态管理 | Zustand | 5 |
| 图标 | lucide-react | - |
| 可视化 | D3.js | 7.9 |
| Markdown | react-markdown + remark-math + rehype-katex | - |
| 数学渲染 | KaTeX | - |
| 富文本安全 | DOMPurify | - |
| 测试 | Vitest + @testing-library/react + jsdom | - |

### 2.3 认证网关 (设计方案)

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| JWT | PyJWT (HS256) |
| 密码 | bcrypt |
| 数据库 | PostgreSQL (独立) |

---

## 3. 系统架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx :8080                           │
│  (统一网关: 路由分发 + WebSocket 代理)                       │
└────┬─────────────┬──────────────┬────────────────┬──────────┘
     │             │              │                │
     ▼             ▼              ▼                ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐
│ Auth GW  │ │ Backend  │ │ WS Proxy │ │   Next.js        │
│ :18001   │ │ :8000    │ │ :18001   │ │   :3000          │
│ (独立)   │ │ (FastAPI)│ │ (同Auth) │ │   (SSR)          │
└──────────┘ └────┬─────┘ └──────────┘ └──────────────────┘
                  │
          ┌───────┴────────┐
          ▼                 ▼
    ┌──────────┐     ┌──────────┐
    │PostgreSQL│     │  Redis   │
    │ (pg16)   │     │ (7-alpine)│
    └──────────┘     └──────────┘
          │
          ▼
    ┌──────────┐
    │ pgvector │
    │(向量检索) │
    └──────────┘

外部服务:
┌──────────┐ ┌──────────┐ ┌──────────┐
│ DeepSeek │ │ OpenAI   │ │ 阿里云   │
│ API      │ │ API      │ │ TTS      │
└──────────┘ └──────────┘ └──────────┘
```

---

## 4. 数据存储与模型

### 4.1 PostgreSQL 数据库表

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| **conversation_user_meta** | 统一 JSONB 存储：目录节点(取代原分区/领域/专题/对话)/消息节点/文件/秘书偏好 | `user_id` (PK), `data` (JSONB) |
| **cognitive_nodes** | 认知量子节点，每个知识点一行 | `user_id`+`node_id` (PK), `label`, `level`, `parent`, `path_id`, `subsystems` (JSONB) |
| **events** | 统一事件记录 (取代 cognitive_events) | `id`, `user_id`, `event_type`, `source_type`, `source_id`, `status`, `payload` (JSONB), `created_at`, `updated_ats` (TIMESTAMPTZ[]) |
| **knowledge_edges** | 知识图谱边 | `source_node_id`, `target_node_id`, `edge_type`, `strength`, `trust_score` |
| **conversation_node_links** | 会话-节点关联 | `conversation_id`, `node_id`, `is_primary` |
| **questions** | 题库 | `id`, `skill_id`, `content` (JSONB), `bloom_level`, `difficulty` |
| **practice_sessions** | 练习会话 | `id`, `user_id`, `status`, `planned_skills` (JSONB) |
| **practice_attempts** | 答题记录 | `id`, `user_id`, `question_id`, `is_correct`, `response_time_ms` |
| **error_book** | 错题本 | `id`, `user_id`, `question_id`, `resolved` |
| **materials** | 资料索引 | `id`, `title`, `url`, `source_type`, `user_id` |
| **material_chunks** | 资料分块 | `id`, `material_id`, `content`, `embedding` |
| **material_toc** | 资料目录 | `id`, `material_id`, `title`, `level`, `position` |
| **secretary_proposals** | 秘书提案 | `id`, `user_id`, `module_id`, `status`, `content` (JSONB) |
| **user_notes** | 笔记 | `id`, `user_id`, `node_id`, `type`, `content` |
| **learning_goals** | 学习目标 | `id`, `user_id`, `title`, `deadline`, `status` |
| **exploration_projects** | 探索项目 | `id`, `user_id`, `topic`, `status` |
| **plan_task_completions** | 计划任务完成 | `id`, `user_id`, `task_id`, `completed_at` |

### 4.2 Redis 黑板

- 用途: 秘书系统临时状态存储 (会话级)
- 键格式: `bb:secretary:{session_id}`
- TTL: 300 秒

### 4.3 CognitiveNode 子系统 (JSONB 存储)

每个 CognitiveNode 包含 20+ 子系统:

| 子系统 | 核心字段 | 用途 |
|--------|----------|------|
| `Activation` | `base_level`, `retrieval_prob`, `latency_ms` | ACT-R 激活理论 |
| `Belief` | `α`, `β`, `proficiency_mean`, `peak_proficiency` | 贝叶斯 Beta 分布信念 |
| `PracticeSummary` | `total_attempts`, `correct`, `recent_success_rate_7d` | 练习汇总 |
| `Trend` | `velocity_ewma`, `stagnation_days`, `direction` | 学习趋势 |
| `Scheduling` | `urgency`, `next_review`, `next_action_type` | 复习调度 |
| `ErrorClusters` | 错误模式聚类 | 错误分析 |
| `Metacognition` | `calibration_error`, `direction` | 元认知校准 |
| `Engagement` | `xp`, `streak` | 激励 |
| `CognitiveLoad` | `intrinsic`, `dynamic` | 认知负荷 |
| `DeepProcessing` | 任务模板+实例 | 深度思考 |
| `Composition` | chunk 化状态机 | 知识编译 |
| `Prerequisite`/`Unlock`/`Associate` | 图结构边 | 前置/解锁/关联 |

### 4.4 知识层级 (重构中)

认知层次 (CognitiveNode, 语义层, 独立于目录):
```
CognitiveNode: Partition → Domain → Topic → Concept → Atom
```
_CognitiveNode 的 level 独立于目录结构, 不受目录重构影响_

目录层次 (DirectoryNode, 存储层, 重构目标):
```
DirectoryNode(node_type=dir, kind=general) → DirectoryNode(node_type=dir) → ... → DirectoryNode(node_type=conv, kind=general|temp|practice|secretary) → MessageNode
```
- `node_type`: 结构 — `"dir"`(目录容器, 可挂子节点) | `"conv"`(会话, 末端)
- `kind`: 行为 — `"general"`(普通) | `"temp"`(临时目录/临时会话) | `"practice"`(练习) | `"secretary"`(秘书)
- `kind="temp"` 的 conv: 首条消息触发分类器, 确认后移入目标目录且 kind→general
_详见 ADR 0005: 自由目录节点结构 — 取消固定三级, 用户自建任意深度_

---

## 5. 模块功能设计与职责

### 5.1 后端模块

#### 5.1.1 API 路由层 (`app/api/`)

| 路由前缀 | 模块 | 职责 |
|----------|------|------|
| `/api/conversations` | conversation | 对话树 CRUD + SSE 流式 AI 回复 + 子分支 |
| `/api/study` | learning/study | 学习计划生成/进度/建议 |
| `/api/practice` | practice | 练习提交/会话管理/错题本 |
| `/api/practice-routes` | practice (v7) | 智能题库/自适应选題 |
| `/api/progress` | learning/progress | 学习进度/日历/摘要 |
| `/api/knowledge` | knowledge | 知识图谱力导向布局/AI 解释 |
| `/api/v2` | cognitive | 消息分类/Dashboard/图谱管理 |
| `/api/multimodal` | multimodal | TTS + Whisper 转写 |
| `/api/achievements` | achievements | 成就系统 |
| `/api/search` | search | 全站统一搜索 (4 源并行) |
| `/api/secretary` | secretary | 提案 CRUD + Agent 助手 SSE |
| `/api/learning` | learning_enhance | 笔记/目标/项目 CRUD |
| `/api/files` | files | 文件上传+索引 |
| `/api/auth` | auth | 登录历史/用户 LLM 配置 |
| `/api/data` | data | 学习数据管理 |
| `/health` | - | 健康检查 |

#### 5.1.2 领域层 (`app/domain/`)

| 模块 | 职责 | 关键文件 |
|------|------|----------|
| **conversation** | 回复 pipeline、树存储、同步钩子 | `domain/conversation/` |
| **secretary** | 诊断、提案生成、9 引擎模块 | `domain/secretary/engines/` |
| **knowledge** | 前置卡控、查询服务 | `domain/knowledge/` |
| **practice** | PracticeService impl | `domain/practice/` |
| **planning** | PlanningService impl | `domain/planning/` |
| **analytics** | AnalyticsService impl | `domain/analytics/` |
| **habits** | HabitService impl | `domain/habits/` |
| **auth** | JWT 中间件、依赖注入 | `domain/auth/` |
| **materials** | 资料系统 | `domain/materials/` |
| **multimedia** | TTS + SVG 渲染 | `domain/multimedia/` |

#### 5.1.3 服务层 (`app/services/`)

| 模块 | 职责 |
|------|------|
| **practice** | CognitiveNode 更新、统计、错题本、会话管理 |
| **conversation** | 流式生成、上下文构建、TokenBuffer、摘要 |
| **knowledge** | 树操作 (CRUD/子支/同步)、ZPD 调度器、命名 |
| **analytics** | 成就引擎、自适应计划、行为/情绪分析、间隔重复 |
| **llm** | LLM 核心、prompts、工具分发/执行、Embedding |
| **materials** | 资料解析、语义搜索、索引、TOC 提取 |
| **common** | 背景任务、分类器、事件服务、PG 存储、摘要 |

#### 5.1.4 认知引擎 (`app/cognitive/`)

| 文件 | 职责 |
|------|------|
| `models.py` | CognitiveNode 实体 + 20+ 子系统定义 |
| `storage.py` | PostgreSQL CRUD + 向量搜索 + 事件读写 |
| `pg_repository.py` | CognitiveNodeRepository Protocol 实现 |
| `memory_repository.py` | 内存 Fake 实现 (测试用) |
| `events.py` | 认知事件处理器 (18 步全链路, 重构目标: 迁移至统一 events 表 + CognitiveOperationRegistry) |
| `writer.py` | 统一写入器 (幂等创建) |
| `growth_engine.py` | 自动生长引擎: 祖祖先补全/横向扩展/波纹跨域 |
| `edge_models.py` | KnowledgeEdge 边模型 |
| `edge_storage.py` | 边存储层 + 信任度衰减 |
| `link_storage.py` | 会话-节点关联存储 |

#### 5.1.5 秘书引擎 (`app/domain/secretary/engines/`)

9 个内置模块:

| 模块 | 触发条件 | 功能 |
|------|----------|------|
| `builtin_daily_brief` | 每日首次 | 今日学习简报 |
| `builtin_fatigue_manager` | 学习超时 | 疲劳提醒+休息建议 |
| `builtin_review_reminder` | 间隔到期 | 艾宾浩斯复习提醒 |
| `builtin_lateral_expansion` | growth_engine 触发 | 横向扩展建议 |
| `builtin_temp_conv_cleanup` | 临时会话过期 | 清理临时对话 |
| `context_engine` | 实时 | 上下文感知推荐 |
| `diagnosis` | 用户请求 | 综合学习诊断 |
| `exam_mode` | 考试前 | 考前冲刺计划 |
| `llm_proposal_generator` | LLM 触发 | 通用 LLM 提案生成 |

#### 5.1.6 事件总线 (`infra/event_bus.py`)

- 异步内存 EventBus
- 16 种领域事件
- Handler 超时 5s

**领域事件清单**:

| 事件 | 发布时机 | 消费者 |
|------|----------|--------|
| `AnswerSubmitted` | 提交答案 | analytics, habits, knowledge |
| `ErrorRecorded` | 答错 | error_book, knowledge, media |
| `SessionCompleted` | 练习完成 | conversation, planning |
| `CognitiveNodeUpdated` | 认知节点更新 | planning, ZPD 调度器 |
| `AssistantReplied` | AI 回复完成 | multimedia (TTS) |
| `MessageClassified` | 消息分类确认 | 知识图谱生长 |
| `PracticeSubmitted` | 练习提交 | 多消费者 |
| `NodeCreated` | 知识点创建 | growth_engine |
| `ProposalAccepted` | 秘书提案采纳 | planning, 执行器 |

#### 5.1.7 共享协议 (`shared/protocols/`)

模块间契约 (`typing.Protocol`):

| Protocol | 方法数 | 用途 |
|----------|--------|------|
| `CognitiveNodeRepository` | 19 | 认知节点 CRUD |
| `SecretaryRepository` | ~8 | 提案 CRUD |
| `PracticeService` | ~25 | 练习全链路 |
| `ConversationService` | ~21 | 对话全链路 |
| `KnowledgeQueryService` | ~8 | 认知查询 |
| `DataRepository` | 3 | 数据加载/保存 |
| `AudioSynthesizer` | - | TTS |
| `ImageRenderer` | - | 概念图渲染 |
| `AchievementService` | - | 成就系统 |

### 5.2 前端模块

#### 5.2.1 页面路由

| 路由 | 功能 | 说明 |
|------|------|------|
| `/` → `/dashboard` | 驾驶舱 | redirect |
| `/login` | 登录 | 表单认证 |
| `/learn` | 学习空间 | 最核心页面, 对话式学习 |
| `/practice/**` | 练习系统 | history/banks/sessions/generate/review |
| `/knowledge-tree` | 知识树 | 独立知识树视图 |
| `/graph` | 图谱对话 | 知识图谱可视化 |
| `/analytics/**` | 学习分析 | 仪表盘 |
| `/secretary/**` | AI 秘书 | 提案管理 |
| `/settings/**` | 设置 | 含 data 管理 |
| `/resources` | 资源库 | - |
| `/files/[id]` | 文件详情 | - |
| `/focus` | 专注模式 | 全屏沉浸 |
| `/calendar` | 学习日历 | - |
| `/achievements` | 成就系统 | - |
| `/emotion` | 情绪追踪 | - |
| `/search` | 统一搜索 | - |

#### 5.2.2 状态管理

| Store | 技术 | 状态 | 说明 |
|-------|------|------|------|
| `useConversationStore` | Zustand 5 | 分区/领域/专题/对话/消息/SSE | actions 拆分到 `actions/` 目录 |
| `useNotificationStore` | Zustand 5 | 秘书通知 CRUD | 页面感知路由 |
| `useExplainStore` | Zustand 5 | 知识解释卡片 | 乐观更新 |
| `AgentStore` | 模块级单例 | Agent 对话 | 非 Zustand, 模块级 refs |

#### 5.2.3 API 层 (`src/lib/api/`)

| 文件 | 用途 |
|------|------|
| `api.ts` | 统一 API 客户端 (token 刷新 + 错误处理) |
| `auth.ts` | 认证 API (login/register/refresh) |
| `fetch-interceptor.ts` | 全局 fetch 拦截器 (自动附加 JWT) |
| `graph-api.ts` | 知识图谱 API |
| `practice-api.ts` | 练习系统 API |
| `learning-api.ts` | 学习 API |

#### 5.2.4 组件组织 (`src/components/`)

| 目录 | 内容 |
|------|------|
| `layout/` | AppShell, Sidebar, BottomNav, ClientProviders |
| `conversation/` | 对话系统 (core/blocks/banners/cards/hooks/input/media/panels/renderers/tree) |
| `practice/` | 练习系统 (panels/shared) |
| `graph/` | 知识图谱 (graphs/modals/panels/pages/nodes) |
| `notification/` | 通知系统 |
| `agent/` | AI Agent 浮动组件 |
| `secretary/` | 秘书系统 |
| `analytics/` | 雷达图等分析组件 |
| `ui/` | 通用 UI (Card/Skeleton/EmptyState/ErrorBoundary) |

---

## 6. 模块间接口

### 6.1 前端 → 后端

```
前端 (Next.js :3000) → Nginx :8080 → 后端 (FastAPI :8000)
         └→ Auth GW :18001 (仅 login/register)
```

- API 调用: `window.fetch` → `fetch-interceptor` 自动加 JWT → Nginx 路由
- SSE: `/api/conversations/stream/{cid}` 流式接收 AI 回复
- WebSocket: 经 Auth GW 代理 → Backend :8000

### 6.2 后端 → 外部服务

| 服务 | 协议 | 用途 |
|------|------|------|
| LiteLLM | HTTP | LLM 调用路由 (DeepSeek/OpenAI/...) |
| OpenVINO | 本地进程 | Embedding 推理 |
| Edge-TTS | HTTP | 文字转语音 |
| Redis | TCP | 黑板缓存 |
| PostgreSQL | TCP | 主存储 |

### 6.3 后端内部依赖

```
API 路由层 → Service 层 → Domain 层 → Infrastructure 层
                ↓                            ↓
           Shared Protocols           PostgreSQL/Redis
                ↓
         Cognitive 引擎
```

- 逆向依赖: 通过 `shared/protocols/` 接口注入, 具体实现在 `app/cognitive/` 和 `app/db/`
- DI 容器: `app/application/` 中唯一的装配点
- 事件: Domain 层发布 → EventBus → Service 层消费者

### 6.4 前端内部依赖

```
Page → Component → Store → API Layer → Backend
         ↓
    UI Components
```

- Store 直接调用 API 函数 (无 service 层)
- 组件通过 Zustand hooks 读取状态
- 流式 SSE: 组件内直接管理 EventSource

---

## 7. 文件组织框架

### 7.1 后端目录结构

```
backend/
├── app/
│   ├── api/                    # FastAPI 路由
│   │   ├── conversation/       # 对话 SSE
│   │   ├── knowledge/          # 知识图谱
│   │   ├── learning/           # 学习/进度/cognitive
│   │   ├── practice/           # 练习+v7 题库
│   │   └── system/             # 秘书/搜索/文件/成就/多模态
│   ├── application/            # DI 容器装配
│   ├── cognitive/              # 认知引擎(核心)
│   ├── config.py               # pydantic-settings
│   ├── db/                     # DB 连接+迁移+仓储
│   │   ├── database.py         # 连接池+建表
│   │   ├── repositories.py     # PG 仓储
│   │   └── *.sql              # Schema 定义
│   ├── domain/                 # 领域逻辑
│   │   ├── auth/               # JWT 中间件
│   │   ├── conversation/       # 回复 pipeline
│   │   ├── knowledge/          # 图谱查询
│   │   ├── practice/           # 练习 Service impl
│   │   ├── secretary/          # 秘书系统+9引擎
│   │   └── ...                 # habits/planning/analytics/media/materials
│   ├── infrastructure/         # 基础设施 (crypto, event_bus)
│   ├── main.py                 # FastAPI 入口
│   ├── middleware/             # 追踪中间件
│   ├── schemas/                # Pydantic 模型
│   ├── scripts/                # 迁移/测试脚本
│   └── services/               # 业务服务
│       ├── analytics/          # 成就/自适应/行为/情绪分析
│       ├── common/             # 分类/事件/存储/摘要
│       ├── conversation/       # 流式/上下文/摘要
│       ├── knowledge/          # 树操作/ZPD/命名
│       ├── llm/                # LLM 核心/prompts/tools
│       ├── materials/          # 资料解析/索引/搜索
│       └── practice/           # 练习/认知更新
├── shared/
│   └── protocols/              # 模块间接口契约
├── config/                     # .env 配置
├── config.yaml                 # 主配置文件
├── alembic/                    # 数据库迁移
├── infra/                      # 基础设施模块
├── tests/                      # 测试
└── scripts/                    # 独立脚本
```

### 7.2 前端目录结构

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router 页面 (~20 路由)
│   ├── components/
│   │   ├── layout/             # AppShell, Sidebar, BottomNav
│   │   ├── conversation/       # 对话子系统 (10+ 子目录)
│   │   ├── practice/           # 练习子系统
│   │   ├── graph/              # 知识图谱 (D3 力导向/DAG/思维导图)
│   │   ├── notification/       # 通知系统
│   │   ├── agent/              # AI Agent
│   │   ├── secretary/          # 秘书系统
│   │   ├── analytics/          # 分析组件
│   │   ├── auth/               # AuthGuard
│   │   ├── search/             # 全局搜索
│   │   └── ui/                 # 通用 UI
│   ├── store/                  # Zustand 状态管理
│   │   ├── conversation/       # 对话 store + actions
│   │   ├── notification/       # 通知 store
│   │   └── explain/            # 知识解释 store
│   ├── lib/
│   │   ├── api/                # API 客户端层
│   │   ├── types/              # 图谱类型
│   │   └── utils/              # 工具函数
│   ├── hooks/                  # 自定义 hooks
│   ├── contexts/               # React Context (Auth, Theme)
│   └── types/                  # 全局 TS 类型
├── public/                     # 静态资源
├── config/                     # 环境变量
└── scripts/                    # 构建脚本
```

### 7.3 认证网关 (设计方案)

```
auth-gateway/
├── CONTEXT.md                  # 架构设计文档
├── requirements.txt            # 依赖
└── venv/                       # Python venv
```

---

## 8. 技术方法

### 8.1 后端模式

| 模式 | 实现 |
|------|------|
| 分层架构 | API → Service → Domain → Infrastructure |
| 依赖注入 | 自定义 DI 容器 (`app/application/`) |
| 仓储模式 | Repository Protocol + PG/内存实现 |
| 事件驱动 | 异步内存 EventBus |
| 策略模式 | 秘书引擎模块注册表 |
| 协议编程 | `typing.Protocol` 接口契约 |
| 适配器模式 | pg_repository 适配 storage 模块 |
| 统一写入 | CognitiveNodeWriter 幂等创建 |
| 自动生长 | growth_engine (祖先补全/横向扩展/波纹跨域) |
| BKT 算法 | 贝叶斯知识追踪 (Beta 分布后验) |
| ACT-R 激活 | 基于频率/间隔的激活计算 |
| TokenBuffer | SSE 流式缓冲 |
| 健康检查 | DB 连通性 + 队列堆积 + 连接池统计 |

### 8.2 前端模式

| 模式 | 实现 |
|------|------|
| SSR | Next.js App Router |
| 状态管理 | Zustand (持久状态) + 模块级变量 (流式) |
| 乐观更新 | explain store 先更新本地 |
| SSE 流式 | EventSource + 模块级 refs 缓存 |
| 全局拦截器 | fetch-interceptor 自动附加 JWT |
| 设计令牌 | CSS 变量体系 + 5 套主题 |
| 响应式布局 | AppShell (桌面侧栏 / 移动底部导航) |
| 错误边界 | React ErrorBoundary |
| 路由保护 | AuthGuard 组件 |
| Action 拆分 | conversation store actions 独立目录 |

---

## 9. 运行时流程

### 9.1 核心对话流程

**临时会话 (kind=temp) 第一轮:**

```
1. 用户输入 → 前端 POST /api/conversations/tree/conversation/{id}/message
2. 对话是 kind=temp 且为首条消息 → 触发分类器:
   a. [A] 向量检索 CognitiveNode (参考树) → path_id + score
   b. [B] 向量检索 DirectoryNode (name/summary_short) → path + score
   c. 合并排序 → 返回候选列表
3. 用户确认候选路径:
   a. CognitiveNode 来源 → 沿 path_id 逐级创建 DirectoryNode(node_type=dir, kind=general)
   b. DirectoryNode 来源 → 已有路径直接复用
   c. 移动 conv 节点从 `dir(kind=temp)` 到目标节点下
   d. kind: temp → general
4. 后续同普通对话流程
```

**普通对话 (conv_type=normal):**

```
1. 用户输入 → 前端 POST /api/conversations/tree/conversation/{id}/message
2. FastAPI → conversation_processor.start_background_pipeline()
3. Pipeline:
   a. 构建上下文 (历史消息 + 知识图谱状态)
   b. LLM 生成回复 (LiteLLM 路由)
   c. 工具执行 (LLM 调用的 tools)
   d. 存储消息节点 (MessageNode + ResponseBlock)
   e. 发布 AssistantReplied 事件
4. SSE 流式推送到前端 (TokenBuffer)
5. 前端逐步渲染回复 (响应块分发)
6. AssistantReplied → multimedia 模块生成 TTS 等
```

### 9.2 练习流程

```
1. 用户提交答案 POST /api/practice/submit
2. PracticeService:
   a. 校验答案
   b. BKT 后验更新 Beta 分布 (Belief)
   c. 更新 PracticeSummary / Trend / Activation
   d. 发布 AnswerSubmitted 事件
3. 事件消费者:
   a. analytics: 更新成就/行为分析
   b. habits: 更新习惯数据
   c. knowledge: 更新图谱状态
4. 答错 → ErrorRecorded → 错题本 + 媒体推荐
```

### 9.3 认知事件处理 (18 步)

```
handle_practice_response:
1. 遗忘衰减
2. 证据融合 (BKT 后验)
3. 更新峰值
4. 更新衰减计数
5. 更新 PracticeSummary
6. EWMA 趋势
7. 计算停滞天数
8. 更新 Activation (ACT-R)
9. 更新 CognitiveLoad
10. 更新疲劳
11. 调度 (urgency/next_review)
12. 激励 (XP/streak)
13. 写库
14. 下降检测
15. 深度思考触发检查
16. 父节点聚合
17. 发布 CognitiveNodeUpdated
```

### 9.4 秘书系统流程

```
1. active_checker 定时轮询 (周期 ~5min)
2. module_registry 发现可触发模块
3. 各引擎模块生成 Proposal
4. ProposalStore 持久化到 secretary_proposals 表
5. 前端轮询或 WebSocket 接收通知
6. 用户查看/采纳/忽略/延后
7. 采纳 → proposal_action_handler 执行
8. → secretary_plan_bridge 调整学习计划
```

### 9.5 知识图谱生长流程

```
1. 对话消息 → 分类器 (embedding + 沉浸感知)
2. → 关联到对应 topic/atom (conversation_node_links)
3. 用户确认分类 → 发布 MessageClassified
4. → growth_engine:
   a. ensure_ancestors: 补全祖先节点
   b. suggest_lateral_expansion: 横向扩展建议
   c. ripple_cross_domain: 语义检索 + 边创建
5. → 前端图谱可视化更新
```

### 9.6 认证流程

```
1. 用户 login → 前端 POST /api/auth/login → Nginx → AuthGW :18001
2. AuthGW 验证密码 → 签发 JWT (access 24h + refresh 7d)
3. 前端存储到 localStorage → 后续请求自动附加
4. 后端 AuthMiddleware 本地解码 JWT (HS256, 共享 secret)
5. 路由级注入 user_id from request.state
6. 401 → 前端刷新 token / 重定向到 /login
```

---

## 10. 部署架构

### 10.1 Docker Compose (4 服务)

| 服务 | 镜像 | 端口 | 依赖 |
|------|------|------|------|
| postgres | pgvector/pg16:latest | 5432 | - |
| redis | redis:7-alpine | 6379 | - |
| backend | Dockerfile.backend (3.11-slim) | 8000 | postgres, redis |
| frontend | Dockerfile.frontend (node 20-alpine) | 3000 | backend |

### 10.2 裸机部署

```
Nginx :8080 (反向代理 + SSL 终止)
├── Auth GW :18001 (独立进程)
├── Backend :8000 (uvicorn 4 workers, systemd)
├── Frontend :3000 (Next.js standalone)
├── PostgreSQL :5432
└── Redis :6379
```

### 10.3 环境变量

| 变量 | 用途 |
|------|------|
| `JWT_SECRET` | JWT 签名密钥 (前后端共享) |
| `OPENAI_API_KEY` / `BASE` | LLM API |
| `DB_PASSWORD` | 数据库密码 |
| `APP_DEBUG` | 调试模式 |
| `ENCRYPTION_KEY` | Fernet 加密密钥 |
| `NEXT_PUBLIC_API_URL` | 前端 API base URL |

---

## 11. 关键数据通路

```
对话输入 → 分类 → 知识图谱关联 → 认知节点更新 → 练习推荐
  ↓                                              ↓
LLM 回复 ← 上下文构建 ← 知识图谱状态 ← 认知状态查询
  ↓
事件发布 → 多媒体/TTS/习惯/成就/调度
```

```
练习提交 → BKT 后验 → CognitiveNode 18步更新 → 调度复习
                      ↓
                  AnswerSubmitted 事件
                      ↓
           成就/习惯/知识图谱/自适应计划
```

---

## 12. 已知技术债务 (v7.1-integration-debt)

**已规划重构 (参见 ADR 0004, ADR 0005):**

- **统一 events 表**: ~~`cognitive_events` → 通用 `events` 表 (独立于 cognitive 模块), 含 Event 模型 + EventsRepository, 支持多 event_type, source 追溯~~ ✅ `events_schema.sql` + `events_repository.py` 已完成, 旧表已移除
- **CognitiveOperationRegistry**: ~~认知操作按名注册/派发, 类 ToolRepository 模式, discover() 扫描~~ ✅ `operation_registry.py` 已完成; `belief_operations.py` (2 操作) + `trend_operations.py` (1 操作); `events.py` 已集成 Registry
  - cognitive/storage.py + pg_repository.py: 旧 events CRUD 已删除, 由 EventsRepository 替代 ✅
  - cognitive_schema.sql: cognitive_events 已移除 ✅
- **自由目录结构**: ~~Partition/Domain/Topic → 统一 `DirectoryNode`~~ ✅ DirectoryNode 已全量部署；URL 路径化: `proposal-navigator.ts` `?node=`→`?node_id=`; `FocusModePanel.tsx` `?partition=&node=`→`?node_id=`; `KnowledgeTreePage.tsx` reader 统一；删除旧 `?p=&d=&t=&c=` 向后兼容代码
- **conv_type→kind**: ~~`conv_type` 改为 `kind`~~ ✅ `DirectoryNode.kind` 已部署 (`general|temp|practice|secretary`), conv 为末端节点; `normal`→`general` 迁移完成
- **MessageNode 解耦**: ~~TreeNode 改名 MessageNode, 删除 discussed_skill_ids, 关联事件化~~ ✅ TreeNode→MessageNode 重命名完成; `discussed_skill_ids` 字段已从模型+前端+存储删除; skill_ids 通过 SourceParser 类缓存传递, 事件化记录 via `SKILL_DISCUSSED`
- **分类器重构**: ~~仅在临时会话首条消息运行, 双路匹配 (CognitiveNode + DirectoryNode), 返回路径候选, 删除旧 keyword_weights 四级配置文件~~ ✅ reply_pipeline Stage1 已 gate temp-only；`classify_by_text` 死代码清理（旧 keyword 路径删除）；`_search_directory_nodes` 使用 directory_nodes
- **架构规范**: ~~`selected_node_id` + `active_conv_id` 简化 store~~ ✅ `conversation-store.ts`: `selectedNodeId + selectedNodeType` 两字段取代 6 个旧导航字段; `activeConversationId` 删除, conv 推断自 `selectedNodeType==="conv"` (ADR 0006)
- **组织工具**: ~~`OrganizationService` 三方法 + `OrganizationDetector`~~ ✅ `organization_service.py` + `organization_detector.py` 已实现; conv ≥ 6 条触发 LLM 摘要, dir ≥ 3 次合并子 conv; 每 10 秒轮询 events 表

**存量债务 (待清理):**

1. ~~**统一写入**: 对话/TreeNode 写入路径分散 (conversation_user_meta vs cognitive_nodes)~~ ✅ `cognitive_sync.py` 旧 JSONB 列引用已清理；`tree_directory.py` 联动创建 CognitiveNode；`tree_sync.py` 异步重试机制；`llm_core.py` `_find_active_conversation` 改用 directory_nodes
2. ~~**事件贯通**: 部分领域事件未被消费者正确处理~~ ✅ PracticeSubmitted/NodeCreated 发布修复；MaterialIndexed 死代码移除；PendingCrossTopic 注册；KnowledgeStateUpdated 标记弃用
3. ~~**性能**: SSE TokenBuffer 不稳定的情况~~ ✅ 事件限界 (500) + 自动清理 + 前端 rAF 节流
4. ~~**协议覆盖**: 部分模块间调用未通过 Protocol 接口~~ ✅ `EventService` 使用 `CognitiveNodeRepository` Protocol 注入
5. ~~**测试覆盖**: 主要集中在 notification/agent, 对话/图谱核心模块缺少测试~~ ✅ `test_cognitive_writer.py` (17 用例, CognitiveNodeWriter) + `test_tree_directory.py` (25 用例, DirectoryNode CRUD)
6. **Auth Gateway**: ~~独立网关 `auth-gateway/` 已实现，但后端 `app/domain/auth/` 仍有重复认证 API~~ ✅ `app/domain/auth/api.py` 路由注册已从 `main.py` 移除；`AuthMiddleware`（JWT 本地解码）保留；`settings_api` 保留；前端通过 nginx 将 `/api/auth/*` 路由到网关 :18001
7. ~~**前端 API 层**: 命名不统一 (apiFetch vs authedFetch vs api)~~ ✅ 统一委托 `@/lib/api/api`
8. ~~**配置分散**: 部分配置在 config.yaml, 部分在 .env, 部分硬编码~~ ✅ 核心超时移入 Settings；`cognitive/constants.py` 补缺；前端 API_BASE 集中
9. ~~**知识树存储**: v5 单表 JSONB 和 v2.10 cognitive_nodes 双写并存~~ ✅ 经调研为 dual-source 非 dual-write，`tree_sync.py` 死代码已清理
