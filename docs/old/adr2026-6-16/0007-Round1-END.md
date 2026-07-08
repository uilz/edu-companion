# ADR 0007: Round 1 重构完成

> 日期: 2026-06-13 | 状态: Accepted

Round 1 完成 6 项核心重构, 为自由目录结构和事件化认知系统奠定基础.

## 完成项

| ADR | 内容 | 关键影响 |
|-----|------|----------|
| 0001 | 独立认证网关 | auth-gateway 独立进程+独立 DB, 业务后端 JWT 本地解码 |
| 0002 | 用户数据隔离 | `Depends(current_user_id)` 强制签名, 移除全部 `DEFAULT_USER_ID` |
| 0003 | WebSocket 代理认证 | Gateway 注入 `user_id` query 参数, 业务 WS 端点直接读取 |
| 0004 | 通用事件表 + 认知操作注册 | `events` 表取代 `cognitive_events`, `CognitiveOperationRegistry` 装饰器注册 |
| 0005 | 自由目录节点结构 | `DirectoryNode` 统一 dir+conv, 取消固定三级, `MessageNode` 解耦 CognitiveNode |
| 0006 | Store 导航简化 | `selectedNodeId` + `selectedNodeType` 两字段取代旧六个导航字段 |

## 遗留

- Auth Gateway 仍标记为"设计方案"阶段, 部署脚本待完善
- 旧 `conversation_user_meta` 中 partitions/domains/topics JSONB 字段待清理
- 前端 ~200 处 `selectedPartitionId/active*Id` 引用待迁移
