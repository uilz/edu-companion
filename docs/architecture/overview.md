# 系统架构总览 v8.0

> 版本: v8.4.0 | 最后更新: 2026-06-09
> CognitiveNode 是唯一数据源，所有模块的认知状态以此为基准。

---

## 一、项目概述

苹果果是一个 AI 驱动的个人知识体系构建工具，提供自主学习规划、精准答疑、多模态交互、知识追踪、个性化陪伴等功能。

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 14 + Tailwind CSS | SSR/CSR 混合，CSS Variables 主题切换 |
| 状态管理 | Zustand | 分模块 store（conversation/、explain/） |
| 后端 | Python FastAPI | 异步高性能，OpenAPI 自动文档 |
| 数据库 | PostgreSQL 14+ + pgvector | JSONB 灵活存储 + 向量检索 |
| LLM | LiteLLM（统一路由） | 支持 OpenAI / DeepSeek / 通义千问 / Anthropic 等 100+ 模型，支持用户自定义配置 |
| 认证 | 独立认证网关 | 与业务后端完全解耦，独立 JWT 管理 |
| 加密 | cryptography (Fernet) | API Key 等敏感信息加密存储 |
| 部署 | Docker + Nginx | 双容器部署，前端 standalone 模式 |

---

## 二、后端分层架构

```
backend/
├── app/
│   ├── api/              # 表示层 — REST API 路由
│   │   ├── conversation/ # 对话 API（WS、消息、分支）
│   │   ├── knowledge/    # 知识图谱 API（CRUD、查询、AI、对话联动）
│   │   ├── learning/     # 学习/认知 API（进度、画像、计划、增强）
│   │   ├── practice/     # 练习 API（v7 题库、错题本、会话、出题、统计、导入、解释卡片、参考资料）
│   │   └── system/       # 系统 API（秘书、搜索、成就、文件管理、多模态、摘要、数据管理）
│   │
│   ├── domain/           # 领域层 — 业务逻辑核心
│   │   ├── analytics/    # 分析域（行为分析、情绪分析、习惯养成）
│   │   ├── auth/         # 认证域（用户、登录事件、LLM 自定义配置）
│   │   ├── conversation/ # 对话域
│   │   ├── knowledge/    # 知识域（图谱、认知引擎、ZPD）
│   │   ├── practice/     # 练习域
│   │   ├── secretary/    # 秘书域（诊断引擎、提案生成、模块注册表、事件消费者）
│   │   └── ...           # habits/ materials/ media/ multimedia/ planning/
│   │
│   ├── services/         # 应用层 — 服务实现
│   │   ├── conversation/ # 对话服务（LLM 对话、消息仓库）
│   │   ├── knowledge/    # 知识服务（图谱展开、ZPD 调度）
│   │   ├── practice/     # 练习服务（自适应、题库、错题）
│   │   ├── llm/          # LLM 服务（核心、提示词、工具调度、嵌入、服务）
│   │   └── ...
│   │
│   ├── cognitive/        # 认知引擎模型
│   ├── schemas/          # 数据模型（Pydantic）
│   └── db/               # 数据访问层
│
├── shared/               # 共享层 — 协议、常量、事件
│   ├── protocols/         # 仓储协议接口
│   ├── events.py          # 事件定义
│   └── constants.py       # 常量
│
└── infra/                # 基础设施层
    ├── llm/              # LLM 客户端适配
    └── database.py       # 数据库连接
```

### 分层原则

| 层 | 职责 | 依赖方向 |
|----|------|----------|
| api/ | HTTP 路由、请求验证、响应序列化 | → domain/, services/ |
| domain/ | 业务规则、领域模型、领域服务 | → shared/protocols |
| services/ | 应用服务、用例编排、外部调用 | → domain/, infra/ |
| db/ | 数据访问、仓储实现 | → shared/protocols |
| shared/ | 协议接口、常量、事件定义 | 无依赖 |
| infra/ | 外部依赖适配（LLM、DB） | 无依赖 |

---

## 三、前端分层架构

