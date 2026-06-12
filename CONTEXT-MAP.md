# Context Map

This is a multi-context repo. Each context has its own `CONTEXT.md` defining its domain language.

| Context      | Path                           | Description                                                  |
| ------------ | ------------------------------ | ------------------------------------------------------------ |
| Auth Gateway | `auth-gateway/`                | 独立认证网关服务 (~2,000 行, 端口 18001)。独立数据库、独立 JWT。 |
| Backend      | `backend/docs/CONTEXT.md`      | Python FastAPI 业务后端 (~36,000 行, 端口 8000)。自适应学习/AI 对话/认知追踪/练习/秘书系统。 |
| Frontend     | `frontend/docs/CONTEXT.md`     | Next.js 14 前端应用 (~19,000 行 TS/TSX, 端口 3000)。纯 SSR，无代理逻辑。 |
| Nginx        | `nginx/`                       | Nginx 统一网关 (端口 8080)。路由分发 + WS 代理 + SSL 终结。 |
| Shared       | `backend/shared/` + `docs/`    | 纯共享层：领域事件定义 (events.py)、常量 (constants.py)、协议接口 (protocols/)、架构文档 (docs/architecture/)。 |

## Relationships

- **Nginx → All**: Nginx 是唯一对外入口。所有流量从 Nginx :8080 进入，按路径分发。
- **Nginx → Backend**: `/api/*` → Backend :8000。后端 AuthMiddleware 本地解码 JWT（不调认证网关，~0.01ms）。
- **Nginx → Auth Gateway**: `/api/auth/*` → Auth Gateway :18001（认证 API 原生处理）；`/api/conversations/ws` → Auth Gateway :18001（WS 代理 + JWT 注入）。
- **Nginx → Frontend**: `/*` → Next.js :3000。前端无任何代理配置，API 和 WS 均通过同源相对路径请求 Nginx。
- **Auth Gateway → (独立)**: 认证网关不依赖业务后端模块，拥有独立数据库连接池和 JWT 密钥。
- **Backend Auth**: 后端通过共享 `JWT_SECRET` 本地解码 JWT（HS256），不再 HTTP 调用认证网关。
- **Shared layer (`backend/shared/`)**: 领域事件定义（events.py）、常量（constants.py）、协议接口（protocols/）不属于任何 context，是纯共享层。

## Data Flow

```
用户浏览器 ──→ Nginx :8080 (单一入口)
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
   Auth GW   Backend    Next.js
   :18001    :8000      :3000
   认证API    业务API    SSR
   WS代理     本地JWT
              解码
```

## Security Flow

```
1. 登录：  浏览器 → Nginx → Auth GW :18001 → 返回 JWT token
2. API：   浏览器 → Nginx → Backend :8000（AuthMiddleware 本地解码 JWT）
3. WS：    浏览器 → Nginx → Auth GW :18001（验证 JWT → 注入 user_id → 转发到 Backend :8000）
```
