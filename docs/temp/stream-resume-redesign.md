# 流式恢复架构重设计

## 现状问题

- 后端在 pipeline 完成时才生成 msg_id（Stage 4），刷新恢复时前端只能用临时 ID 占位
- `_handleDone` 需要做 ID 替换，streaming 期间 store 中始终是"假 ID"
- `streamingId` 是 `string | null`，不支持多分支并发流
- Buffer key 是 `conv_id`，无法按消息粒度恢复
- `ctx.stream_content_blocks` 与 Buffer 事件双源并行，存在状态偏移
- PostProcessStage 兼顾"块状态标记"和"持久化"，职责模糊
- `ActiveStreamTracker` 只追踪 `conv_id` 级活跃，不够细粒度

## 新架构设计

### 核心决策

1. **消息 ID 预分配**：pipeline 启动时（Stage 0）生成 msg_id + INSERT shell 消息（status=streaming）
2. **Buffer key = msg_id**：每个消息独立 buffer，事件按 msg_id 隔离
3. **活跃流发现**：`loadMessages` 返回 `status=streaming` 的消息，前端自动检测触发 replay，无需 GET /active 端点
4. **content_blocks 构建**：pipeline 完成时从 raw_events 用纯函数 `events_to_content_blocks()` 一次性合并（方案 C）
5. **DB 写入完成态**：仅 pipeline 完成时 UPDATE shell 消息（不流式写 DB）
6. **新增 status 列**：messages 表加 status VARCHAR(20) DEFAULT 'done'（streaming / done / orphaned）
7. **前端 streamingId 改为 Set<string>**：支持多消息并发流
8. **删除临时 ID 替换**：msg_id 从生到死不变

### 数据流

```
send:
  POST /message { action: "send" }
    → StreamingResponse 返回
    → 后台 pipeline 启动

      Stage 0 (InitStage):
        ├─ msg_id = "msg_" + uuid
        ├─ INSERT message (id=msg_id, role="assistant", status="streaming", content_blocks=[])
        └─ yield { type: "pending_msg", msg_id }
            → Buffer.raw_events.append + SSE 推送 { type: "pending_msg", msg_id, status: "streaming" }

      Stage 1-3 (classify → save_user → tool_loop):
        ├─ yield token/reasoning/tool_call/tool_result 事件
        │   → Buffer.publish(event)
        │     └─ raw_events.append + SSE(给实时前端)
        └─ (不再操作 ctx.stream_content_blocks)

      Stage 4 (PostProcessStage):
        ├─ raw = buffer.get_raw_events(msg_id)
        ├─ blocks = events_to_content_blocks(raw)    ← 纯函数, 无状态
        ├─ UPDATE message SET status='done', content_blocks=blocks WHERE id=msg_id
        └─ yield { type: "done", msg_id, status: "done" }

replay (刷新后恢复):
  1. loadMessages(convId) → 消息列表中包含 msg_C1 { status: "streaming", content_blocks: [] }
  2. 前端遍历 messages: msg_C1.status === "streaming"
     → streamingIds.add("msg_C1")
     → POST /message { action: "replay", pending_msg_id: "msg_C1" }
  3. 后端:
     → Buffer 有 msg_C1 entry → SSE 从 event 0 回放 + 实时
     → Buffer 无 entry → { type: "stream_ended", msg_id: "msg_C1" }
  4. 前端收到 stream_ended → 不做额外操作（消息在 DB 中已是最终态）
```

### Buffer 结构变化

```python
# 当前 (conv_id 级, 事件 + Buffer 两层)
StreamBuffer:
  key: conv_id
  - events: list[dict]          # 全量事件
  - subscribers: list[Queue]     # SSE 连接
  - pipeline_task: asyncio.Task

# 新 (msg_id 级, 纯 raw_events)
StreamBuffer:
  key: msg_id                    # ← 从 conv_id 改为 msg_id
  - raw_events: list[dict]       # ← 改名, 只存原始事件
  - subscribers: list[Queue]     # SSE 连接
  - pipeline_task: asyncio.Task
  - status: "streaming" | "done" | "error"

映射注册表 (新增):
  active_by_conv: dict[str, set[str]]   # conv_id → Set[msg_id], 用于清理
```

### events_to_content_blocks 纯函数

```python
def events_to_content_blocks(raw_events: list[dict]) -> list[dict]:
    """raw_events → content_blocks (merged)。

    规则:
    - 过滤控制事件: pending_msg, done, error, stage
    - 连续 token → 合并为一个 text 块
    - reasoning 块不做 status 标记（DB 只存最终态）
    - tool_call / tool_result 保持原序
    - tool_call 和 tool_result 保持分离（不做配对合并）
    """
```

### 前端变化

```typescript
// 当前
streamingId: string | null

// 新
streamingIds: Set<string>  // 活跃流消息 ID 集合
```

**触发时机：**
1. `send()` → 收到 `pending_msg` 事件 → `streamingIds.add(msg_id)`
2. `replay()` → 收到 `pending_msg` 事件 → `streamingIds.add(msg_id)`
3. `loadMessages()` → 遍历消息, `msg.status === "streaming"` → `streamingIds.add(msg_id)` + 自动 replay
4. `_handleDone()` → `streamingIds.delete(msg_id)` (无需 ID 替换)

### DB 变更

`messages` 表新增列:
```sql
ALTER TABLE messages ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'done';
```

值域: `streaming` | `done` | `orphaned`

### 清理项

1. 删除 `ctx.stream_content_blocks`（被 raw_events 替代）
2. 删除 `ActiveStreamTracker`（被 msg_id 级 Buffer 注册表替代）
3. 删除 `PostProcessStage` 中的 `_sync_user_answer_to_response_blocks`（？需确认）
4. 删除 `_handleDone` 的 ID 替换逻辑
5. 删除 `_append_block` / `_append_tool_to_stream` 中的 stream_content_blocks 写入
