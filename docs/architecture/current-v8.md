# 智能伴学系统架构文档 v8.0

> 版本: v8.0
> 最后更新: 2026-06-05
> 当前版本号: v7.0.14+
> 状态: 分层重构已完成（后端 + 前端）

---

## 一、项目概述

智能伴学系统（edu-companion）是一个基于 AI 的全栈学习伴侣平台，提供自适应学习规划、精准答疑、多模态交互、学情追踪、心理陪伴等功能。

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 14 + Tailwind CSS | SSR/CSR 混合，CSS Variables 主题切换 |
| 状态管理 | Zustand | 分模块 store（conversation/、explain/） |
| 后端 | Python FastAPI | 异步高性能，OpenAPI 自动文档 |
| 数据库 | PostgreSQL 14+ + pgvector | JSONB 灵活存储 + 向量检索 |
| LLM | OpenAI 兼容 API | 通过 .env 配置模型名 |
| 认证 | 独立认证网关 | 与业务后端完全解耦，独立数据库、JWT 管理 |
| 部署 | Docker + Nginx | 双容器部署，前端 standalone 模式 |

---

## 二、后端分层架构

```
backend/
├── app/                          # 主应用
│   ├── api/                      # 表示层 — REST API 路由
│   │   ├── conversation/         # 对话 API（WS、消息、分支）
│   │   ├── knowledge/            # 知识图谱 API
│   │   ├── learning/             # 学习/认知 API（study、progress、cognitive）
│   │   ├── practice/             # 练习 API（v7 题库、错题本、考试）
│   │   └── system/               # 系统 API（秘书、搜索、成就、文件、多模态）
│   │
│   ├── domain/                   # 领域层 — 业务逻辑核心
│   │   ├── analytics/            # 分析域（行为分析、情绪分析、习惯养成）
│   │   ├── auth/                 # 认证域（JWT、用户、会话）
│   │   ├── conversation/         # 对话域
│   │   ├── habits/               # 习惯域
│   │   ├── knowledge/            # 知识域（图谱、认知引擎、ZPD）
│   │   ├── materials/            # 资料域
│   │   ├── media/                # 媒体域
│   │   ├── multimedia/           # 多模态域
│   │   ├── planning/             # 规划域
│   │   ├── practice/             # 练习域
│   │   └── secretary/            # 秘书域（诊断引擎、提案生成、策略引擎）
│   │
│   ├── services/                 # 应用层 — 服务实现
│   │   ├── analytics/            # 分析服务（自适应规划、间隔重复、成就）
│   │   ├── common/               # 公共服务（存储、事件、分类器、摘要）
│   │   ├── conversation/         # 对话服务（LLM 对话、消息仓库、上下文）
│   │   ├── knowledge/            # 知识服务（图谱展开、认知查询、ZPD 调度）
│   │   ├── llm/                  # LLM 服务（核心、提示词、工具调度、嵌入）
│   │   ├── materials/            # 资料服务（索引、搜索、解析、B站搜索）
│   │   └── practice/             # 练习服务（自适应、题库、错题、考试）
│   │
│   ├── application/              # DI 容器
│   ├── db/                       # 数据访问层（连接池 + 仓储实现）
│   ├── middleware/               # 中间件（认证、CORS）
│   ├── schemas/                  # 数据模型（Pydantic）
│   ├── cognitive/                # 认知引擎模型
│   ├── data/                     # 运行时数据（策略记忆、秘书偏好）
│   ├── knowledge/                # 课程知识（各学科课程文件）
│   └── scripts/                  # 运维脚本
│
├── shared/                       # 共享层 — 协议、常量、事件
│   ├── protocols/                # 仓储协议接口
│   ├── events.py                 # 事件定义
│   ├── constants.py              # 常量
│   └── ...                       # 工具函数（blackboard、errors、learner_model 等）
│
├── infra/                        # 基础设施层 — 外部依赖适配
│   ├── llm/                      # LLM 客户端适配
│   └── database.py               # 数据库兼容重导出
│
└── auth-gateway/                 # 独立认证网关（独立进程）
    ├── auth_app/                 # 认证应用
    ├── config/                   # 独立配置
    └── ...
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
├── app/                          # 页面路由（Next.js App Router）
│   ├── (auth)/                   # 认证页面（login）
│   ├── dashboard/                # 仪表盘页
│   ├── practice/                 # 练习页
│   ├── focus/                    # 专注模式页
│   ├── graph/                    # 图谱页
│   ├── settings/                 # 设置页
│   └── ...
│
├── components/                   # UI 组件 — 按业务域分组
│   ├── conversation/             # 对话组件
│   │   ├── core/                 # 核心组件（Panel、Input、MessageList）
│   │   ├── renderers/            # 消息渲染器
│   │   ├── blocks/               # 消息块组件
│   │   ├── banners/              # 横幅组件
│   │   ├── panels/               # 面板组件
│   │   ├── input/                # 输入组件
│   │   ├── cards/                # 卡片组件
│   │   ├── tree/                 # 树形组件
│   │   ├── media/                # 媒体组件
│   │   └── hooks/                # 对话 hooks
│   │
│   ├── graph/                    # 知识图谱组件
│   │   ├── graphs/               # 图形可视化
│   │   ├── modals/               # 弹窗
│   │   ├── panels/               # 侧边面板
│   │   ├── pages/                # 页面级组件
│   │   └── nodes/                # 节点组件
│   │
│   ├── practice/                 # 练习组件
│   │   ├── panels/               # 面板
│   │   └── components/           # 子组件
│   │
│   ├── dashboard/                # 仪表盘
│   │   ├── tabs/                 # Tab 页面
│   │   └── analytics/            # 分析子组件
│   │
│   ├── layout/                   # 布局组件
│   ├── ui/                       # 通用 UI（shadcn）
│   ├── search/                   # 搜索组件
│   ├── secretary/                # 秘书组件
│   ├── focus/                    # 专注组件
│   ├── analytics/                # 分析组件
│   ├── auth/                     # 认证组件
│   └── ...
│
├── lib/                          # 库 — 按职责分组
│   ├── api/                      # API 客户端（api、auth、practice-api、learning-api、graph-api、fetch-interceptor）
│   ├── utils/                    # 工具函数（utils、math、sanitize）
│   ├── types/                    # 类型定义（graph-types）
│   └── hooks/                    # 通用 hooks（useRenderedContent）
│
├── store/                        # 状态管理 — 按域分组
│   ├── conversation/             # 对话状态（含 actions/）
│   └── explain/                  # 解释状态
│
├── hooks/                        # 页面级 hooks — 按域分组
│   ├── conversation/             # 对话 hooks
│   ├── graph/                    # 图谱 hooks
│   ├── practice/                 # 练习 hooks
│   └── study/                    # 学习 hooks
│
├── contexts/                     # React Context（Auth、Theme）
└── types/                        # 全局类型
```

