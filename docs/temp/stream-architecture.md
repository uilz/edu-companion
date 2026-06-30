# 对话流式架构重构

## 核心模型

一个端点 `POST /api/conversations/{cid}/message`，三种 action：

| action | 行为 |
|---|---|
| `send` | 启动 Pipeline → 返回 SSE（从事件 0 开始） |
| `replay` | 重连 → 从事件 0 回放全部 + 继续新事件 |
| `stop` | cancel pipeline_task → 持久化 → `{ ok: true }` |

## StreamBuffer（服务端）

```
每 conv: {
  events: list,           // Pipeline 全部事件（上限 2000）
  pipeline_task: Task,    // asyncio Task（只有一个状态位）
  subscribers: set,       // 当前 SSE generator
}
```

- 无 paused/stopped 状态标记
- reply → events[0] 起回放 → 实时追
- Pipeline crash → error event → 所有 subscriber 断开

## 前端 useChatStream

```typescript
const [events, setEvents] = useState<StreamEvent[]>([]);
const [phase, setPhase] = useState("idle|streaming|done");

send(text) → POST { action:"send", text } → readSSE(res.body)
replay()   → POST { action:"replay" }     → readSSE(res.body)
stop()     → abort + POST { action:"stop" }

// 派生渲染
streamingText = events.type="token" 的 content 拼接
toolBlocks    = events.type="tool_block" 的 block
```

## P0 基础设施 Bug（不修架构也跑不了）

### 1. `request_timeout` 30s 强制超时（main.py:268-278）

`asyncio.wait_for(call_next(request), timeout=30)` 包裹了所有请求。
SSE 长连接超过 30s 就会 `TimeoutError` → 流必断。

**修**: 检查 `request.url.path`，跳过流式端点。

### 2. Nginx buffer + read_timeout（nginx.conf:44-51）

`/api/` 没有 `proxy_buffering off`（默认 on，缓冲延迟 token 送达）。
没有 `proxy_read_timeout` 延长（默认 60s，断长连接）。

**修**: 对 `/api/conversations/*/message` 启用 `proxy_buffering off` + 更长的 `proxy_read_timeout`。

## 重构会自然解决的 Bug

| Bug | 原因 | 新架构如何解决 |
|---|---|---|
| streamingId 单值 + done 回调覆盖新 streamingId | 全局单值 + 事件竞态 | 不依赖 streamingId，events[] 是每次 send 独立 |
| _rebuild 覆盖流式 message | 多数据源合并 | done 后才进 MessageStore |
| EventSource 不支持 Authorization header | 只能用 query param | fetch ReadableStream 支持 header |
| StreamPipeline 4 阶段状态机 | 过度设计 | 无了 |
| setup.ts 跨 Store 分发工具事件 | setup.ts 查找 streamingId 匹配 | Hook 内 events[] → 直接派生 |
| SSE 重连 reply blocks 丢失 | 断线后 done 事件不再 replay | replay 从事件 0 回放，不丢 |

## 实现步骤（到 /docs/temp/tasks.md）

1. 后端 StreamBuffer 替代 TokenBuffer
2. 后端统一 POST /message 端点（action=send/replay/stop）
3. 后端移除旧的 stream_sse 端点（GET stream + pause/resume/stop）
4. 修复 request_timeout 中间件
5. 修复 Nginx 配置
6. 前端 useChatStream hook + readSSEStream
7. 前端删除 StreamPipeline / SSESource / setup.ts 旧逻辑
8. 前端 ChatInput / ConversationPanel 接入 useChatStream
9. rebuild.sh 测试
