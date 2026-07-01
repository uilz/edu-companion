# 对话管线中断与恢复 — 设计分析

## 当前架构回顾

```
┌─ 前端 ─────────────────────────────────────────────────────┐
│                                                              │
│  ChatInput                                                   │
│    ↓ 调用 sendMessageImpl                                    │
│                                                              │
│  sendMessageImpl (actions/send-message.ts)                   │
│    1. 乐观写入: t_xxx(用户) + a_xxx(assistant占位)           │
│    2. chatStream.send(text, convId, dirId)                   │
│                                                              │
│  useChatStream (hooks/conversation/useChatStream.ts)          │
│    send() → POST /api/.../message {action:"send"}            │
│            → fetch ReadableStream → readSSEStream            │
│            → 每收到 event → dispatchEvent() → 直接写         │
│              useMessageStore.setState                         │
│                                                              │
│    stop() → abortRef.abort() → POST {action:"stop"}          │
│                                                              │
│  useConversation (refresh 恢复)                              │
│    → GET /api/.../stream/active/{convId}                     │
│    → 若 active → chatStream.replay(convId)                   │
│    → loadMessages(convId)                                    │
│                                                              │
├─ 后端 ─────────────────────────────────────────────────────┤
│                                                              │
│  POST /message {action:"send"}                               │
│    → start_background_pipeline() → StreamingResponse(SSE)    │
│                                                              │
│  _run_pipeline_task()                                        │
│    ReplyPipeline.invoke()                                    │
│    → Stage 1 ClassifyStage                                   │
│    → Stage 2 SaveMessageStage   ← 持久化用户消息             │
│    → Stage 3 ToolLoopStage      ← LLM 流式生成               │
│    → Stage 4 PostProcessStage   ← 持久化 assistant 消息      │
│    → Stage 5 DoneStage          ← 产出 done 事件             │
│                                                              │
│  POST /message {action:"stop"} → stream_buffer.cancel()      │
│    → task.cancel() 触发 asyncio.CancelledError               │
│    → 发布 done(cancelled:true) 到 buffer                     │
│    → PostProcessStage 不会执行                               │
│                                                              │
│  POST /message {action:"replay"}                             │
│    → has_active(convId) ? SSE回放 : {stream_ended:true}      │
│                                                              │
│  ActiveStreamTracker (active_stream.py)                      │
│    mark_start() — 只在 legacy process_message() 调用          │
│    _run_pipeline_task() 没有调用 mark_start()                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 问题 1: 刷新后内容无法恢复

### 涉及的链路

用户正在流式对话 → 刷新页面 → `useConversation` 挂载 → 三步恢复流程：

1. **URL/localStorage 恢复 selectedNode** (useConversation.ts:84-129)
2. **流式重连检查** (useConversation.ts:175-217)
3. **loadMessages 加载历史** (useConversation.ts:220-226)

### 缺陷 A: ActiveStreamTracker 未接入新管线 (Critical Bug)

**代码证据:**

`active_streams.mark_start()` 只在旧入口 `process_message()` 调用:

```python
# conversation_processor.py:49 — 旧入口
async def process_message(...):
    await active_streams.mark_start(conv_id)  # ✅ 调用
    ...

# conversation_processor.py:93 — 新入口（当前实际使用）
async def start_background_pipeline(...):
    await stream_buffer.publish(conv_id, {"type": "stream_start"})  # ❌ 没调用 mark_start
    task = asyncio.create_task(_run_pipeline_task(...))
    ...

# _run_pipeline_task() 内部也没有调用 mark_start
```

**后果:** `/api/conversations/tree/stream/active/{convId}` 永远返回 `{"active": false}`。`useConversation.ts:175-217` 的重连逻辑永远不会触发 replay。

**影响范围:** 所有使用新 POST `/message` 端点的会话（即当前全线会话），刷新后都不会触发流式重连。

### 缺陷 B: loadMessages 与 replay 并发竞态

`useConversation.ts` 中两个 `useEffect` 都依赖 `activeConversationId`:

```typescript
// Effect 1: 流式重连 (line 175)
useEffect(() => {
  // ... check stream active → replay(convId)
}, [activeConversationId, chatStream]);

