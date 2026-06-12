# Auth Gateway — 独立认证网关

独立认证网关服务（端口 18001，开发 8001），负责用户注册/登录/密码管理/JWT 签发与验证。完全独立于业务后端——独立数据库连接池、独立 JWT 密钥库。

详见 [CONTEXT-MAP.md](../CONTEXT-MAP.md) 中的组件关系。

---

## Language

### 核心实体

**User (用户)**:
存储在 `users` 表的认证用户。字段：id(username 无关的 UUID)/username(email)/password_hash(bcrypt)/display_name/avatar_url/role(user|admin)/is_active/token_version/last_login。auth-gateway 持有 User 数据的所有权。
_Avoid_: account（与"账号"概念混淆时）

**Reserved Username (保留用户名)**:
禁止注册的系统保留用户名集合：default_user/admin/root/system/anonymous/guest/null/undefined/api/test。所有用户名注册时自动转小写去重。
_Avoid_: 黑名单用户名

### 认证令牌

**Access Token (访问令牌)**:
HS256 签名的 JWT short-lived 令牌。声明含 sub(user_id)/username/role/token_version/exp/iat/type(access)。默认有效期 24 小时。
_Avoid_: JWT token（冗余）、登录令牌

**Refresh Token (刷新令牌)**:
HS256 签名的 JWT long-lived 令牌。声明仅含 sub(user_id)/exp/iat/type(refresh)。默认有效期 7 天。用于无感刷新 access token。

**Token Version (令牌版本)**:
`users.token_version` 字段。每次强制下线（密码修改/管理员踢出）时递增，旧令牌自动失效。

### 认证流程

**Register (注册)**:
创建新用户。验证用户名非保留、密码强度（≥8 位+大小写+数字）。返回 user + access_token + refresh_token。

**Login (登录)**:
验证用户名密码，更新 `last_login` 时间。受限流保护：60 秒内最多 5 次尝试（key 为用户名或 IP），超出返回 429。

**Login Event (登录事件)**:
每次登录写入 `login_events` 表。记录 user_id/ip_address/device_type/browser/os/region。用于安全审计与在线状态判定。

**Password Policy (密码策略)**:
最小 8 位，必须包含大写字母、小写字母和数字。bcrypt 哈希存储（`hash_password`/`verify_password`）。

### 限流与安全

**Login Rate Limit (登录限流)**:
内存字典追踪 `(attempts, first_attempt_time)`。60 秒窗口内超过 5 次失败，返回 429 Too Many Requests。窗口期满自动重置。
_Avoid_: 暴力破解防护（具体实现是限流）

**CORS Whitelist (CORS 白名单)**:
从 `AUTH_CORS_ORIGINS` 环境变量读取允许的跨域源列表。默认 `http://localhost:3000,http://127.0.0.1:3000`。

### 代理

**Reverse Proxy (反向代理)**:
auth-gateway 内嵌 HTTP 反向代理（`ReverseProxyMiddleware`），将非认证 API 请求转发到业务后端。当 Nginx 统一网关部署后（推荐），此层为 fallback，不再承担主要路由职责。
_Avoid_: 依赖 auth-gateway 作为主要 HTTP 代理（应使用 Nginx）

**WebSocket Proxy (WS 代理)**:
auth-gateway 将 `/api/conversations/ws` 的 WebSocket 升级请求透明转发到业务后端。在代理层注入 `user_id` query 参数（从 JWT payload 提取），实现 WS 层面的用户隔离。此功能在 Nginx 架构下仍保留——Nginx 将 WS 流量路由到 auth-gateway 执行认证 + 注入后，再转发到后端。

### 流量路径（Nginx 架构）

```
登录/注册:  Browser → Nginx :8080 → Auth GW :18001
WS 对话:    Browser → Nginx :8080 → Auth GW :18001（JWT 验证 + user_id 注入 → Backend :8000）
业务 API:   Browser → Nginx :8080 → Backend :8000（后端本地 JWT 解码）
前端页面:   Browser → Nginx :8080 → Next.js :3000
```

### 部署

**独立数据库**:
auth-gateway 拥有独立的 PostgreSQL 连接池（`DB` 实例），与业务后端数据库物理或逻辑隔离。

**Health Check (健康检查)**:
`GET /api/health` 返回 `{"status":"ok"}`。用于负载均衡器和监控系统探测。

### Flagged ambiguities

- **"JWT 密钥"** 与 "JWT_SECRET" —— 环境变量名 `JWT_SECRET`，代码中变量名 `secret`。auth-gateway 与业务后端/管理员后端使用完全相同的 JWT_SECRET 以确保令牌互认。
- **"登录"** 与 "认证" —— "登录"是提交凭证获取令牌的动作，"认证"是整个身份验证体系。
- **"用户 ID"** 与 "username" —— User 的 `id` 字段是内部 UUID（`u_` 前缀），`username` 字段是登录用的唯一标识符。两者不同。
- **"黑名单"** —— 系统使用"保留用户名"（Reserved Username）而非黑名单，因"黑名单"带有预设价值判断，且系统不维护独立的"封禁名单"概念——封禁通过 `is_active=false` + `token_version` 递增实现。