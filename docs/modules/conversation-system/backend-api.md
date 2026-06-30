# 对话系统 · 后端 API

> REST API + SSE 流式协议。目录树操作和消息发送两支独立路由。
> 源码: [backend/app/api/conversation/](../../../backend/app/api/conversation/) | [backend/app/domain/conversation/](../../../backend/app/domain/conversation/)

---

## REST API

### 目录树操作

基础路径: `/api/conversations/tree/directory`

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/tree/directory` | 列出根级目录（root nodes） |
| GET | `/tree/directory?parent_id={id}` | 列出指定目录的子节点 |
| POST | `/tree/directory` | 创建目录/会话节点 |
| PATCH | `/tree/directory/{id}` | 重命名/移动节点 |
| DELETE | `/tree/directory/{id}` | 删除节点（级联） |

**POST 创建节点请求体：**

```json
{
  "node_type": "dir",      // "dir" | "conv"
  "kind": "temp",          // "temp" | "general" | ...
  "parent_id": "root_xxx",  // 父节点 ID（顶层可省略）
  "name": "💬 临时"         // 节点名称
}
```

**响应：**

```json
{
  "directory_node": {
    "id": "node_xxx",
    "node_type": "dir",
    "kind": "temp",
    "name": "💬 临时",
    "parent_id": "root_xxx",
    "created_at": "2026-06-26T..."
  }
}
```

### 消息操作

基础路径: `/api/conversations/tree/conversation`

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/tree/conversation/{cid}` | 获取会话信息 |
| GET | `/tree/conversation/{cid}/messages` | 获取会话消息列表 |
| POST | `/tree/conversation/{cid}/message` | 发送消息（触发 pipeline） |
| DELETE | `/tree/conversation/{cid}/message/{mid}` | 删除消息 |

**POST 发送消息：**

```json
{
  "text": "用户输入的内容",
  "partition_id": "pId_xxx",
  "conversation_id": "cId_xxx"
}
```

**响应（立即返回，不阻塞）：**

```json
{ "ok": true }
```

消息流式响应通过 SSE 通道（见下方）实时推送。

### 健康检查

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/health` | 服务健康检查 |

---

## SSE 流式协议

端点: `GET /api/conversations/{cid}/stream?reasoning=true&agent_label=`

传输格式: Line-delimited JSON (EventSource 兼容)

```
type: <event_type_id>
id: <seq_num>
data: <json>

```

### 事件类型

| ID | 事件名 | 数据格式 | 说明 |
|----|--------|---------|------|
| 0 | `token` | `{type:"text", text:"...", agent_label:"tutor"}` | 流式文本增量 |
| 1 | `tool_calls` | `{tool_calls:[{id,name,args}]}` | 工具调用宣告（pending） |
| 2 | `tool_call_update` | `{tool_call_id, status:"running"}` | 工具执行中 |
| 3 | `block_update` | `{type:"tool", block:{status:"done", result_content,...}}` | 工具执行结果 |
| 4 | `reasoning` | `{content:"...", signature:"..."}` | LLM 推理过程 |
| 5 | `done` | `{assistant_message:{id,...}, response_blocks:[...]}` | 流结束，附完整消息数据 |
| 6 | `error` | `{code, message}` | 错误 |
| 7 | `phase_change` | `{phase:"streaming"}` | 阶段切换通知 |
| 8 | `context_switch` | `{target_partition_id, reason}` | 上下文切换建议 |
| 9 | `tree_recommendation` | `{node_id, title}` | 知识树推荐 |

### 断线重连

服务端每条事件携带 `id:` 字段（自增序号）：

```
id: 42
data: {"type": "text", "text": "hello"}

```

浏览器 `EventSource` 断开时自动发送 `Last-Event-ID: 42` 头，服务端从第 43 条开始回放。`token_buffer` 缓存已发送事件支持回放。

---

## 后端 ReplyPipeline 阶段

```
POST /tree/conversation/{cid}/message 触发
  │
  ├─ Stage 1: 分类器 → auto_resolve (context_switch 事件)
  ├─ Stage 2: 保存用户消息 → tree_ops.add_message()
  ├─ Stage 3: 工具循环（无限轮，LLM 决定何时停止）
  │   ├─ tool_calls 事件 → 宣告所有工具调用
  │   ├─ tool_call_update 执行中
  │   └─ tool_block 事件 → 执行结果
  ├─ Stage 4: PostProcessor 链（索引、缓存、fire-and-forget）
  └─ Stage 5: done 事件
      ├─ assistant_message: 持久化后的真实消息 ID
      └─ response_blocks: 所有工具执行结果
```

---

## 认证

所有 `/api/conversations/tree/*` 路由需通过认证网关 (`:18001`) 验证 JWT token。请求头：

```
Authorization: Bearer <jwt_token>
```

未认证返回 `401 {"detail": "未登录或令牌已失效，请重新登录"}`。