// Effect 2: 加载历史消息 (line 220)
useEffect(() => {
  if (activeConversationId && !isSending()) {
    actions.loadMessages(activeConversationId);
  }
}, [activeConversationId]);
```

两者在 `activeConversationId` 变更时并发触发，存在竞态：
- replay 创建 `r_xxx` 临时 assistant 消息并接入 SSE
- loadMessages 调用 `_rebuild()`，用 `outlines + loadedContent` 重建 `messages`
- `_rebuild` 中的 `pipelineMsgs` 保存逻辑能兜住 `r_xxx`，但顺序取决于哪个先完成
- 若 `loadMessages` 的 API 响应先于 replay 的 SSE 连接建立，`_rebuild` 后 `r_xxx` 消失，后续 SSE token 写入可能丢失目标

### 缺陷 C: 取消时 assistant 消息未持久化

Pipeline 被 `cancel()` → `asyncio.CancelledError` 抛在 `pipeline.invoke()` 循环中 → 直接跳到 `except CancelledError` 分支:

```python
# conversation_processor.py:228-234
except asyncio.CancelledError:
    await _publish_event_to_buffer(conv_id, ReplyEvent(
        type="done", content=assistant_text,
        data={"done": True, "cancelled": True},
    ))
```

`PostProcessStage` 中的 `tree_ops.add_message()` (pipeline_stages.py:504-509) 没有机会执行。

**后果:** 即使 replay 重连成功，也只能恢复 StreamBuffer 中的事件（token/tool 等），assistant 消息本身不会作为树节点存储在数据库中。下次 `loadMessages` 时，树上没有这条 assistant 消息。

### 缺陷 D: replay 创建新占位消息而非恢复已有

```typescript
// useConversation.ts:191-211
const tempAsstId = "r_" + ... // 新建临时 ID
useMessageStore.setState((s) => ({
  streamingId: tempAsstId,
  messages: [...s.messages, { id: tempAsstId, ... }], // 追加空白占位
}));
```

replay 从 StreamBuffer 事件 0 开始完整回放，这意味着所有历史 token 会重新拼接到一个**全新的** `r_xxx` 消息上，而不是恢复到原始 assistant 消息。这导致:

- `loadMessages` 加载的历史消息和 replay 恢复的消息是**两条不同的消息**（不同的 ID），UI 出现重复
- replay 消息的 parent_id 等关系链缺失

---

## 问题 2: 中断后 AI 输出截断 vs 丢失

### 当前行为分析

用户点击 Stop → `chatStream.stop()` 执行两步:

```
1. abortRef.current?.abort()         ← 立即断开 fetch/SSE
2. POST {action:"stop"} → backend    ← 告诉后端停止生成
```

**步骤 1 的 AbortError 处理:**

```typescript
// useChatStream.ts:209-214
catch (err: unknown) {
  if (err instanceof DOMException && err.name === "AbortError") {
    storeApi.setState({ isLoading: false, statusMessage: "" });
    useMessageStore.setState({ streamingId: null });
    return;  // ← 直接返回，不抛出上游
  }
}
```

**步骤 2 的后端行为:**

```python
# stream_buffer.py:122-135
async def cancel(self, conv_id: str):
    task.cancel()     # 触发 CancelledError
    entry["done"] = True
    # 通知 subscriber（但前端已断开）
```

```python
# conversation_processor.py:228-234
except asyncio.CancelledError:
    await _publish_event_to_buffer(conv_id, ReplyEvent(
        type="done", content=assistant_text,  # 累积的文本
        data={"done": True, "cancelled": True},
    ))
    # PostProcessStage 未执行，assistant 消息未持久化
