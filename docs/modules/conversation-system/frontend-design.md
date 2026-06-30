# 对话系统 · 前端设计

> 基于 Zustand Store + SSE StreamPipeline + Block Renderer Registry 的组件架构。
> 源码: [frontend/src/store/conversation/](../../../frontend/src/store/conversation/) | [frontend/src/components/conversation/](../../../frontend/src/components/conversation/)

---

## 组件架构

```
ConversationPage
├── ConversationPanel
│   ├── PartitionSidebar       — 树形目录侧栏（DirectoryNode 树）
│   ├── MessageList            — 消息列表
│   │   └── Block Renderer Registry    — type→组件查表渲染
│   │       ├── ToolCallBlock          — 工具调用卡片（三态）
│   │       ├── ReasoningBlock          — 推理过程（可折叠）
│   │       ├── TextRenderer           — 文本内联渲染
│   │       ├── ImageBlock             — 图片
│   │       ├── FileBlock              — 文件
│   │       └── QuoteBlock             — 引用
│   ├── ConversationChatInput   — 聊天输入框
│   └── SwitchBanner            — 上下文切换提示
```

---

## 状态管理 (Zustand)

### conversation-store.ts — 根 Store

| 状态 | 类型 | 说明 |
|------|------|------|
| `messages` | `MessageNode[]` | 所有消息 |
| `activeConversationId` | `string\|null` | 当前活跃会话 ID |
| `selectedNode` | `{id, level, parent}` | 侧边栏选中节点 |
| `isLoading` | `boolean` | 是否正在加载 |
| `statusMessage` | `string` | 状态提示文本 |
| `postSendRedirect` | `string\|null` | 发送后跳转 |

| Action | 说明 |
|--------|------|
| `sendMessage(text, files)` | Phase 1 创建会话 → Phase 2 发送消息 |
| `loadMessages(cId)` | 从 REST 加载历史消息 |
| `loadDirList()` | 刷新侧边栏目录树 |

### tree-store.ts — 目录树 Store

| 状态 | 说明 |
|------|------|
| `rootId` | 根目录节点 ID |
| `childMap` | `Map<string, Children[]>` 子节点缓存 |
| `directoryNodes` | 扁平节点列表 |

| Action | 说明 |
|--------|------|
| `loadRootNodes()` | 加载根级目录 |
| `loadChildren(parentId)` | 加载子节点 |
| `selectNode(id)` | 选中节点并展开路径 |

### pipeline/setup.ts — SSE 桥接层

12 个事件 subscriber，将 SSE 事件流映射到 Store：

| SSE 事件 | Store 操作 |
|----------|-----------|
| `token` | 追加文本到当前 assistant 消息的 text block |
| `tool_calls` | 插入 ToolBlock[](status:pending) 到 content_blocks |
| `tool_call_update` | 更新 ToolBlock status:pending→running |
| `block_update` | 更新 ToolBlock status:running→done + result_content |
| `reasoning` | 追加到 ReasoningBlock |
| `done` | 替换消息 ID + 合并最终 response_blocks |
| `error` | 创建 error 消息节点 |
| `context_switch` | 通知栏提示 |
| `tree_recommendation` | 通知栏提示 |
| `phase_change` | 更新 isLoading/wsConnected |

---

## Block Renderer Registry

消息渲染通过查表实现，而非 if/else 链：

```typescript
const BLOCK_RENDERERS: Record<string, React.ComponentType<any> | null> = {
  tool:     ToolCallBlock,    // 工具调用卡片（pending/running/done）
  reasoning: ReasoningBlock,   // 推理过程（可折叠）
  text:     null,             // 文本由 MessageList 内联处理
  image:    ImageBlock,
  file:     FileBlock,
  quote:    QuoteBlock,
}
```

渲染时遍历 `content_blocks`，按 `type` 查表渲染。新增 block 类型只需注册一行。

---

## 发消息完整流程

```
sendMessageImpl(text, files):
│
├─ 防重复：isLoading 时跳过
│
├─ Phase 1: ensureAndSelectConversation()
│   ├─ GET  /tree/directory                 → 查临时目录
│   ├─ POST /tree/directory                 → 创建临时目录（如没有）
│   ├─ GET  /tree/directory?parent_id=pId   → 查空会话（优先复用）
│   ├─ POST /tree/directory                 → 创建会话（如没有空会话）
│   ├─ loadRootNodes() + loadChildren()     → 刷新侧边栏
│   ├─ loadDirList()                        → 更新目录列表
│   └─ set({ selectedNode, postSendRedirect }) → 选中会话
│
├─ Phase 2: 发送
│   ├─ beginStream(cId, pId, asstId)        → SSE 长连接
│   ├─ 乐观写入（user msg + assistant 占位符）
│   ├─ set({ isLoading: true })
│   └─ POST /tree/conversation/{cId}/message → 触发后端
│                                           → SSE 事件实时更新
```

---

## SSE 流协议

传输: Line-delimited JSON (EventSource 兼容)

```
type: <event_type_id>
id: <seq_num>
data: <json>

```

事件类型:

| ID | 事件 | 数据 | 说明 |
|----|------|------|------|
| 0 | `token` | `{type:"text", text, agent_label?}` | 流式文本 |
| 1 | `tool_calls` | `{tool_calls: [{id, name, args}]}` | 工具调用宣告 |
| 2 | `tool_call_update` | `{tool_call_id, status:"running"}` | 工具状态切换 |
| 3 | `block_update` | `{type, block: ToolBlock}` | 工具执行结果 |
| 4 | `reasoning` | `{content, signature?}` | 推理过程 |
| 5 | `done` | `{assistant_message, response_blocks}` | 完成 |
| 6 | `error` | `{code, message}` | 错误 |
| 7 | `phase_change` | `{phase}` | 阶段切换 |

断线重连: 服务端每条事件带 `id:`，浏览器 `EventSource` 断开时自动发 `Last-Event-ID` 头，服务端从断点回放。

---

## 目录结构

```
frontend/src/
├── store/
│   ├── conversation/
│   │   ├── conversation-store.ts      — 根 Store
│   │   ├── message-store.ts           — 消息 Store
│   │   ├── tree-store.ts              — 目录树 Store
│   │   ├── tree-helpers.ts            — API 工具函数
│   │   ├── setup.ts                   — SSE 桥接 (pipeline/setup.ts)
│   │   └── actions/
│   │       └── send-message.ts        — 发消息 action
│   │       └── tree-ops.ts            — 树操作 action
│   └── pipeline/
│       ├── StreamPipeline.ts          — SSE 连接管理
│       ├── SSESource.ts               — EventSource 封装
│       └── setup.ts                   — 事件 subscriber 注册
│
├── components/
│   └── conversation/
│       ├── core/
│       │   ├── ConversationPanel.tsx   — 主面板
│       │   ├── MessageList.tsx         — 消息列表（含 Registry）
│       │   ├── ConversationChatInput.tsx — 输入框
│       │   └── PartitionSidebar.tsx    — 侧边栏
│       └── blocks/
│           ├── registry.ts            — Block Renderer 注册表
│           ├── ToolCallBlock.tsx       — 工具调用卡片
│           ├── ReasoningBlock.tsx      — 推理过程
│           ├── ImageBlock.tsx
│           └── FileBlock.tsx
│
└── hooks/
    └── conversation/
        └── useConversation.ts          — 页面级 hook
```
