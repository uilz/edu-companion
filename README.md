# 🎓 智能伴学系统 (Edu-Companion)

> AI 驱动的个性化学习伴侣 —— 自适应学习规划、知识点讲解、智能练习、学情追踪

---

## 📋 目录

- [项目简介](#项目简介)
- [架构概览](#架构概览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [对话系统（核心）](#对话系统核心)
- [快速开始](#快速开始)
- [开发指南](#开发指南)
- [近期重构](#近期重构)

---

## 📖 项目简介

智能伴学系统是一个面向学生的 AI 辅助学习平台，覆盖**课前→课中→课后**全链路：

| 模块 | 功能 |
|------|------|
| 🤖 **AI 伴学对话** | 多轮启发式对话，支持知识点讲解、答疑、苏格拉底式追问 |
| 📚 **自适应练习** | 按知识点出题，BKT 知识追踪，动态调整难度 |
| 🧠 **知识图谱** | 知识点关联推理，技能前提链检测，薄弱环节定位 |
| 📊 **学情分析** | 学习进度可视化（雷达图/趋势图），错题归因分析 |
| 📝 **智能规划** | 基于掌握度的自适应学习路径推荐 |
| 🎯 **错题本** | 自动整理错题，遗忘曲线驱动的复习计划 |
| 🔊 **多模态交互** | 语音问答、图文讲解、视频检索（B站等） |

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Next.js 14)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ AI 对话   │ │ 练习中心  │ │ 学习报告  │ │ 知识图谱     │   │
│  │ (WS流式)  │ │ (BKT追踪) │ │ (CRUD)   │ │ (可视化)     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 (FastAPI + Python 3.11)                │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ 对话系统  │ │ 练习引擎  │ │ 知识追踪  │ │ 学习分析     │   │
│  │(分层路由) │ │(自适应出题)│ │(BKT+知识桥)│ │(事件驱动)    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ 分类器    │ │ 规划器   │ │ 多模态   │ │ 认知节点     │   │
│  │(意图路由) │ │(学习计划) │ │(搜索/语音)│ │(CognitiveNode)│  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└──────┬──────────┬──────────┬──────────────────────┬────────┘
       │          │          │                      │
       ▼          ▼          ▼                      ▼
┌──────────┐ ┌──────────┐ ┌──────────┐  ┌──────────────────┐
│PostgreSQL│ │  Redis   │ │  向量    │  │  外部 AI API     │
│  14/16   │ │   7      │ │ pgvector │  │  (Deepseek等)    │
│ +对话持久 │ │ +缓存    │ │ +语义检索 │  │                  │
└──────────┘ └──────────┘ └──────────┘  └──────────────────┘
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Next.js 14 (App Router) | React 18 + TypeScript, shadcn/ui |
| **后端** | FastAPI + Python 3.11 | 异步 REST + WebSocket |
| **数据库** | PostgreSQL 14/16 | 对话数据(PG)、JSONB 元数据、pgvector |
| **AI** | DeepSeek / OpenAI 兼容 API | LiteLLM 路由, 多模型策略 |
| **语音** | Edge-TTS / Whisper | 语音合成+识别 |
| **部署** | Nginx + systemd / Docker | 双机部署（编辑机+运行机） |

---

## 📁 项目结构

```
edu-companion/
├── backend/                   # Python 后端
│   ├── app/
│   │   ├── api/               # REST API 路由
│   │   │   ├── conversation.py    # 对话系统 CRUD (分区/领域/专题/对话/消息)
│   │   │   ├── practice.py        # 练习系统
│   │   │   ├── knowledge.py       # 知识图谱 API
│   │   │   ├── progress.py        # 学习进度
│   │   │   ├── partition_progress.py # 分区进度
│   │   │   ├── chat.py            # WebSocket 聊天
│   │   │   └── ...                # 其他路由
│   │   ├── services/           # 业务逻辑层
│   │   │   ├── conversation_llm.py # 🌟 AI 对话主逻辑 (845行)
│   │   │   ├── prompts.py          # 系统提示词 (从 conversation_llm 拆分)
│   │   │   ├── context_builder.py  # 对话上下文构建 (从 conversation_llm 拆分)
│   │   │   ├── pg_storage.py       # PostgreSQL 存储引擎
│   │   │   ├── tree_ops.py         # 侧栏树结构操作 (CRUD)
│   │   │   ├── classifier.py       # 意图分类/路由
│   │   │   ├── llm_service.py      # LLM 调用封装
│   │   │   └── ...                 # 其他服务
│   │   ├── schemas/             # Pydantic 数据模型
│   │   │   └── conversation.py     # 对话系统模型 (UserData/TreeNode/Partition...)
│   │   ├── core/                # 核心引擎
│   │   │   ├── orchestrator.py     # 事件编排器
│   │   │   ├── learner_model.py    # 学习者模型
│   │   │   └── knowledge_trace.py  # BKT 知识追踪
│   │   ├── cognitive/           # 认知节点系统 (Phase 6)
│   │   │   ├── models.py           # CognitiveNode 模型
│   │   │   ├── events.py           # 认知事件
│   │   │   └── storage.py          # 认知数据存储
│   │   ├── application/         # DI 容器
│   │   │   └── di.py               # 依赖注入容器
│   │   ├── db/                  # 数据库层
│   │   │   ├── database.py         # 连接池管理
│   │   │   └── conversation_schema.sql # 对话表 Schema
│   │   ├── shared/              # 共享类型
│   │   │   └── events.py           # 事件定义
│   │   ├── infra/               # 基础设施
│   │   │   ├── event_bus.py        # 事件总线
│   │   │   ├── circuit_breaker.py  # 熔断器
│   │   │   ├── resilience.py       # 重试/超时
│   │   │   └── tracing.py          # 链路追踪
│   │   └── main.py              # 入口 + lifespan
│   ├── domain/                 # 领域层
│   │   ├── conversation/          # 对话领域
│   │   ├── practice/              # 练习领域
│   │   ├── analytics/             # 分析领域
│   │   └── ...                    # 其他领域
│   ├── infra/                  # 顶层基础设施（供 domain/ 使用）
│   │   ├── event_bus.py
│   │   ├── resilience.py
│   │   ├── tracing.py
│   │   ├── database.py
│   │   ├── llm.py
│   │   └── tts_client.py
│   └── shared/                 # 顶层共享协议
│       ├── events.py
│       └── protocols/
├── frontend/                   # Next.js 前端
│   └── src/
│       ├── app/learn/             # 学习主页（对话界面）
│       ├── components/
│       │   └── conversation/      # 对话组件
│       │       ├── PartitionSidebar.tsx  # 侧栏树
│       │       ├── MessageList.tsx        # 消息列表
│       │       └── ...                    # 其他组件
│       └── ...
├── docs/                       # 设计文档
│   ├── phase1/ ~ phase6/         # 分阶段设计文档
│   └── architecture-v3.md       # 架构设计 v3
└── README.md
```

---

## 💬 对话系统（核心）

对话系统采用 **4 层分层结构**：

```
分区 (Partition)        ← 最高层级，按学科/方向划分
  └── 领域 (Domain)     ← 学科子领域
        └── 专题 (Topic) ← 具体知识点专题
              └── 对话 (Conversation)  ← 多轮对话会话
```

### 数据流

```
用户消息
  → classifier.auto_resolve()    # 意图分类 + 分区路由
    → conversation_llm.send_and_reply()
      → _build_context_messages()  # 构建 9 层上下文（情绪/知识桥/图谱...）
        → llm_service.chat()       # LLM 推理
          → 工具调用（搜索/出题/绘图）
            → 流式返回 + response_block 渲染
              → 异步: 知识证据分析 + CognitiveNode 联动
```

### 关键 API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/partitions` | GET/POST/PATCH/DELETE | 分区 CRUD |
| `/partitions/{id}/domains` | GET | 列出领域 |
| `/domains/{id}/topics` | GET | 列出专题 |
| `/topics/{id}/conversations` | GET/POST | 对话列表/创建 |
| `/conversations/{id}/messages` | GET | 消息列表 |
| `/message` | POST | 发送消息（REST） |
| `/ws` | WebSocket | 流式对话 |
| `/messages/{id}` | PUT/DELETE | 编辑/删除消息 |

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+（含 pgvector 扩展）
- Redis 7+（可选，缓存）

### 安装

```bash
# 后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 修改配置
./venv/bin/uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | AI API 密钥 | - |
| `OPENAI_API_BASE` | API 端点 | https://api.deepseek.com/v1 |
| `TEXT_MODEL` | 对话模型 | deepseek/deepseek-v4-flash |
| `DB_PASSWORD` | PostgreSQL 密码 | companion123 |
| `DB_PORT` | PostgreSQL 端口 | 5433 |

---

## 🧹 近期重构

| 重构项 | 说明 |
|--------|------|
| **conversation_llm.py 拆分** | 1064 行→845 行，提取 `prompts.py` 和 `context_builder.py` |
| **删除重复 `application/di.py`** | 顶层副本已删除，统一使用 `app.application.di` |
| **修复 13 处 `except: pass`** | 改为带上下文日志的 `logger.debug/warning` |
| **添加 ~55 条中文文档字符串** | 覆盖核心 4 文件（conversation.py, tree_ops.py, pg_storage.py, schemas） |
| **PG 存储引擎修复** | save() 加清理逻辑 + `__uncategorized__` 白名单保护 |
| **前端 404 自动清理** | loadChildren/loadMessages 遇到 404 自动移除僵尸节点 |