```

### 关键缺陷: 前端断开连接后后端 done 事件无法送达

后端确实产出了 `done(cancelled:true)` 事件到 StreamBuffer，但前端 fetch 已被 `abort()` 断开，SSE reader 不再读取。`done` 事件传递的 `assistant_text`（中断前已累积的完整文本）永远到不了前端。

**当前残留数据:**

停止后 `messages` 数组里保留着 `a_xxx` 消息 + 流式阶段通过 `_handleToken` 累积的 `content_blocks`。`_rebuild` 时 `pipelineMsgs` 保护机制也能保留这个临时消息。

**但什么情况下数据会真正丢失:**

| 场景 | 结果 |
|------|------|
| 停止后继续在当前会话聊天 | pipelineMsgs 保留 `a_xxx` ✅ |
| 停止后切换到另一个 conversation | `selectGraphNode` 执行 `useMessageStore.setState({ messages: [] })` → `a_xxx` 清除 ❌ |
| 停止后刷新页面 | `loadMessages` 从服务端加载 → 服务端没有 `a_xxx`（PostProcessStage 未执行）→ 丢失 ❌ |
| 停止后等待超时（StreamBuffer 清理） | StreamBuffer 是内存结构，服务重启后 `done(cancelled)` 事件也丢失 |

---

## 根因总结

```
刷新丢失内容的根因链:
  _run_pipeline_task() 未调 active_streams.mark_start()
    → stream/active 永远返回 inactive
      → useConversation 不触发 replay
        → 刷新后只走 loadMessages
          → 服务端无未完成消息（PostProcessStage 未执行）
            → 刷新后丢失 ❌

中断丢失内容的根因链:
  stop() 中 abort() 断开 SSE
    → 后端 done(cancelled) 事件无法送达前端
      → 前端拿不到 done 数据中的完整 assistant_text
        + 后端 PostProcessStage 未执行（assistant 消息未持久化）
          → 残留只在内存中（a_xxx 临时消息）
            → 离开会话或刷新后丢失 ❌
```

两个问题的根因交汇于同一个设计缺陷:

> **Pipeline 取消链路中，前端"切断"了与后端的通信，同时后端不持久化部分完成的 assistant 消息。**

---

## 推荐修复方向

### 方案: 不 abort SSE + 后端在取消时持久化截断消息

**前端侧 (useChatStream):**

```
stop() 不应 abort fetch，应:
  1. 仅 POST {action:"stop"} 告知后端
  2. 设置本地标志 hasStopped = true
  3. 在 SSE 事件循环中，每收到 token 时检查 hasStopped，忽略后续 token
  4. 等待后端 done(cancelled) 事件到达
  5. done 事件中携带的 assistant_message 包含完整截断内容
```

**后端侧 (_run_pipeline_task):**

```
CancelledError handler 中:
  1. 跑 PostProcessStage 的精简版，调用 tree_ops.add_message() 持久化截断消息
  2. 持久化的 assistant 消息携带最终 content_blocks
  3. 发布 done 事件时包含完整的 assistant_message model_dump
```

**后端侧 (start_background_pipeline):**

```
补充 active_streams.mark_start(conv_id) 调用
```

### 优点

1. 停止后 SSE 连接自然关闭，前端拿到截断消息（不是空白占位符）
2. 截断消息已持久化到树，刷新后 `loadMessages` 可以恢复
3. StreamBuffer 中回复的 active 状态正确，replay 机制可用
4. 前端不需要维护两套 ID（a_xxx vs r_xxx）的复杂合并逻辑

### 需注意

- SSE 等待 done 事件的超时保护（若后端崩溃，不能永久阻塞）
- `mark_start` 放在 `start_background_pipeline` 还是 `_run_pipeline_task` 开头需要确认
- 取消时的 PostProcessStage 精简版：SocraticCounter 等非必要处理器可跳过，只需 `tree_ops.add_message()` + `ResponseBlockSaver`
