# 对话系统前端设计文档

## 1. 组件架构

### 1.1 总览

```
learn/page.tsx (LearnPage)
├── NewPartitionDialog           — 新建分区模态框
├── SwitchBanner                 — 上下文切换提示横幅
├── MobileBottomSheet            — 移动端底部弹出面板
│   └── PartitionSidebar          — 侧栏树组件
├── PartitionSidebar              — 桌面端侧栏树组件
├── MessageList                   — 消息列表
│   ├── ResponseBlockRenderer     — 响应块渲染器
│   │   ├── TextBlock             — 文本块
│   │   ├── VideoBlockRouter      — 视频块 (嵌入/搜索结果)
│   │   ├── PracticeBlockRouter   — 练习题块 (交互式/被动式)
│   │   │   └── InlinePracticeBlock — 内联交互式练习
│   │   ├── ImageBlock            — 图片块
│   │   ├── AudioBlock            — 音频块
│   │   ├── MindMapBlock          — 思维导图块
│   │   ├── DocumentBlock         — 文档块
│   │   ├── MediaSearchBlock      — 媒资搜索结果
│   │   └── VideoEmbed            — 视频嵌入播放器
│   └── SpeakButton               — TTS 朗读按钮
└── ConversationChatInput         — 聊天输入框
    └── VoiceRecorder             — 语音录制器
```

### 1.2 子组件职责

| 组件 | 路径 | 职责 |
|------|------|------|
| **LearnPage** | `page.tsx` (1262行) | 主状态容器；WebSocket 管理；路由/URL 同步；所有事件处理器的定义地 |
| **PartitionSidebar** | `PartitionSidebar.tsx` | 树形导航（分区→领域→专题→对话）；懒加载子节点；内联重命名/删除/CURD 操作 |
| **MessageList** | `MessageList.tsx` | 消息渲染（用户/助手）；消息去重；内联编辑/版本切换/复制/删除；自动滚动 |
| **ConversationChatInput** | `ChatInput.tsx` | 文本输入；文件/图片上传；语音录制；Enter 发送 |
| **ResponseBlockRenderer** | `ResponseBlockRenderer.tsx` | 按 type + status 分发渲染不同类型的响应块 |
| **NewPartitionDialog** | `page.tsx` 内 | 新建分区模态框（名称 + emoji）|
| **SwitchBanner** | `page.tsx` 内 | 检测到上下文切换时提示用户确认切换会话 |
| **MobileBottomSheet** | `page.tsx` 内 | 移动端侧栏的底部弹出容器 |

---

## 2. 状态管理

所有状态集中在 `LearnPage` 组件中（~20 个 state 变量），子组件通过 props 接收数据和回调。

### 2.1 核心会话状态

| 变量 | 类型 | 默认值 | 用途 | 设置位置 | 消费位置 |
|------|------|--------|------|---------|---------|
| `partitions` | `Partition[]` | `[]` | 全部分区列表 | `loadPartitions()` (API fetch) | PartitionSidebar, 桌面 header |
| `selectedPartitionId` | `string \| null` | `null` | 当前选中的分区 ID | URL 恢复、handleSelectConversation、handleNewConversation、handleSend 中的 ensureConversation | PartitionSidebar (高亮), 消息加载, 桌面 header |
| `activeConversationId` | `string \| null` | `null` | 当前打开的对话 ID | URL 恢复、handleSelectConversation、handleNewConversation、handleSend | loadMessages, MessageList, ChatInput |
| `messages` | `TreeNode[]` | `[]` | 当前对话的消息列表 | `loadMessages()`, streaming onToken/onDone, handleSend | MessageList |
| `responseBlocks` | `ResponseBlock[]` | `[]` | 当前消息关联的响应块 | `loadMessages()` 遍历助理消息获取, WS onBlockUpdate/onDone | MessageList → ResponseBlockRenderer |
| `isLoading` | `boolean` | `false` | 是否正在等待 AI 回复 | handleSend (true), WS onDone/onError (false) | MessageList (显示加载动画), ChatInput (禁用) |
| `statusMessage` | `string` | `""` | 当前状态文本（如"正在思考..."） | WS onStatus, handleSend | MessageList 加载指示器 |

### 2.2 侧栏 & UI 状态

