# 对话系统 · 后端 API

> 完整 API 文档见 [subsystems/conversation/backend-api.md](../../subsystems/conversation/backend-api.md)（迁移中）。
>
> 以下为关键接口概览。

---

## REST 接口

### 分区 (Partition)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/partitions` | 列出所有分区（ETag 缓存） |
| POST | `/partitions` | 创建新分区 |

### 领域/专题/对话

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/{parent_type}/{id}/children` | 获取子节点列表 |
| POST | `/{parent_type}` | 创建子节点 |
| PATCH | `/{type}/{id}` | 重命名 |
| DELETE | `/{type}/{id}` | 删除（级联） |

### 消息

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/conversations/{id}/messages` | 获取消息列表 |
| POST | `/conversations/{id}/messages` | 发送消息 |
| PATCH | `/messages/{id}` | 编辑消息内容 |
| DELETE | `/messages/{id}` | 删除消息 |
| POST | `/messages/{id}/sub-branch` | 创建子支会话 |

## WebSocket

```
ws://host/conversations/{id}/ws?user_id={user_id}
```

### 流式事件

| 事件 | 方向 | 说明 |
|------|------|------|
| `stream_start` | → 前端 | 开始流式响应 |
| `stream_chunk` | → 前端 | 文本块 |
| `response_block` | → 前端 | 多模态响应块 |
| `stream_end` | → 前端 | 流结束 |
| `tree_recommendation` | → 前端 | 知识树推荐 |
| `temp_recommendation` | → 前端 | 临时会话推荐 |
| `error` | → 前端 | 错误信息 |
