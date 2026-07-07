# 对话系统简化架构

> 状态: 已完成 | 日期: 2026-07-07
> 原则: 服务端为唯一真相源，前端不做比服务端更聪明的状态推断

---

## 一、删除的概念

| 概念 | 原代码量 | 删除原因 |
|---|---|---|
| `load_state` 五态机 (placeholder/loading/loaded/broken/streaming) | ~80 行 | 一次性加载全部消息，不逐条懒加载 |
| `_loadingInFlight` / `_loadingPromises` / `_loadAttempted` | ~30 行 | 无懒加载则无并发控制 |
| `loadFullContent` / `loadVisibleContent` / `retryLoadContent` | ~120 行 | 无懒加载 |
| `hasFullContent` 判断 | ~20 行 | 无懒加载 |
| `sending` 锁 / `pathReady` 守卫 | ~30 行 | 等后端确认，无需前端锁 |
| 乐观写入 (临时 ID `t_`/`a_`/`err-`) | ~80 行 | 等 `pending_msg` 事件再追加 |
| `replaceMessageIdInState` / `isTempMessage` | ~40 行 | 无临时 ID |
| `generationRef` / `stoppedRef` / `sendPromiseRef` / `replayPromiseRef` | ~30 行 | 简化为 AbortController |
| 首尾分片加载 (`head=`/`tail=`) | ~30 行 | 一次性全量加载 |
| `fillAncestorPath` (单次链式补齐) | ~80 行 | 全量加载后本地计算路径 |
| `calcPath` (异步回溯+补齐) | ~60 行 | 全量加载后本地计算路径 |
| `replay` (重连流) | ~40 行 | 刷新页面→重新加载全部消息 |

**总计删除约 640 行** (~80% of message-store.ts + ~50% of useChatStream.ts)

---

## 二、新架构

### 2.1 数据流

```
页面加载
  │
  ├─ GET /tree/conversation/{convId}/messages?all=true
  │   → 返回全部消息 (MessageNode[])
  │   → 写入 nodeMap + 计算 currentPath
  │
  └─ 渲染 MessageList

用户发消息
  │
  ├─ POST /tree/conversation/{convId}/message { action:"send", text }
  │   (fetch + ReadableStream)
  │
  ├─ SSE 事件流:
  │   pending_msg → 追加 user + assistant 到 messages[] + currentPath
  │   token       → 追加文本到最后一个 assistant 消息
  │   tool_calls  → 插入 tool block
  │   done        → 完成
  │   error       → 显示错误
  │
  └─ stop → AbortController.abort()

分支切换
  │
  ├─ switchBranch(msgId) → 本地计算新 currentPath
  │   └─ nodeMap 有全部消息，回溯 parent_id 即可
  │
  └─ setCurrentPath(newPath) → _rebuildMessages()

版本切换 (上一版本/下一版本)
  │
  ├─ 逻辑不变: parent_id::role 分组
  │   └─ 基于 nodeMap，不依赖懒加载
  │
  └─ navigateVersion(msgId, direction)
```

### 2.2 Store 结构 (精简后)

```typescript
interface MessageState {
  // 数据
  nodeMap: Record<string, MessageNode>;    // 全部消息索引
  currentPath: string[];                   // 当前活跃路径
  messages: MessageNode[];                 // 当前路径的渲染列表

  // UI 状态
  streamingId: string | null;              // 当前流式消息 ID
  isLoading: boolean;                      // 是否正在加载会话
  convError: string | null;                // 加载错误

  // Actions
  loadConversation(convId: string): Promise<void>;
  sendMessage(text: string, convId: string, dirId: string): Promise<void>;
  stopGeneration(): void;
  switchBranch(msgId: string): void;
  navigateVersion(msgId: string, direction: "prev" | "next"): void;
  deleteMessage(msgId: string): Promise<void>;
  editMessage(msgId: string, newText: string): Promise<void>;
}
```

### 2.3 SSE 处理 (精简后)