| 变量 | 类型 | 默认值 | 用途 |
|------|------|--------|------|
| `switchBanner` | `{ partitionId, conversationId, domainName, topicName } \| null` | `null` | WebSocket context_switch 通知时显示提示横幅 |
| `showPartitionSidebar` | `boolean` | `false` | 移动端侧栏弹窗开关 |
| `sidebarCollapsed` | `boolean` | `false` | 桌面端侧栏折叠状态 |
| `showNewPartition` | `boolean` | `false` | 新建分区对话框开关 |
| `loadingPartitions` | `boolean` | `true` | 分区数据加载中 |
| `isLoadingPartitions` | `boolean` | `true` | 分区加载中（用于时机控制） |
| `loadingMessages` | `boolean` | `false` | 消息加载中 |
| `convError` | `string \| null` | `null` | 对话加载错误信息 |

### 2.3 Stream 缓冲区 (refs)

| 变量 | 类型 | 用途 |
|------|------|------|
| `streamBufferRef` | `string` | 累积流式 token 文本 |
| `streamingMsgIdRef` | `string \| null` | 当前正在流的助手消息 ID |
| `streamingContextRef` | `{ partitionId, conversationId } \| null` | 当前流对应的分区+对话上下文（用于验证流数据是否仍然有效） |

### 2.4 URL/恢复状态

| 变量 | 类型 | 默认值 | 用途 |
|------|------|--------|------|
| `urlInitialized` | `boolean` | `false` | 标记 URL 参数是否已恢复（防止初始化前触发的副作用） |

---

## 3. 事件流程

### 3.1 `handleNewConversation` — 新建对话

**触发位置**: PartitionSidebar 的"新建会话"按钮（分区/领域/专题级）

**完整流程**:
1. **参数**: `level` (`"default"` | `"partition"` | `"domain"` | `"topic"`) + `parentId`
2. **`level === "default"`**: 无选中分区 → 使用第一个分区或创建默认分区，然后递归调用 `handleNewConversation("partition", pId)`
3. **`level === "topic"`**: 直接使用 `parentId` 作为 `topicId`
4. **其他 level**: 根据 level 调用对应 API 获取子节点列表
   - `"partition"` → `GET /partitions/{id}/domains` → 取第一个 domain → `GET /domains/{id}/topics`
   - `"domain"` → `GET /domains/{id}/topics` → 取第一个 topic
   - 如果列表为空，自动创建默认层级链
5. **创建对话**: `POST /conversations/conversations` 传入 `topic_id`
6. **状态更新**: `setActiveConversationId(新ID)`，桌面端保持当前 `selectedPartitionId`
7. **刷新侧栏**: `loadPartitions()` (通过 `onTreeChanged` 回调)
8. **移动端**: `setShowPartitionSidebar(false)` 关闭侧栏

### 3.2 `handleSelectConversation` — 选择对话

**触发位置**: PartitionSidebar 点击 conversation 节点

**流程**:
```
handleSelectConversation(partitionId, conversationId)
  → setSelectedPartitionId(partitionId)
  → setActiveConversationId(conversationId)
  → setConvError(null)
  → setShowPartitionSidebar(false)    // 移动端关闭侧栏
  → setSwitchBanner(null)             // 清除上下文切换横幅
```

**副作用**: `useEffect` 依赖 `activeConversationId` 自动触发 `loadMessages()`。

### 3.3 `handleSend` — 发送消息

**触发位置**: ConversationChatInput 的发送按钮 / Enter 键

**完整流程**:
```
handleSend(text, files?)
  ├─ guard: if (!text.trim() || isLoading) return
  │
  ├─ ensureConversation():
  │   ├─ 已有 selectedPartitionId + activeConversationId → 直接返回
  │   ├─ 无 partition → 选第一个/创建默认分区
  │   ├─ 无 domain → 创建默认领域
  │   ├─ 无 topic → 创建默认专题
  │   └─ 无 conversation → POST 创建对话，更新 selectedPartitionId + activeConversationId
  │
  ├─ 构建用户消息 TreeNode (临时 id)
  ├─ setMessages([...prev, userMsg])       // 立即显示用户消息
  ├─ setIsLoading(true)
  ├─ setStatusMessage("正在思考...")
  │
  ├─ 构建占位助手消息 (临时 id + 空内容)
  ├─ streamingMsgIdRef.current = assistantMsgId
  ├─ streamingContextRef.current = { partitionId, conversationId }
  ├─ setMessages([...prev, assistantPlaceholder])
  │
  ├─ sendWSMessage({ text, partition_id, conversation_id })
  │   └─ 如果 WS 未连接 → HTTP 回退 POST /api/conversations/message
  └─ WS onDone/onError 负责设置 isLoading=false, statusMessage=""
```