---

## 四、认证架构

系统采用**独立认证网关**方案，与业务后端完全解耦：

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   前端       │────▶│  认证网关         │────▶│  业务后端         │
│  Next.js    │     │  auth-gateway    │     │  FastAPI         │
│             │◀────│  :8001           │     │  :8000           │
└─────────────┘     └──────────────────┘     └──────────────────┘
                           │                          │
                    ┌──────┴──────┐            ┌──────┴──────┐
                    │ 认证数据库   │            │ 业务数据库   │
                    │ PostgreSQL  │            │ PostgreSQL  │
                    └─────────────┘            └─────────────┘
```

- **认证网关**：独立进程，独立数据库，负责注册/登录/密码修改/JWT 签发
- **业务后端**：通过认证中间件验证 JWT，注入用户上下文
- **前端**：全局 fetch 拦截器自动附加 Token

---

## 五、核心实体：CognitiveNode

系统中所有知识点的统一表征。详见旧版架构文档 `archive/current-v4.md`。

---

## 六、代码规模

| 模块 | 行数（估） | 文件数 |
|------|-----------|--------|
| 后端 (Python) | ~35,000 | 175 (app/) + 22 (shared/) + 8 (infra/) |
| 前端 (TS/TSX) | ~18,000 | 180 |
| 认证网关 (Python) | ~2,000 | 15 |
| 合计 | ~55,000 | ~400 |

---

## 七、部署架构

```
Nginx (:80/443)
├── /          → Frontend (Next.js :3000)
├── /api/      → Backend (FastAPI :8000)
└── /auth/     → Auth Gateway (FastAPI :8001)
```

---

## 八、重构历史

| 时间 | 重构内容 |
|------|----------|
| 2026-06-04 | 后端分层重构：消除两套 domain 并存，合并 core→shared，按业务域拆分 services/ 和 api/ |
| 2026-06-05 | 前端分层重构：conversation/graph/practice/hooks 深度分组，lib/store 按域拆分 |
| 2026-06-05 | 认证网关独立：与业务后端完全解耦 |
