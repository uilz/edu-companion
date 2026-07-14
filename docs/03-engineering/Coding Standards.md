# AppleGo Coding Standards

> 本文档由 开发规范 + 前端规范 + 后端规范 合并而成。原文归档于 `docs/engineering/`。

---

## 通用规范

### 工作流

AppleGo 采用 Experience-Driven Development（EDD）。Agent 不自选任务、不自创任务。所有开发以 Spec 为唯一依据。

```
Founder → Experience → Specification → CPO 拆 Capability → Agent 拆 Story + Task → Coding → DoD 检查 → Founder 验收 → CPO Review
```

### Definition of Done

任何 PR 必须通过以下检查才能 Merge：

| 维度 | 检查项 |
|------|--------|
| 产品 | Product Bible 一致、不新增产品概念、不破坏 Today→Session→Growth 闭环 |
| 领域 | Aggregate 边界正确、领域事件完整、无跨 Aggregate 直接数据访问 |
| 工程 | API 不破坏兼容性、Tests 通过、关键路径有日志、错误路径有处理 |
| UI | Loading / Empty / Error 三态齐全、Mobile 适配 |
| 体验 | Demo 可演示、用户可理解、AI 行为符合 AI Constitution |

### Git 工作流

- 分支命名：`feature/<epic>-<story-id>-<short-name>`
- Commit 信息：`<type>(<scope>): <description>`（feat / fix / refactor / test / docs）
- PR 前执行 `rebuild.sh` 验证构建通过
- 禁止 force push to main/master

### 分层与依赖方向

后端五层，上层依赖下层，不可逆：

```
api → domain/services → infrastructure
api → schemas → shared
```

前端三层：

```
app (路由+页面) → components (UI组件) → store/lib (状态+工具)
```

---

## 前端规范

### 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Next.js | 14 (App Router) | 框架 |
| React | 18 | UI 库 |
| TypeScript | strict | 类型安全 |
| Tailwind CSS | 3.x | 样式 |
| Zustand | — | 状态管理 |

### 组件规范

- **文件命名**：`PascalCase.tsx`（组件）、`camelCase.ts`（工具/hook/store）
- **三态必须**：每个数据组件必须处理 Loading / Empty / Error 三个状态
- **Props 类型**：所有组件 Props 必须显式声明 TypeScript 接口
- **导出方式**：优先 named export，页面组件用 default export
- **组件拆分**：单个文件不超过 300 行，复杂逻辑抽 hook

### 状态管理（Zustand）

```
store/
├── conversation/    # 对话状态（消息树、SSE 流）
├── agent/           # 秘书状态
├── pipeline/        # SSE 流处理
├── notification/    # 通知系统
└── explain/         # 知识解释
```

- 一个模块一个 store 文件，actions 从 store 中拆分到独立文件
- 避免在组件内直接操作深层状态，统一通过 store actions

### 样式规范

- 统一使用 Tailwind CSS utility classes
- 自定义设计令牌通过 CSS Variables 注入，由 `ThemeContext` 管理
- 5 套设计风格（professional / playful / knowledge / soft-data / gamified），每套支持 light/dark
- 圆角：卡片 10px、按钮 10px、气泡 14px
- 响应式断点：768px → 1024px，移动端底部导航

### 路由规范

- App Router 文件约定：`page.tsx`（页面）、`layout.tsx`（布局）、`loading.tsx`（加载态）、`error.tsx`（错误态）
- 动态路由：`[id]/page.tsx`
- API 客户端统一放在 `lib/api/`，不散落在组件中

---

## 后端规范

### 技术栈

| 技术 | 用途 |
|------|------|
| Python FastAPI | HTTP 框架 |
| PostgreSQL + pgvector | 数据库 + 向量检索 |
| LiteLLM | LLM 路由 |
| Pydantic | 数据校验 |

### 分层架构

```
backend/app/
├── api/               # 表示层：路由、请求验证、响应序列化
├── domain/            # 领域层：业务规则、领域模型（纯逻辑，无 I/O）
├── services/          # 应用层：用例编排
├── application/       # 依赖注入（di.py）、事件绑定
├── infrastructure/    # 基础设施：LLM 客户端、DB、调度器
├── schemas/           # Pydantic 数据模型
└── shared/            # 协议接口、常量、事件定义
```

### API 规范

- RESTful 约定：资源名用复数名词（`/conversations`、`/practice/sessions`）
- 请求/响应统一使用 Pydantic 模型
- 认证：JWT via `Authorization: Bearer <token>`，由独立 Auth Gateway 签发
- SSE 流式响应需设置 `proxy_buffering off`（Nginx 层）
- 错误响应格式：`{ "error": { "code": "string", "message": "string" } }`

### 数据模型规范

- JSONB 灵活存储 + 向量检索（HNSW 索引）
- 领域实体定义在 `domain/` 中为纯 Python 类
- 数据表 schema 管理在 `infrastructure/db/`
- 时区约定：DB 列存 CST 墙钟，Python 用 `datetime.now()`，禁止 `datetime.utcnow()`

### 错误处理

- 业务异常统一抛出 Domain Exception，由 FastAPI exception handler 转换为 HTTP 响应
- 所有 LLM 调用必须带超时和重试策略
- 关键路径（对话、练习、认知追踪）必须有日志

---

## 测试规范

### 核心理念

测试不以代码覆盖率为目标，以**产品验收**为目标。产品验收不通过 = 功能未完成。

### 测试层级

| 层级 | 内容 | 负责人 |
|------|------|--------|
| 产品验收 | 是否符合 Product Bible 和 Experience 定义 | Founder / CPO |
| E2E 测试 | 完整用户流程（前后端集成） | Agent |
| 单元测试 | 核心领域逻辑 | Agent |

### 测试要求

- Agent 提交前必须通过 Definition of Done 全部检查
- 测试数据不得使用生产数据
- 后端测试用 pytest，前端测试用 vitest
- 每个 Story 必须附带 Given-When-Then 格式的验收场景

---

> 如有冲突以 `docs/00-foundation/` 中的产品宪法和设计原则为准。