### 3.4 `handleStream` — WebSocket 流式处理

WS 消息通过 `connectConversationWS()` 注册的 6 个回调处理：

```
onStatus(msg)
  → setStatusMessage(msg)

onToken(content, blockId?)
  → 验证 streamingContextRef 与当前 selectedPartitionId + activeConversationId 一致
  → streamBufferRef.current += content
  → 根据 streamingMsgIdRef 更新 messages 中的对应项 (text_summary + content_blocks)

onDone(partitionId, assistantMessage)
  → setIsLoading(false); setStatusMessage("")
  → 清除 streamingContextRef
  → 验证上下文是否仍然有效；无效则删除流式占位消息
  → 用 assistantMessage 替换占位消息（含空回复兜底）
  → setTimeout: 300ms 后 loadPartitions()
  → setTimeout: 500ms 后 loadMessages() 刷新确保数据一致

onError(msg)
  → setIsLoading(false); setStatusMessage("")
  → 将流式占位消息替换为错误消息节点（含 ❌ 前缀）
  → 清除 stream refs

onBlockUpdate(block)
  → setResponseBlocks (更新已存在/追加新块)

onContextSwitch(data)
  → setSwitchBanner({ partitionId, conversationId, domainName, topicName })
```

### 3.5 `loadPartitions` — 加载分区列表

```typescript
loadPartitions()
  → setLoadingPartitions(true); setIsLoadingPartitions(true)
  → GET /api/conversations/partitions
  → setPartitions(data.partitions || [])
  → finally: 两个 loading 状态都置 false
```

**触发时机**: 组件挂载 (`useEffect`)、新建/删除/重命名分区后、流完成刷新。

### 3.6 `loadMessages` — 加载消息

```typescript
loadMessages(conversationId)
  → 清除 stream refs (streamingMsgIdRef, streamBufferRef, streamingContextRef)
  → setLoadingMessages(true)
  → GET /api/conversations/conversations/{id}/messages?limit=50&offset=0
  → setMessages(data.messages || [])
  → 对每条 assistant 消息:
      GET /api/conversations/messages/{msgId}/blocks
      → 收集所有 blocks → setResponseBlocks(allBlocks)
  → catch: 根据错误码设置 convError (404→已删除, 403/401→无权限, 其他→加载失败)
  → finally: setLoadingMessages(false)
```

**触发时机**: `activeConversationId` 变化时 (`useEffect`)，以及每 30 秒轮询。

### 3.7 消息编辑/版本切换

**编辑 (`handleEditMessage`)**:
```
PUT /api/conversations/messages/{msgId}
  body: { content_blocks: [{ type: "text", text: newText }], text_summary: newText }
  → 返回 version_count
```

**版本切换 (`handleVersionSwitch`)**:
```
GET /api/conversations/messages/{msgId}  → 获取 versions 列表
  → 计算前一个/后一个版本的 index
  → GET /api/conversations/messages/{targetVersionId}
  → 用目标版本的内容替换当前消息（保持 id 不变）
  → 返回 { index, total }
```

---

## 4. 侧栏树结构

### 4.1 树状态类型

```
PartitionItem (partition)
  ├── DomainItem (domain)
  │   ├── TopicItem (topic)
  │   │   ├── ConversationItem (conversation)
  │   │   └── ...more conversations
  │   └── ...more topics
  ├── ...more domains
  └── ...more partitions
```

每个节点共用 `TreeItemCommon`:
```typescript
interface TreeItemCommon {
  level: "partition" | "domain" | "topic" | "conversation";
  expanded: boolean;
  loading: boolean;
}
```

### 4.2 数据加载策略

- **分区列表**: 从父组件通过 `partitions` props 传入，`PartitionSidebar` 将其映射为 `PartitionItem[]`（保留展开状态）
- **子节点懒加载**: `toggleExpand` 时触发 `loadChildren()`：
  - Partition 展开 → `GET /partitions/{id}/domains` → 构建 `DomainItem[]`
  - Domain 展开 → `GET /domains/{id}/topics` → 构建 `TopicItem[]`
  - Topic 展开 → `GET /topics/{id}/conversations` → 构建 `ConversationItem[]`
  - Conversation 点击 → 触发 `onSelectConversation`，不展开

### 4.3 自动展开路径

当 `activeConversationId` 变化时，`PartitionSidebar` 自动展开到目标对话的完整路径：

