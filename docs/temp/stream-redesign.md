# 对话系统流式架构修复

## 决定：保留 POST+SSE 双连接架构

用户要求保留「刷新后看到正在流式输出的半截文字」功能，因此保留双连接方案：
- POST 触发 pipeline（fire-and-forget）
- SSE 独立订阅事件流（可断线重连）

## 已修复的 Bug

### 1. TokenBuffer 事件截断 → token 静默丢失
- **根因**: `events` 截断后订阅者 `last_read_idx` 失效，读取位置错乱
- **修复**: 引入 `consumed_offset` 全局序号，截断时自动推进订阅者位置

### 2. StreamPipeline completing 超时(5s) 切断 SSE
- **根因**: PostProcessor 慢时 `stream_end` 未到就断开
- **修复**: 超时延至 30s

### 3. postSendRedirect 跳转不存在的路由
- **根因**: 尝试 `router.replace('/conversation/' + id)` 但路由只有 `/conversation`
- **修复**: 改用 query 参数 `?conv=xxx`

### 4. 认证中间件支持 SSE
- **结论**: 非 Bug。AuthMiddleware 已处理 `?token=` query param

## 待观察

- MessageStore 多路数据源（outlines + loadedContent + pipeline msgs）是否会导致渲染闪烁
- activeConversationId effect 在流式过程中是否会覆盖消息
