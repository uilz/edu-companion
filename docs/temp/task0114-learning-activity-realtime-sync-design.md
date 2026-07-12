# Phase 3：跨壳学习活动实时同步与多源聚合设计

## 1. 背景与目标

Phase 2 已实现 `learning_activities` 表与事件处理器，但前端只能被动轮询。Phase 3 目标是：

1. 当学习事件发生时，前端仪表盘能实时收到新活动通知。
2. 解决「同一学习行为被多个来源记录」导致的多源聚合冲突。

## 2. 关键决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 实时通道 | SSE | 单向推送足够，浏览器原生支持，比 WebSocket 轻量 |
| 冲突类型 | 多源聚合冲突 | 同一业务行为可能由 practice/cognitive/error_book 等不同来源产生记录 |
| 持久化 | 事件总线 + PostgreSQL | 不引入新组件，沿用现有基础设施 |
| 幂等键 | `idempotency_key` | Phase 2 已引入业务幂等键，Phase 3 在此基础上扩展优先级与合并策略 |

## 3. 多源聚合冲突解决策略

### 3.1 业务键分配规则

每个活动必须带一个全局唯一的 `idempotency_key`，格式为 `{domain}:{business_id}`：

| 事件 | 业务键示例 |
|------|-----------|
| AnswerSubmitted | `answer:{attempt_id}` |
| SessionCompleted | `session:{session_id}` |
| FlashCardReviewed | `fc_review:{card_id}:{session_id}:{ts}` |
| TreeNodeCreated | `tree_node:{node_id}` |
| PlanItemCompleted | `plan_completed:{plan_item_id}` |

### 3.2 来源优先级（source_authority）

当同一 `idempotency_key` 被多个来源写入时，按来源优先级决定是否覆盖/合并：

| 来源模块 | 优先级 | 说明 |
|----------|--------|------|
| practice | 100 | 练习域是答题/会话的原始来源，权威最高 |
| error_book | 90 | 错题本是练习的衍生记录 |
| flashcard | 80 | 闪卡复习独立来源 |
| reading | 80 | 阅读进度独立来源 |
| knowledge_tree | 70 | 用户主观结构 |
| planning | 70 | 计划项状态 |
| secretary | 60 | 秘书系统聚合/推荐 |

### 3.3 冲突处理流程

```
写入新 activity 时：
  1. 查找 (user_id, idempotency_key) 是否已存在
  2. 不存在 → 插入
  3. 存在 → 比较 source_authority
       新来源优先级 >= 旧来源 → 覆盖 title/description/meta/source_module
       新来源优先级 < 旧来源 → 跳过
  4. 无论插入还是覆盖，都发布 SSE 事件通知前端
```

## 4. SSE 协议

### 4.1 端点

```
GET /api/activities/stream
Authorization: Bearer <token>
Content-Type: text/event-stream
```

### 4.2 事件格式

```json
{
  "event": "activity_created" | "activity_updated" | "connected" | "heartbeat",
  "activity_id": "la_xxx",
  "user_id": "u_xxx",
  "data": { /* LearningActivityResponse */ }
}
```

### 4.3 心跳

每 30 秒发送一次 `: heartbeat\n\n` 保活。

## 5. 前端消费

新增 `useLearningActivityStream` hook：

- 自动建立 EventSource 连接
- 收到 `activity_created` / `activity_updated` 时：
  - 方式 A：将新活动 prepend 到本地列表（ optimistic ）
  - 方式 B：触发 `useLearningActivities` 的 refetch（简单可靠）
- 断线后指数退避重连
- 页面不可见时暂停连接，恢复后重连

## 6. 实现文件清单

后端：
- `backend/app/application/handlers/learning_activity_event_bus.py`
- `backend/app/api/learning_activity/routes.py` 新增 `/stream`
- `backend/app/application/handlers/learning_activity_handler.py` 写入后发布 SSE
- `backend/app/api/learning_activity/service.py` 新增 `get_activity_by_idempotency_key`

前端：
- `frontend/src/hooks/useLearningActivityStream.ts`

## 7. 验收条件

- [x] 发布 SessionCompleted 后，SSE 客户端 1 秒内收到 `activity_created` 事件
- [x] 同一 session_id 再次发布 SessionCompleted，SSE 客户端收到 `activity_updated` 或不推送（取决于是否覆盖）
- [x] 模拟低优先级来源覆盖高优先级来源，数据库记录保持不变
- [x] 前端 hook 能在仪表盘组件中实时更新活动列表
- [x] rebuild.sh 全链路验证通过

## 8. 验证记录

验证时间：2026-07-12
验证脚本：`scripts/test/task0118/verify_phase3_realtime_sync.py`

结果：
- SSE 实时推送：✅ 通过
- 多源聚合冲突解决：✅ 通过
- 幂等更新：✅ 通过
- 前端秘书页「学习活动」标签：✅ 实时连接中，列表正常更新
- rebuild.sh 全链路：✅ 通过