1. 展开目标分区加载 domains
2. 展开所有 domains 加载 topics
3. 展开所有 topics 加载 conversations
4. 递归查找目标对话 ID，沿途设置 `expanded: true`

### 4.4 树 CRUD 操作

| 操作 | 方法 | API |
|------|------|-----|
| 创建子节点 | `handleCreate` | `POST /partitions/{id}/domains`, `/domains/{id}/topics`, `/conversations` |
| 重命名 | `confirmEdit` | `PATCH /{level}/{id}` |
| 删除 | `confirmDelete` | `DELETE /{level}/{id}` |
| 本地树更新 | `renameInTree`, `removeFromTree`, `updateTreeChildren` | — |

---

## 5. WebSocket 连接

### 5.1 连接生命周期

```
connectConversationWS(callbacks)
  → 如果已有连接且 OPEN → 复用
  → new WebSocket(`ws[s]://{host}/api/conversations/ws`)
  → 注册 onopen / onmessage / onerror / onclose
```

**初始化时机**: `LearnPage` 挂载时 `useEffect`，依赖 `[activeConversationId, loadMessages, loadPartitions, selectedPartitionId]`。

**清理时机**: `useEffect` 返回 `disconnectWS()` 在组件卸载时关闭连接。

### 5.2 连接状态

| 事件 | 行为 |
|------|------|
| `onopen` | 重置重连尝试计数 |
| `onclose` | 设置定时器，指数退避重连（1s → 2s → 4s → ... → 最大 30s） |
| `onerror` | 静默处理（onclose 处理重连） |
| `disconnectWS()` | 清除重连定时器，设置 `ws.onclose = null` 阻止重连 |

### 5.3 消息格式

**发送**:
```typescript
sendWSMessage({
  text: string,                     // 用户输入的文本
  partition_id?: string,
  conversation_id?: string,
})
```

**接收** (通过 `WSIncomingMessage` 联合类型分发):

| `type` | 处理逻辑 |
|--------|---------|
| `status` | 更新底部状态栏文本 |
| `token` | 追加到流缓冲区，更新 message 列表 |
| `tool_block` | 存入/更新 responseBlocks |
| `done` | 完成流，替换占位消息，刷新分区和消息 |
| `error` | 替换为错误节点 |
| `block_update` | 同 tool_block |
| `context_switch` | 显示切换横幅 |
| `user_message` | 忽略（已在前端显示） |
| `pong` | 忽略（心跳） |

### 5.4 回退机制

如果 WS 未连接（`sendWSMessage` 返回 `false`），自动回退到 HTTP POST：

```
POST /api/conversations/message
  body: { text, partition_id, conversation_id }
  → 解析 response 中的 assistant_message
  → 更新占位消息
```

---

## 6. URL 状态恢复

### 6.1 URL 参数

```
/learn?p={partitionId}&c={conversationId}
/learn?partition_id={partitionId}&conversation_id={conversationId}   // 兼容格式
/learn?panel=graph                                                   // 重定向到知识图谱
```

### 6.2 恢复流程

1. **组件挂载后** (`useEffect`):
   - 解析 `window.location.search`
   - 若 `p` 或 `partition_id` 存在 → `setSelectedPartitionId(pId)`，若有 `c` → `setActiveConversationId(cId)`
   - 否则检查 `localStorage.getItem("learn-page-state")` → 恢复上次的分区和对话
   - 设置 `urlInitialized = true`

2. **同步 URL + localStorage** (第二个 `useEffect`):
   - 依赖: `[selectedPartitionId, activeConversationId, urlInitialized]`
   - URL 参数变化 → `window.history.replaceState()` 更新地址栏
   - `localStorage.setItem("learn-page-state", JSON)`

3. **验证** (第三个 `useEffect`):
   - 分区加载完成后，检查 `selectedPartitionId` 是否在 `partitions` 中存在
   - 如不存在（已被删除）→ 清除选择和 URL params

4. **panel=graph 重定向**:
   - 组件挂载时检测 `panel=graph` → `router.replace('/dashboard?tab=graph&partition_id=...')`

---

## 7. 移动端 vs 桌面端

### 7.1 判断方式

```typescript
const isDesktop = useMediaQuery("(min-width: 768px)");
```

使用自定义 `useMediaQuery` hook 监听 CSS media query 变化。

### 7.2 移动端布局 (`!isDesktop`)

```
┌──────────────────────────┐
│ [Menu]  分区标题          │  ← 顶部导航栏 (border-bottom)
├──────────────────────────┤
│ (SwitchBanner)           │  ← 上下文切换横幅（可选）
│ (convError)              │  ← 错误提示（可选）
│                          │
│    MessageList           │  ← 可滚动消息区域 (flex-1)
│                          │
├──────────────────────────┤
│    ChatInput              │  ← 输入框（固定在底部）
└──────────────────────────┘

