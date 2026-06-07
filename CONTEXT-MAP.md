# Context Map

This is a multi-context repo. Each context has its own `CONTEXT.md` defining its domain language.

| Context      | Path                           | Description                                                  |
| ------------ | ------------------------------ | ------------------------------------------------------------ |
| Auth Gateway | `auth-gateway/`                | 独立认证网关服务 (~2,000 行, 端口 8001/18001)。独立数据库、独立 JWT。 |
| Backend      | `backend/docs/CONTEXT.md`      | Python FastAPI 业务后端 (~36,000 行, 端口 8000)。自适应学习/AI 对话/认知追踪/练习/秘书系统。 |
| Frontend     | `frontend/docs/CONTEXT.md`     | Next.js 14 前端应用 (~19,000 行 TS/TSX, 端口 3000)。含 API 代理 (rewrites)。 |
| Shared       | `backend/shared/` + `docs/`    | 纯共享层：领域事件定义 (events.py)、常量 (constants.py)、协议接口 (protocols/)、架构文档 (docs/architecture/)。 |

## Relationships

- **Frontend → Backend**: Frontend 的 Next.js rewrites 将 `/api/*` 和 `/ws/*` 请求代理到 Backend（127.0.0.1:8000），实现同源访问。
- **Frontend → Auth Gateway**: Frontend 在登录/注册场景下直连 Auth Gateway（端口 18001）。
- **Auth Gateway → (独立)**: 认证网关不依赖业务后端模块，拥有独立数据库连接池和 JWT 密钥。
- **Shared layer (`backend/shared/`)**: 领域事件定义（events.py）、常量（constants.py）、协议接口（protocols/）不属于任何 context，是纯共享层。

## Data Flow

```
用户浏览器
    │
    ▼
Frontend (Next.js :3000)
    │
    ├── rewrites (同源代理)
    │   ├── /api/*  ──────────────────► Backend (FastAPI :8000)
    │   └── /ws/*  (WebSocket upgrade) ──► Backend (FastAPI :8000)
    │
    └── 直连
        └── 登录/注册 ──────────────► Auth Gateway (:18001)
```
