# 🎓 智能伴学系统 (Edu-Companion)

> 基于 AI 的智能学习伴侣，为学生提供个性化的学习辅导、知识问答、学习规划和进度追踪服务。

---

## 📋 目录

- [项目简介](#项目简介)
- [架构概览](#架构概览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [Docker 部署](#docker-部署)
- [本地开发](#本地开发)
- [环境变量](#环境变量)

---

## 📖 项目简介

智能伴学系统是一个面向 K12 教育场景的 AI 辅助学习平台，集成了以下核心功能：

- 🤖 **AI 智能问答** — 基于大语言模型的学科知识问答，支持多轮对话
- 📚 **个性化学习路径** — 根据学生水平智能推荐学习内容和练习
- 📊 **学习进度追踪** — 实时记录和可视化学习进度与薄弱环节
- 🧠 **知识图谱** — 基于向量数据库的知识关联与检索增强生成（RAG）
- 📝 **智能错题本** — 自动整理错题并生成针对性复习计划
- 👨‍👩‍👧‍👦 **家长/教师看板** — 多角色权限管理，支持学习报告生成

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │   Web 浏览器      │  │   移动端 App      │  │  小程序端     │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
└───────────┼─────────────────────┼───────────────────┼───────────┘
            │                     │                   │
            ▼                     ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      前端应用层                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Next.js (React 18 + TypeScript)             │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │ 学习中心  │ │ AI 对话  │ │ 错题本   │ │ 学习报告 │   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端服务层                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                FastAPI (Python 3.11)                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │ 用户认证  │ │ AI 引擎  │ │ 课程管理 │ │ 数据分析 │   │    │
│  │  │  模块    │ │  模块    │ │   模块   │ │   模块   │   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────┬──────────┬──────────┬──────────────────────┬────────────┘
        │          │          │                      │
        ▼          ▼          ▼                      ▼
┌──────────┐ ┌──────────┐ ┌──────────┐  ┌──────────────────┐
│PostgreSQL│ │  Redis   │ │ 向量数据库 │  │   外部 AI API    │
│   16     │ │   7      │ │ pgvector │  │  (OpenAI等)      │
│ +数据持久化│ │ +缓存/队列│ │ +语义检索 │  │                  │
└──────────┘ └──────────┘ └──────────┘  └──────────────────┘
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Next.js 14 | React 服务端渲染框架 |
| | TypeScript | 类型安全的 JavaScript |
| | Tailwind CSS | 原子化 CSS 框架 |
| | Zustand | 轻量级状态管理 |
| | Socket.IO | 实时通信 |
| **后端** | FastAPI | 高性能 Python Web 框架 |
| | SQLAlchemy 2.0 | 异步 ORM |
| | Alembic | 数据库迁移工具 |
| | Pydantic v2 | 数据校验与序列化 |
| | Celery | 异步任务队列 |
| **数据库** | PostgreSQL 16 | 主数据库（含 pgvector） |
| | Redis 7 | 缓存、会话、消息队列 |
| | pgvector | 向量相似度检索（RAG） |
| **AI** | OpenAI API | 大语言模型接口 |
| | LangChain | AI 编排框架 |
| | Sentence Transformers | 文本向量化 |
| **部署** | Docker | 容器化部署 |
| | Docker Compose | 多服务编排 |
| | Nginx | 反向代理（生产） |

---

## 📁 项目结构

```
edu-companion/
├── docker/                      # Docker 配置
│   ├── docker-compose.yml       # 服务编排配置
│   ├── Dockerfile.backend       # 后端镜像构建
│   └── Dockerfile.frontend      # 前端镜像构建
├── backend/                     # 后端服务
│   ├── __init__.py
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置管理
│   ├── models/                  # 数据模型
│   │   ├── user.py
│   │   ├── course.py
│   │   ├── question.py
│   │   └── learning_record.py
│   ├── schemas/                 # Pydantic 模式
│   │   ├── user.py
│   │   ├── course.py
│   │   └── chat.py
│   ├── api/                     # API 路由
│   │   ├── v1/
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── course.py
│   │   │   └── analytics.py
│   ├── services/                # 业务逻辑
│   │   ├── ai_service.py
│   │   ├── rag_service.py
│   │   ├── user_service.py
│   │   └── analytics_service.py
│   ├── utils/                   # 工具函数
│   │   ├── auth.py
│   │   └── vector_store.py
│   └── requirements.txt         # Python 依赖
├── frontend/                    # 前端应用
│   ├── src/
│   │   ├── app/                 # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── chat/
│   │   │   ├── courses/
│   │   │   ├── mistakes/
│   │   │   └── dashboard/
│   │   ├── components/          # 可复用组件
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── KnowledgeCard.tsx
│   │   │   ├── ProgressBar.tsx
│   │   │   └── Sidebar.tsx
│   │   ├── lib/                 # 工具库
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   └── socket.ts
│   │   ├── stores/              # 状态管理
│   │   │   ├── chatStore.ts
│   │   │   └── userStore.ts
│   │   └── types/               # TypeScript 类型
│   │       └── index.ts
│   ├── public/                  # 静态资源
│   ├── next.config.js
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.ts
├── alembic/                     # 数据库迁移
│   ├── versions/
│   └── env.py
├── alembic.ini
├── .env.example
├── .gitignore
├── README.md
└── Makefile
```

---

## 🚀 快速开始

### 前提条件

- Docker >= 24.0
- Docker Compose >= 2.20
- Node.js >= 20（本地开发需要）
- Python >= 3.11（本地开发需要）

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/your-org/edu-companion.git
cd edu-companion

# 2. 复制环境变量配置文件
cp .env.example .env

# 3. 编辑 .env 文件，填入你的 API 密钥
#    至少需要配置 OPENAI_API_KEY

# 4. 启动所有服务
cd docker
docker compose up -d

# 5. 查看服务状态
docker compose ps

# 6. 访问应用
#    前端: http://localhost:3000
#    后端 API 文档: http://localhost:8000/docs
#    PostgreSQL: localhost:5432
#    Redis: localhost:6379
```

---

## 🐳 Docker 部署

### 启动服务

```bash
cd docker

# 构建并启动
docker compose up -d --build

# 仅启动数据库和缓存（开发用）
docker compose up -d postgres redis

# 查看日志
docker compose logs -f backend
docker compose logs -f frontend
```

### 常用命令

```bash
# 停止所有服务
docker compose down

# 停止并清除数据卷
docker compose down -v

# 重建指定服务
docker compose build --no-cache backend

# 进入容器调试
docker compose exec backend bash
docker compose exec postgres psql -U eduadmin -d edu_companion

# 运行数据库迁移
docker compose exec backend alembic upgrade head

# 查看资源占用
docker compose stats
```

### 生产环境建议

1. 使用 Nginx 反向代理，配置 HTTPS
2. 修改所有默认密码和密钥
3. 配置 PostgreSQL 持久化存储到高性能磁盘
4. 设置 Redis 密码认证
5. 配置日志收集和监控
6. 使用 `--profile` 启动可选服务

---

## 💻 本地开发

### 后端开发

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
cd backend
pip install -r requirements.txt

# 启动 PostgreSQL 和 Redis（使用 Docker）
cd ../docker
docker compose up -d postgres redis

# 运行数据库迁移
cd ..
alembic upgrade head

# 启动后端开发服务器（热重载）
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
# 安装依赖
cd frontend
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 类型检查
npm run type-check

# 代码格式化
npm run lint
```

---

## ⚙️ 环境变量

### 后端环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL 连接字符串 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址 |
| `SECRET_KEY` | - | JWT 签名密钥（必填） |
| `OPENAI_API_KEY` | - | OpenAI API 密钥（必填） |
| `OPENAI_MODEL` | `gpt-4o` | 使用的 LLM 模型 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 向量化模型 |
| `POSTGRES_USER` | `eduadmin` | 数据库用户名 |
| `POSTGRES_PASSWORD` | `edu_secret_2024` | 数据库密码 |
| `POSTGRES_DB` | `edu_companion` | 数据库名称 |
| `CORS_ORIGINS` | `http://localhost:3000` | 允许的跨域来源 |

### 前端环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | 后端 API 地址 |
| `NEXTAUTH_SECRET` | - | NextAuth 签名密钥 |
| `NEXTAUTH_URL` | `http://localhost:3000` | 应用访问地址 |

---

## 📜 许可证

MIT License © 2024 Edu-Companion Team
