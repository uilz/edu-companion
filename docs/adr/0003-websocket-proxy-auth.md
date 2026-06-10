# ADR 0003: WebSocket 代理认证

WebSocket 连接不直接暴露给客户端，而是通过 auth-gateway 透明代理。Gateway 在代理层从 JWT cookie 解析用户身份，将 `user_id` 作为 query 参数注入 WS 升级请求，业务后端从 query 参数读取。

## Status

Accepted

## Considered Options

- **WS 直连后端**：前端直接连到主后端 WS 端口。需要 WS 协议处理 JWT 认证（复杂易出错），且对外暴露业务后端端口。
- **Gateway WS 代理**：认证网关统一处理 HTTP 和 WS 认证。增加一次代理转发开销，但统一了认证入口，业务后端不需要处理 WS 认证逻辑。

## Consequences

- auth-gateway 依赖 `websockets` 库（≥10.4）的 `additional_headers` 参数注入 user_id
- 业务后端 WS 端点从 `websocket.query_params` 读取 `user_id`，不再依赖 cookie 或 token
- Gateway 层同时实现 WS 连接限制（每 IP 最多 10 个连接）和消息大小限制（1MB）
- 增加约 1-5ms 的代理延迟，但大幅简化 WS 认证流程