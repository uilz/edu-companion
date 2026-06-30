# ADR 0002: 用户数据隔离策略

所有数据操作的用户身份必须从 `request.state.user_id`（中间件注入）或 `Depends(current_user_id)`（路由层注入）获取，禁止任何形式的硬编码用户 ID（如 `DEFAULT_USER_ID`）。

## Status

Accepted

## Considered Options

- **硬编码默认用户**：开发阶段使用 `DEFAULT_USER_ID="default"` 快速迭代。部署时存在严重安全隐患——所有用户共享同一身份，数据完全未隔离。
- **动态注入用户 ID**：通过 FastAPI 依赖注入系统，每个请求从 JWT 令牌解析用户 ID，中间件注入到 `request.state`。开发成本较高，但保证用户级数据隔离。

## Consequences

- 2026-05~06 期间完成了全量清理：路由层（knowledge_routes/conversation_routes）和 service 层（28+ 文件）移除 `DEFAULT_USER_ID` 硬编码
- `Depends(current_user_id)` 成为所有业务路由的强制签名要求
- WebSocket 连接通过 auth-gateway 代理注入 `user_id` query 参数，后端 WS 端点从 query 读取
- 新增路由时必须显式注入用户 ID，否则编译/运行时即可发现问题