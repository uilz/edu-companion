# ADR 0023: 跨壳学习活动实时同步与多源聚合冲突解决

## 状态

已接受 (Accepted) — Phase 3 实现完成 (Task #118)

## 背景

Phase 2 已建立 `learning_activities` 表与事件处理器，将跨模块学习行为统一记录。但前端只能通过轮询获取更新，无法实时反映用户的学习动态。同时，同一学习行为可能被多个模块记录（如一次答题可能同时被 practice、error_book、cognitive 关注），需要明确的冲突解决策略。

## 决策

### 1. 实时通道采用 SSE

- **选择**：Server-Sent Events (SSE)
- **理由**：
  - 学习活动是服务器到客户端的单向推送，无需双向通信
  - 浏览器原生支持 `EventSource`，比 WebSocket 更轻量
  - 与现有 HTTP 基础设施（Nginx、认证中间件）兼容性好

### 2. 认证方式采用 query token

- **选择**：`/api/activities/stream?token=<jwt>`
- **理由**：
  - `EventSource` 无法自定义请求头，不能走 `Authorization: Bearer` 标准方式
  - token 有效期短（access token），泄露风险可控
  - 后端复用现有 `AuthService.decode_token` 解析用户身份

### 3. 多源聚合冲突解决采用来源优先级

- **选择**：为每个来源模块分配 `source_authority` 数值，高优先级覆盖低优先级
- **优先级**：
  - `practice`: 100
  - `error_book`: 90
  - `flashcard`: 80
  - `reading`: 80
  - `knowledge_tree`: 70
  - `planning`: 70
  - `secretary`: 60
  - 其他：50
- **理由**：
  - 练习域是答题/会话的原始来源，权威最高
  - 错题本、闪卡、阅读等是独立或衍生来源，按业务重要性排序
  - 秘书系统作为聚合/推荐层，优先级最低，避免覆盖业务原始记录

### 4. 幂等键采用业务键

- **选择**：`idempotency_key = {domain}:{business_id}`
- **理由**：
  - 同一业务行为在不同来源间共享同一业务键
  - 结合 `(user_id, idempotency_key)` 唯一索引实现幂等写入
  - 避免重复记录和冲突

## 后果

### 正面

- 前端仪表盘、秘书页可实时展示学习活动
- 多模块记录同一行为时不会重复或相互覆盖错误
- 不引入新组件，复用 PostgreSQL 和内存 EventBus

### 负面

- SSE 连接数随在线用户增长，需要监控单实例连接上限
- query token 会暴露在 URL 中，需配合短有效期 token 使用
- 事件总线目前为单实例内存实现，多实例部署需引入 Redis 等共享通道

## 相关文件

- `backend/app/application/handlers/learning_activity_event_bus.py`
- `backend/app/application/handlers/learning_activity_handler.py`
- `backend/app/api/learning_activity/routes.py`
- `backend/app/api/learning_activity/service.py`
- `frontend/src/hooks/useLearningActivityStream.ts`
- `frontend/src/components/secretary/LearningActivityStream.tsx`
- `docs/temp/task0114-learning-activity-realtime-sync-design.md`
- `scripts/test/task0118/verify_phase3_realtime_sync.py`
