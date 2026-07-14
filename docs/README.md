# 苹果果 - AI Learning Companion

> AI 驱动的个人学习伙伴，持续理解学习者、陪伴成长、优化学习路径。

**技术栈**：Next.js 14 + React 18 + FastAPI + PostgreSQL + pgvector

**核心定位**：以 Session（学习会话）为产品核心对象，通过 Learner Model 持续理解学习者。

---

## 快速开始

```bash
bash rebuild.sh      # 一键启动（前后端 + Nginx + 认证网关）
# 访问 http://localhost:8080

cd frontend && npm run dev          # 前端开发（:3000）
cd backend && uvicorn main:app --reload  # 后端开发（:8000）
```

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx | 8080 | 统一入口、SSE 代理 |
| Next.js | 3000 | App Router 前端 |
| FastAPI | 8000 | 业务 API、LLM 调用 |
| Auth Gateway | 18001 | 认证、JWT |
| Admin | 3001 | 管理后台 |

---

## 新手入口

> **如果你是第一次来：请先读 [README_FIRST.md](../README_FIRST.md)。**

---

## 文档导航（AppleGo Product OS）

### 00-foundation（最高决策层 — 永远不会轻易改）

| 文档 | 唯一职责 |
|------|---------|
| [Manifesto](00-foundation/Manifesto.md) | 苹果果为什么存在 |
| [Product Vision](00-foundation/Product%20Vision.md) | 为谁而做、核心飞轮、北极星指标 |
| [Product Constitution](00-foundation/Product%20Constitution.md) | 12 条最高原则 |
| [AI Constitution](00-foundation/AI%20Constitution.md) | AI 行为边界（6 条） |
| [Product Principles](00-foundation/Product%20Principles.md) | 5 条设计原则（快速决策） |
| [Interaction Laws](00-foundation/Interaction%20Laws.md) | 全产品交互定律（6 条，任何 Story 违反即打回） |
| [Learning Principles](00-foundation/Learning%20Principles.md) | 学习理念（12 条，所有 Story 的最高仲裁） |
| [V1 Scope](00-foundation/V1%20Scope.md) | V1 精确功能边界 |

### 01-product（产品表现层 — 回答"产品怎么做给用户"）

| 文档 | 唯一职责 |
|------|---------|
| [Product Bible](01-product/Product%20Bible.md) | 苹果果是什么（产品定义） |
| [Product Blueprint](01-product/Product%20Blueprint.md) | V1 完整形态——用户的一天、一个月、半年 |
| [Learning Session Design](01-product/Learning%20Session%20Design.md) | ⭐ 核心产品——一次学习的完整体验（9 章） |
| [Session Interaction Spec](01-product/Session%20Interaction%20Spec.md) | Session 完整交互规范（Agent 编码的唯一交互依据） |
| [Experience Backlog](01-product/Experience%20Backlog.md) | 用户会经历什么（7 条体验） |
| [User Journey](01-product/User%20Journey.md) | 用户旅程——Day 1 ~ Day 30 |
| [Capability Roadmap](01-product/Capability%20Roadmap.md) | 系统需要什么能力 |
| [Roadmap](01-product/Roadmap.md) | 时间线演进路线 |

### 02-domain（领域模型层 — 回答"系统怎么组织"）

| 文档 | 唯一职责 |
|------|---------|
| [DDD](02-domain/DDD.md) | 为什么使用 DDD + Bounded Context + Aggregate + Event |
| [Domain Model](02-domain/Domain%20Model.md) | 领域模型 |
| [Context Map](02-domain/Context%20Map.md) | Bounded Context 映射 |
| [Event Storming](02-domain/Event%20Storming.md) | 事件风暴 |
| [Glossary](02-domain/Glossary.md) | 统一产品术语 |
| [ADR/](02-domain/ADR/) | 架构决策记录（26 条） |

### 03-engineering（工程规范层 — 回答"Agent 怎么写代码"）

| 文档 | 唯一职责 |
|------|---------|
| [AGENTS](03-engineering/AGENTS.md) | Agent 开发规范 |
| [Coding Standards](03-engineering/Coding%20Standards.md) | 编码规范 |
| [API Standards](03-engineering/API%20Standards.md) | API 设计约定 |
| [Architecture](03-engineering/Architecture.md) | 系统架构总览 |
| [Definition of Done](03-engineering/Definition%20of%20Done.md) | PR 完成标准 |
| [Development Workflow](03-engineering/Development%20Workflow.md) | EDD 开发流程 + Development Package |
| [Testing](03-engineering/Testing.md) | 测试规范（产品验收导向） |
| [specifications/](03-engineering/specifications/) | 8 份产品规格书（设计图纸） |

### 04-delivery（交付层 — 回答"现在做什么"）

| 文档 | 唯一职责 |
|------|---------|
| [Master Backlog](04-delivery/Master%20Backlog.md) | 唯一开发清单 |
| [Acceptance](04-delivery/Acceptance.md) | 验收标准 |
| [Releases](04-delivery/Releases.md) | 版本发布记录 |

### 支撑目录

| 目录 | 内容 |
|------|------|
| [modules/](modules/) | 模块技术文档（21 个模块） |
| [templates/](templates/) | 文档模板 |
| [rfcs/](rfcs/) | 技术方案 RFC |
| [research/](research/) | 认知科学与学习科学研究 |
| [archive/](archive/) | 历史归档（旧版 foundation/product/domain/principles 等） |
| [old/](old/) | 更早的历史归档 |

---

## 文档依赖图（单向引用，禁止横向复制）

```
Manifesto
    ↓
Product Vision
    ↓
Product Constitution  ←  AI Constitution
    ↓
Product Bible  ←  Product Principles  ←  V1 Scope
    ↓
Experience Backlog  ←  User Journey
    ↓
Capability Roadmap
    ↓
Specifications（设计图纸，冻结后开发）
    ↓
DDD  ←  Glossary  ←  ADR
    ↓
Master Backlog
    ↓
AGENTS  ←  Coding Standards  ←  Definition of Done
```

> **规则**：下层可引用上层。禁止横向复制内容。一件事实只写一次。

---

## 项目结构速览

```
edu-companion/
├── README_FIRST.md        # 新人入口
├── AGENTS.md              # Agent 协作规则
├── frontend/              # Next.js 14 前端
├── backend/               # FastAPI 后端
├── auth-gateway/          # 独立认证网关
├── admin/                 # 管理后台
├── docs/
│   ├── 00-foundation/     # 最高决策层（6 份）
│   ├── 01-product/        # 产品表现层（6 份）
│   ├── 02-domain/         # 领域模型层（5 + ADR/）
│   ├── 03-engineering/    # 工程规范层（7 + specifications/）
│   ├── 04-delivery/       # 交付层（3 份）
│   ├── modules/           # 模块文档
│   ├── templates/         # 文档模板
│   ├── rfcs/              # RFC 制度
│   ├── research/          # 认知科学/学习科学
│   ├── archive/           # 历史归档
│   └── old/               # 更早归档
└── rebuild.sh             # 一键重启
```

---

> **维护者：Founder。最后更新：IA 重构完成后。**