点击 Menu → 弹出 MobileBottomSheet:
┌──────────────────────────┐
│  导航              [X]   │  ← 半透明背景 + 底部弹出，max-h-[70vh]
├──────────────────────────┤
│  PartitionSidebar        │  ← 可滚动树
└──────────────────────────┘
```

- 使用 `fixed inset-0` + `bottom: var(--bottom-nav-height)` 全屏覆盖
- 侧栏作为底部弹出层（`MobileBottomSheet`），选择对话后自动关闭

### 7.3 桌面端布局 (`isDesktop`)

```
┌────────────┬──────────────────────────────┐
│  ← 驾驶舱   │  🤖 Bot emoji 分区名          │
│  [+][+][◀] │                              │
│ (260px)    │  (SwitchBanner)              │
│            │  (convError)                 │
│ Partition  │                              │
│ Sidebar    │     MessageList              │
│ (树形导航,  │                              │
│  compact)  │                              │
│            ├──────────────────────────────┤
│            │     ChatInput                 │
└────────────┴──────────────────────────────┘
```

- 固定 260px 侧栏宽度，可折叠（`sidebarCollapsed`）
- 侧栏包含返回驾驶舱链接 + 新建会话/分区/折叠按钮
- 分区树使用 `compact` 模式（隐藏侧栏自身 header）

### 7.4 响应式差异总结

| 特性 | 移动端 | 桌面端 |
|------|--------|--------|
| 侧栏 | 底部弹出层 (MobileBottomSheet) | 固定 260px 左侧面板 |
| 侧栏折叠 | 不可用 | 可折叠/展开 (动画) |
| 选择对话后 | 自动关闭侧栏 | 侧栏保持打开 |
| 顶部标题 | 分区名 | Bot 图标 + 分区名 |
| 新建分区按钮 | 侧栏内触发 → 全局 dialog | 侧栏 header 内按钮 |
| 返回驾驶舱 | 无（通过底部导航） | ChevroneLeft 链接 |

---

## 8. 周期轮询

```typescript
// 每 30 秒轮询当前对话的消息
useEffect(() => {
  if (!activeConversationId) return;
  const interval = setInterval(() => {
    loadMessages(activeConversationId);
  }, 30000);
  return () => clearInterval(interval);
}, [activeConversationId, loadMessages]);
```

---

## 9. 消息去重机制

`MessageList` 中通过 `dedupedMessages` 对消息进行去重：

1. **反向遍历**：从后往前，让后面的（最终）版本覆盖前面的（流式中间）版本
2. **同 ID 处理**：优先保留有内容的版本（有 `text` 的非空版本覆盖空版本）
3. **排除已删除**：`m.is_deleted` 的条目跳过

---

## 附录: 核心 API 端点汇总

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/conversations/partitions` | 获取所有分区 |
| POST | `/api/conversations/partitions` | 创建分区 |
| PATCH | `/api/conversations/partitions/{id}` | 重命名分区 |
| DELETE | `/api/conversations/partitions/{id}` | 删除分区 |
| GET | `/api/conversations/partitions/{id}/domains` | 获取分区下的领域 |
| POST | `/api/conversations/domains` | 创建领域 |
| GET | `/api/conversations/domains/{id}/topics` | 获取领域下的专题 |
| POST | `/api/conversations/topics` | 创建专题 |
| GET | `/api/conversations/topics/{id}/conversations` | 获取专题下的对话 |
| POST | `/api/conversations/conversations` | 创建对话 |
| GET | `/api/conversations/conversations/{id}/messages` | 获取对话的消息列表 |
| GET | `/api/conversations/messages/{id}` | 获取单条消息（含版本信息）|
| PUT | `/api/conversations/messages/{id}` | 编辑消息 |
| DELETE | `/api/conversations/messages/{id}` | 删除消息 |
| GET | `/api/conversations/messages/{id}/blocks` | 获取消息的响应块 |
| POST | `/api/conversations/message` | HTTP 发送消息（WS 回退） |
| WS | `/api/conversations/ws` | WebSocket 流式对话 |
| POST | `/api/conversations/workspace/upload` | 上传文件（转 workspace 素材）|