```typescript
// 不再需要 dispatchEvent 的 17 种 switch-case
// 不需要 load_state 状态机
// 不需要 generation 追踪
// 不需要 stopped 标志位

function useChatStream() {
  const abortRef = useRef<AbortController | null>(null);

  const send = async (text: string, convId: string, dirId: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const res = await fetch(`/api/.../${convId}/message`, {
      method: "POST",
      body: JSON.stringify({ action: "send", text, dir_id: dirId }),
      signal: controller.signal,
    });

    const reader = res.body!.getReader();
    // 逐行 SSE 解析 → 直接写 Zustand store
    // 事件类型: pending_msg / token / tool_calls / done / error
    // 其他事件忽略或分流到对应的 store
  };

  const stop = () => {
    abortRef.current?.abort();
    // POST { action: "stop" } 通知后端
  };

  return { send, stop };
}
```

### 2.4 分支导航 (保留，简化)

```typescript
// 全量加载后，nodeMap 有全部消息 → 本地计算路径
switchBranch: (msgId: string) => {
  const { nodeMap } = get();
  const path: string[] = [];
  let cur = nodeMap[msgId];
  while (cur) {
    path.unshift(cur.id);
    cur = cur.parent_id ? nodeMap[cur.parent_id] : null;
  }
  // 沿长子链补齐 descendants
  cur = nodeMap[msgId];
  while (cur) {
    const children = Object.values(nodeMap).filter(
      n => n.parent_id === cur!.id && !n.is_deleted
    );
    cur = _getDefaultChildByVersion(children);
    if (cur && !path.includes(cur.id)) path.push(cur.id);
  }
  get().setCurrentPath(path);
}

// 版本切换: 基于 nodeMap 做兄弟查找
navigateVersion: (msgId: string, direction: "prev" | "next") => {
  const { nodeMap } = get();
  const msg = nodeMap[msgId];
  const siblings = Object.values(nodeMap)
    .filter(n => n.parent_id === msg.parent_id && n.role === msg.role && !n.is_deleted)
    .sort((a, b) => a.version - b.version);
  const idx = siblings.findIndex(s => s.id === msgId);
  const target = direction === "prev" ? siblings[idx - 1] : siblings[idx + 1];
  if (target) get().switchBranch(target.id);
}
```

### 2.5 后端改动

**新增 API**:
```
GET /tree/conversation/{convId}/messages?all=true
  → 返回 conv_message_ids 中全部消息 (不含 deleted)
```

**现有 API 不变**:
- `POST /tree/conversation/{convId}/message` (SSE 流)
- `POST /tree/conversation/{convId}/tool-result` (工具恢复)
- `GET /tree/message/{messageId}` (单条消息 — 保留但前端不再调用)
- 后端 pipeline 不变 (已有修复)

---

## 三、迁移步骤

### Step 1: 后端 API (10 分钟)
1. 在 `conversation_routes.py` 加 `GET /messages?all=true` 端点
2. 返回 `conv_message_ids` 中全部消息

### Step 2: 前端 store 重写 (30 分钟)
1. 新建 `message-store-v2.ts` (约 200 行)
2. `loadConversation` → 一次性 GET all messages
3. `sendMessage` → POST + SSE 流处理
4. `switchBranch` / `navigateVersion` → 本地计算
5. 删除 `load_state`、loading 控制、乐观写入

### Step 3: 组件适配 (20 分钟)
1. `MessageList.tsx` → 去掉 `getLoadStatus` / `loadFullContent` 调用
2. `MessageItem.tsx` → 去掉 `loadState` props
3. `conversation/page.tsx` → 调用 `loadConversation` (替代 `loadMessages`)

### Step 4: 清理 (10 分钟)
1. 删除 `message-store.ts` 旧代码
2. 删除 `useChatStream.ts` 中的 send/replay 旧逻辑
3. 删除 `message-factory.ts` 中的临时 ID 工厂函数

### Step 5: 验证
1. 发消息 → 流式回复 → 停止 → 分支切换 → 刷新恢复