```
frontend/src/
├── app/                   # 页面路由（Next.js App Router）
│   ├── learn/             # 对话学习页
│   ├── learn/graph/       # 学习页内嵌图谱
│   ├── graph/             # 知识图谱页（独立）
│   ├── knowledge-tree/    # 知识树页
│   ├── practice/          # 练习首页
│   │   ├── banks/[id]/    # 题库详情
│   │   ├── sessions/[id]/ # 练习会话
│   │   └── history/       # 练习历史
│   ├── exam/              # 考试模式
│   ├── errors/            # 错题本
│   ├── study/             # 学习规划页
│   ├── focus/             # 专注模式页
│   ├── secretary/         # 秘书面板
│   │   └── settings/      # 秘书偏好设置
│   ├── analytics/         # 分析仪表盘
│   ├── stats/             # 统计页
│   ├── emotion/           # 情绪仪表盘
│   ├── achievements/      # 成就系统
│   ├── progress/          # 学习进度
│   ├── calendar/          # 学习日历
│   ├── resources/         # 资源页
│   ├── files/             # 文件管理
│   │   └── [material_id]/ # 资料详情
│   ├── import/            # 数据导入
│   ├── quality/           # 质量管理
│   ├── dashboard/         # 仪表盘
│   ├── settings/          # 设置
│   │   └── data/          # 数据管理
│   └── login/             # 登录页
│
├── components/            # UI 组件 — 按业务域分组
│   ├── conversation/      # 对话组件
│   ├── graph/             # 知识图谱组件
│   ├── practice/          # 练习组件
│   └── ...
│
├── lib/                   # 库 — 按职责分组
│   ├── api/               # API 客户端
│   ├── utils/             # 工具函数
│   └── types/             # 类型定义
│
├── store/                 # 状态管理 — 按域分组
│   ├── conversation/
│   └── explain/
│
├── hooks/                 # 页面级 hooks
└── contexts/              # React Context（Auth、Theme）
```

---

## 四、认证架构

采用**独立认证网关**方案，与业务后端完全解耦：

```
前端 → 认证网关(:18001) → 业务后端(:8000)
           ↘              ↘
        认证数据库      业务数据库
```

- 认证网关独立进程、独立数据库，负责注册/登录/JWT 签发
- 业务后端通过中间件验证 JWT，注入用户上下文
- 前端全局 fetch 拦截器自动附加 Token

### 用户自定义 LLM 配置

```
前端设置页 → PUT /api/settings/llm → 业务后端
                                         │
                                     ├── Fernet 加密 api_key
                                     ├── 存入 user_llm_configs 表
                                     └── 返回 { ok: true }

对话系统 → LLMService.generate(user_id=xxx)
               │
           ├── 查询 user_llm_configs
           ├── 解密 api_key
           └── 调用 LiteLLM(api_key, api_base, model)
```

### 登录事件追踪

| 事件 | 存储表 | 数据 | 触发时机 |
|------|--------|------|----------|
| 用户登录 | `login_events` | user_id, ip_address, device_type, browser, os, region, login_time | 每次登录成功 |
| 用户活跃 | `users.last_active_at` | timestamp | 每次认证请求更新（5 分钟 DB 内节流） |

在线状态判定：`last_active_at` 在最近 30 分钟内 → 在线。**单一数据源**，主应用与 admin 共用 `users.last_active_at`；admin `/api/admin/users` 列表直接返回 `is_online`，前端 30 秒轮询刷新。

> **时区约定**：DB 列 `timestamp without time zone` 存 CST 墙钟（与服务器本地时一致）。Python 判定在线时必须用 `datetime.now()`，**禁止** `datetime.utcnow()`，否则 0~8 小时内的活跃时间会因负 delta 误判为在线。未来若服务跨时区部署，需将列迁至 `TIMESTAMPTZ`。

---

## 五、部署架构

```
Nginx (:80/443)
├── /          → Frontend (Next.js :3000)
├── /api/      → Backend (FastAPI :8000)
└── /auth/     → Auth Gateway (FastAPI :8001)
```

---

## 六、核心实体：CognitiveNode

系统中所有知识点的统一表征。详见 [specs/01-cognitive-node.md](../specs/01-cognitive-node.md)。

---

## 七、事件总线

详见 [modules/cognitive-engine/event-bus.md](../modules/cognitive-engine/event-bus.md)。

---

## 八、数据库分区

| 数据库 | 用途 | 归属 |
|--------|------|------|
| 业务数据库 (PostgreSQL) | CognitiveNode、对话、图谱、练习、login_events、user_llm_configs 等 | 业务后端 |
| 认证数据库 (PostgreSQL) | 用户、凭据、JWT | 认证网关 |

---

## 九、服务间通信

| 方向 | 方式 | 说明 |
|------|------|------|
| 前端 ↔ 后端 | REST + WebSocket | REST 用于 CRUD，WS 用于流式对话 |
| 前端 ↔ 认证网关 | REST | 注册、登录、Token 刷新 |
| 后端 ↔ LLM | HTTP (LiteLLM) | 通过 LiteLLM 统一路由，支持 100+ 模型，支持用户自定义配置 |

---

## 十、代码规模

| 模块 | 行数（估） | 文件数 |
|------|-----------|--------|
| 后端 (Python) | ~36,000 | ~208 |
| 前端 (TS/TSX) | ~19,000 | ~185 |
| 认证网关 (Python) | ~2,000 | ~15 |
| **合计** | **~56,000** | **~410** |

---

> 详细架构演进历史见 [archive/](../archive/)。当前架构由 v8.1 (知识树 AI 对话) 演进而来。
>
> ### 附：核心子系统架构
>
> | 子系统 | 文档 |
> |--------|------|
> | AI Tool 系统（LLM Function Calling） | [tool-architecture.md](tool-architecture.md) |
