# Task — Conversation 前端优化（性能 / UI / 移动端 / E2E）

> 日期：2026-07-04
> 状态：✅ Part B + Part C 完成（详见 docs/modules/conversation-system/frontend-design.md）
> 范围：仅前端（`frontend/src/app/conversation/`、`frontend/src/components/conversation/`、`frontend/src/store/conversation/`）+ 浏览器 E2E
> 后端端点（44 个）本次不动

## Part B 完成清单

- [x] 安装 `react-virtuoso`
- [x] 提取 `MessageItem.tsx` 独立组件 + React.memo
- [x] `MessageList.tsx` 改用 Virtuoso（followOutput + atBottomStateChange + rangeChanged）
- [x] `FlatConversationList.tsx` 改用 Virtuoso
- [x] `StudySidebar.tsx` 容器 `overflow-hidden` 适配 Virtuoso
- [x] `SidebarTreeNode.tsx` React.memo + 自定义比较
- [x] `EmptyState` / `Skeleton` / `Toast` 三态统一（修复 4 处 named import → default import）
- [x] 添加 6 个 `data-testid` 锚点
- [x] viewport meta（已有）、safe-area（已有）、MobileBottomSheet swipe（已有）

## Part C 完成清单

- [x] 安装 `@playwright/test`
- [x] `playwright.config.ts`（3 project：desktop/tablet/mobile）
- [x] `e2e/helpers.ts`（API 登录 + localStorage 注入）
- [x] `e2e/conversation.spec.ts`（16 个用例，10 desktop + 5 mobile + 1 tablet）
- [x] 测试账号 `e2euser01` / `e2eTest1234`（首次运行自动注册）

## 原始摸底（Part A）

### 1.1 页面（Next.js）

| 路径 | 文件 | 职责 |
|------|------|------|
| `/conversation` | `frontend/src/app/conversation/page.tsx` | 主对话页面，client component，挂 `ErrorBoundary` + `ConversationPanel` |
| `/conversation` (loading) | `frontend/src/app/conversation/loading.tsx` | Next.js Suspense fallback → `ChatSkeleton` |

### 1.2 组件（58 个 TSX/TS）

| 子目录 | 文件数 | 关键文件（按行数排） |
|--------|--------|---------------------|
| `core/` | 8 | **MessageList.tsx (618, 优化后)** / **MessageItem.tsx (新增)** / ConversationPanel.tsx (393) / ChatInput.tsx (356) / ConversationMessageArea.tsx / MessageActions / MessageEditArea / StreamingControls |
| `blocks/` | 23 | **QuestionBlock.tsx (1058)** / KnowledgeExplainCard (134) / InlinePracticeBlock / PracticeSetBlock / SecretarySuggestionsBlock / ToolCallBlock / MarkdownRenderer / MediaSearchBlock / SubMessageCard / SelectionCard / SelfExplainCard / NoteCard / registry / ResponseBlockRenderer / … |
| `panels/` | 5 | FocusModePanel (358) / FlatConversationList (351) / StudySidebar (157) / GraphPanel / MobileBottomSheet (149) |
| `banners/` | 5 | KnowledgeTreeRecommendBanner / SwitchBanner / SocraticFollowUpBar / SubBranchBanner / ErrorBanner |
| `input/` | 4 | VoiceRecorder (340) / ResourcePicker / TextSelectionToolbar / QuotePreview |
| `tree/` | 4 | SidebarTreeNode (350) / TreeBreadcrumb / NodePathBreadcrumb / DirPicker |
| `media/` | 2 | SpeakButton / VideoEmbed |
| `cards/` | 4 | KnowledgeExplainCard / SelectionCard / SelfExplainCard / NoteCard |
| `hooks/` | 3 | useTextSelection (370) / useSocraticMode / useConversation |

**总计：58 个文件**（含 1 个非组件 hooks 子目录）

### 1.3 状态管理（Zustand）

#### `useConversationStore`（coordinator，11 个 UI 标志 + 5 个 actions 子集）

| 字段 | 类型 | 用途 |
|------|------|------|
| `selectedNode` | `SelectedNode` | 当前选中节点（id, level, parent, path），所有导航状态唯一来源 |
| `urlInitialized` | `boolean` | URL 恢复完成标志 |
| `sidebarMode` | `"tree"\|"flat"` | 侧边栏模式（持久化到 localStorage） |
| `dirList` | `DirInfo[]` | 一级目录列表 |
| `loadingDirList` | `boolean` | 目录列表加载中 |
| `showDirSidebar` | `boolean` | 移动端侧边栏抽屉显示状态 |
| `sidebarCollapsed` | `boolean` | 桌面端侧边栏折叠（持久化） |
| `showNewDir` | `boolean` | 新建目录对话框显示 |
| `isLoading` | `boolean` | 正在流式生成 |
| `statusMessage` | `string` | 流式生成时的状态文字 |
| `replyingToId` | `string\|null` | 当前正在回复的消息 ID |
| `switchBanner` | `SwitchBanner\|null` | 上下文切换提示 |
| `recommendationBanner` | `RecommendationBanner\|null` | 知识树推荐提示 |
| `wsConnected` | `boolean` | SSE 连接状态（占位） |
| `pendingQuote` | `Quote\|null` | 引用块（待发送） |
| `isInSubBranch` | `boolean` | 是否在子支会话 |
| `subBranchParentConvId` | `string\|null` | 子支父会话 |
| `subBranchSourceMsgId` | `string\|null` | 子支源消息 |
| `conversationMode` | `"tutor"\|"feynman"\|"peer"` | 对话模式 |

#### `useTreeStore`（树/图谱数据）

| 字段 | 类型 | 用途 |
|------|------|------|
| `childMap` | `Map<string, GraphNode[]>` | 子节点缓存（key = 父节点 ID） |
| `expandedSet` | `Set<string>` | 展开节点集合（持久化） |
| `loadingSet` | `Set<string>` | 加载中节点集合 |
| `rootLoaded` | `boolean` | 根已加载 |
| `rootId` | `string` | 根节点 ID |
| `treeRefreshKey` | `number` | 树变更信号（驱动 sidebar key） |

Actions: `loadRootNodes`, `loadChildren`, `toggleExpand`, `expandAncestors`（Task #80 新增）, `setChildMap`

#### `useMessageStore`（消息/响应块）

| 字段 | 类型 | 用途 |
|------|------|------|
| `outlines` | `MessageNode[]` | 消息骨架（全量，无正文） |
| `tipMessageId` | `string\|null` | 当前活跃路径尾消息 |
| `loadedContent` | `Record<string, MessageNode>` | msgId → 完整消息 |
| `loadingContents` | `string[]` | 正在懒加载的 msgId |
| `messages` | `MessageNode[]` | 渲染源（由 tip + outlines + loadedContent 推导） |
| `streamingId` | `string\|null` | 当前流式写入的 assistant msgId |
| `loadingMessages` | `boolean` | 骨架加载中 |
| `convError` | `string\|null` | 对话错误 |

Actions: `loadMessages`, `lazyLoadContent`, `lazyLoadBatch`, `setTip`, `navigateVersion`, `deleteMessage`, `editMessage`, `versionSwitch`

#### `actions/`（拆分 action 文件）

- `send-message.ts` — `sendMessageImpl` + `setSending/isSending` + `setChatStreamAPI`
- `dir-ops.ts` — `loadDirListImpl`, `createDirectoryImpl`, `renameDirectoryImpl`
- `nav-ops.ts` — `selectConversationImpl`, `switchConfirmImpl`, `switchDismissImpl`
- `tree-ops.ts` — `handleNewConversationImpl`
- `sub-branch.ts` — `setPendingQuoteImpl`, `enterSubBranchImpl`, `createSubBranchImpl`, …
- `message-ops.ts` — 消息级 action

### 1.4 Hooks

| Hook | 行数 | 职责 |
|------|------|------|
| `useConversation` | 282 | 页面级 facade：selector 化订阅 + URL 恢复 + 流重连 |
| `useChatStream` | 960 | SSE 流式（send/replay/stop/waitForDone），generation 机制防交叉 |
| `useDraftPersistence` | 60 | 输入框草稿 localStorage 持久化 |
| `useTextSelection` | 370 | 文本选区 + 引用 + 解释卡创建 |
| `useSocraticMode` | 60 | 苏格拉底模式 |
| `useTreeNavigation` | 280 | 树操作（创建/重命名/删除/新建会话） |
| `useGraphCanvas`, `useGraphData`, `useGraphDialogue`, `useGraphNodeActions`, `useTreeChatStream`, `useTreeLayout` | — | 图谱相关（独立模块） |
| `useBreakpoint` | 62 | 断点（mobile/tablet/desktop） |
| `useMediaQuery` / `useIsMobile` / `useIsTablet` / `useIsDesktop` | 38 | 媒体查询 |

### 1.5 类型（`@/types`）

- `MessageNode` — `{ id, directory_id, content, version, parent_id, children_ids, dir_id, conv_id, content_blocks, text_summary, role, timestamp, token_count, is_deleted, is_archived, has_sub_branches?, cognitive_node_ids? }`
- `ResponseBlock` — `text | image | file | quote | tool | reasoning`
- `ToolBlock` / `ReasoningBlock` / `SubBranchInfo` / `BackgroundJob`

### 1.6 API 调用清单

`useTreeStore.loadRootNodes` → `GET /api/conversations/tree/directory`
`useTreeStore.loadChildren` → `GET /api/conversations/tree/directory?parent_id=`（fallback `/api/cognitive/graph/nodes?parent_id=`）
`useMessageStore.loadMessages` → `GET /api/conversations/tree/conversation/{cid}/messages?limit=50&offset=0`
`useMessageStore.lazyLoadContent` → `GET /api/conversations/tree/message/{mid}`
`useMessageStore.deleteMessage` → `DELETE /api/conversations/tree/message/{mid}`
`useMessageStore.editMessage` → `PUT /api/conversations/tree/message/{mid}` + `POST /api/conversations/tree/message/{mid}/reply`
`FlatConversationList.fetchRecent` → `GET /api/conversations/tree/conversations/recent?limit=50`
`useChatStream.send` → `POST /api/conversations/tree/conversation/{cid}/message` (SSE response)
`useChatStream.replay` → 同上 with `{action:"replay"}`
`useChatStream.stop` → `POST /api/conversations/tree/conversation/{cid}/message` `{action:"stop"}`
`tree-ops.createDirectory` → `POST /api/conversations/tree/directory`
`tree-ops.renameDirectory` → `PATCH /api/conversations/tree/directory/{id}`
`tree-ops.deleteDirectory` → `DELETE /api/conversations/tree/directory/{id}`
`useConversationStore.replayActive` → `GET /api/conversations/tree/stream/active/{cid}`

**前端发起的端点（去重）：15 个**。后端总 44 个对话端点（其中 9 个属于 knowledge-tree/conversations 独立子模块，前端未直接调用）。

---

## 2. 性能现状摸底

### 2.1 虚拟列表 / 懒加载

| 位置 | 状态 | 备注 |
|------|------|------|
| `MessageList`（消息流） | **缺失**（只用 IO 懒加载正文） | 当前消息数 < 50 时全量 DOM 渲染，未做虚拟滚动。100+ 消息时 DOM 节点 100+ |
| `FlatConversationList`（扁平对话列表） | **缺失** | 直接 `.map(50 个 conv)` 渲染，无虚拟化 |
| `SidebarTreeNode`（递归树） | **不需要**（深度有限，节点数小） | 树深度通常 ≤ 3，节点数 ≤ 100 |
| 消息正文懒加载 | **✅ 已实现** | `useMessageStore.lazyLoadContent` + IO + 200px rootMargin |
| 媒体（图片/视频） | **缺失** | `<img>` 无 `loading="lazy"`，markdown 图片未走懒加载 |
| Block 组件代码分割 | **缺失** | `QuestionBlock` (1058 行) / `KnowledgeExplainCard` (134 行) 等大组件直接 import |

### 2.2 重渲染风险点

| 组件 | 风险 | 现状 |
|------|------|------|
| `MessageList` (1147 行) | **高** | 每次流式 token 写入都触发整树重渲染。`_rebuild` 在 `lazyLoadContent` 末尾 + 多个 useEffect 触发 |
| `SidebarTreeNode` (348 行) | **中** | 递归组件，每个节点都 subscribe `useTreeStore`，子节点删除/重命名会传播到祖先 |
| `FlatConversationList` (286 行) | **中** | `.map` 渲染 50 行，每行 onClick 闭包捕获整个 conv 对象 |
| `ChatInput` (340 行) | **低** | useDraftPersistence 触发 setState 频繁（每次按键） |
| `ConversationPanel` (393 行) | **中** | 14 个字段 props，子组件无 memo |

### 2.3 内存/性能热点

- `MessageList` 中 `useExplainStore` 全量订阅 → 任何 explain card 变化都触发重渲染
- `messages.map(m => m.id).join(',')` 作为 useEffect 依赖 → 每次 messages 变化都重新执行
- `loadedContent` 是 spread 浅复制 → `lazyLoadContent` 触发整树 _rebuild

### 2.4 API 缓存

- 无 SWR / React Query
- 仅 `useMessageStore` 的 `loadedContent` 是单会话缓存
- 跨会话不缓存（切换会话再回来要重新 lazy-load）
- 侧边栏树数据用 `useTreeStore.childMap` 缓存（✅）

---

## 3. UI/UX 现状

### 3.1 Loading / Skeleton

| 位置 | 现状 |
|------|------|
| `app/conversation/loading.tsx` | `ChatSkeleton`（3 个 card skeleton，flex-col，p-4） |
| `MessageList` 内 MessageSkeleton | inline component，3 行灰色矩形（isUser 决定方向） |
| `FlatConversationList.loading` | 仅"加载中..."文字（无骨架） |
| `StudySidebar.loading` | 仅"加载中..."文字（无骨架） |
| `useTreeStore.loadingSet` 节点 | 已展开节点的 chevron 旋转动画（✅） |

**问题**：loading 状态样式不统一（一些是骨架，一些是文字）

### 3.2 Empty State

| 位置 | 现状 | 备注 |
|------|------|------|
| `FlatConversationList` | inline：Hash icon + "暂无会话" + "发送消息将自动创建" | 与 `EmptyState` 组件重复 |
| `StudySidebar` | inline：Hash icon + "暂无分区" + "发送消息将自动创建" | 与 `EmptyState` 组件重复 |
| `EmptyState` 组件（ui/EmptyState.tsx） | 已存在，使用 ink-primary/ink-muted 语义 token | **未被 conversation 模块使用** |

**问题**：空状态各自 inline，样式略不一致

### 3.3 Error State

| 位置 | 现状 |
|------|------|
| `useMessageStore.convError` | 字符串，写入 `ErrorBanner`（红色 bg + 红字） |
| `FlatConversationList` error | inline 红色文字 + 重试按钮 |
| `useConversation.error.tsx` (根 layout) | 全局 error 页面 |

**问题**：错误展示样式略不统一（FlatConversationList 直接 `var(--color-error)`，ErrorBanner 用 opacity 10% 背景）

### 3.4 Toast / Notification

| 系统 | 现状 |
|------|------|
| 复制成功 | **无**（`handleCopyMessage` 静默调用 `navigator.clipboard`） |
| 删除成功 | **无**（silent） |
| 重命名成功 | **无**（silent） |
| 流式中断 | `ErrorBanner` 弹出（✅） |
| 通知 store | `useNotificationStore` 已存在（top-right toast） |

**问题**：复制/删除/重命名等用户操作无明确反馈

### 3.5 Design Token 对齐

- `globals.css` 已建立完整的 design token（颜色/字体/间距/圆角/阴影/动效）
- 5 套风格变体（professional/playful/knowledge/soft-data/gamified）
- 大多数 conversation 组件已使用 `var(--color-*)` 引用 token
- 部分组件直接用 Tailwind 色（`bg-blue-500`, `text-emerald-500`）—— 仅 Feynman mode 等特殊场景

**结论**：UI 整体对齐 design-language，个别细节用 Tailwind hard-coded 颜色

---

## 4. 移动端适配现状

### 4.1 Viewport / Breakpoint

| 位置 | 现状 |
|------|------|
| `app/layout.tsx` viewport | `width: device-width, initialScale: 1, maximumScale: 1` |
| `useBreakpoint` | mobile < 640 / tablet 640-1023 / desktop ≥ 1024 |
| `useMediaQuery("(min-width: 1024px)")` | ConversationPanel 用此判断布局 |
| `useIsMobile` / `useIsTablet` / `useIsDesktop` | 已存在但未被 conversation 全面使用 |

### 4.2 移动端布局

| 元素 | 桌面端 | 移动端 |
|------|--------|--------|
| Sidebar | 280px 固定列（可折叠） | `MobileBottomSheet` 抽屉（fixed bottom-sheet） |
| 消息区 | 居中 max-w-3xl | 撑满宽度 |
| 顶部 | 无（紧凑） | Menu 按钮 + 标题 + 模式切换 + 新建 |
| 底部 | 无 | AppShell 自带 BottomNav（被 ConversationPanel 覆盖，bottom: var(--bottom-nav-height)） |
| ChatInput | 同桌面（无差异） | 同桌面，无特别优化 |

### 4.3 Touch / 键盘 / Safe Area

| 项 | 现状 |
|----|------|
| Touch target ≥ 44px | 关键按钮已加 `style={{ minWidth: 44, minHeight: 44 }}`（✅） |
| 键盘弹起 | **未处理**（textarea 自动 resize，但页面无 padding-bottom: env(safe-area-inset-bottom)） |
| Safe area（iPhone notch） | **缺失**（无 env(safe-area-inset-bottom) 适配） |
| 触屏 swipe | **缺失**（MobileBottomSheet 只能点遮罩关闭） |
| 长按菜单 | **缺失**（移动端三点菜单用 hover 模拟，体验差） |
| 缩放 | `maximumScale: 1` 禁止（但可考虑 `viewport-fit=cover` + safe area） |

### 4.4 已知移动端问题

1. **iOS Safari bottom bar**：当 ChatInput 获得焦点弹出键盘，输入框可能被遮挡（无 padding-bottom 调整）
2. **MobileBottomSheet 无 swipe-to-close**：用户只能点击 X 或遮罩
3. **侧边栏无 swipe-to-open**：必须点左上角 Menu 按钮

---

## 5. 关键交互清单

### 5.1 侧边栏节点 CRUD

| 操作 | 入口 | API | 状态流转 |
|------|------|-----|----------|
| 新建目录 | 菜单"新建目录" + `NewNodeDialog` | `POST /tree/directory {node_type:"dir",kind:"general",parent_id,name,emoji}` | optimistic → setNewChildTarget null + 刷新父 childMap |
| 新建会话 | 菜单"新建会话" | `ensureConversationAtLevel` → `POST /tree/directory {node_type:"conv"}` | 复用空"新会话"或新建 |
| 移动节点 | **缺失**（无 drag/drop，无 move 菜单） | — | — |
| 重命名目录 | InlineEdit + `PATCH /tree/directory/{id}` | 乐观更新 childMap + 触发 treeRefreshKey |
| 重命名会话 | 同上 | 同上 | 同上 |
| 删除目录 | `ConfirmDialog` + `DELETE /tree/directory/{id}` | 父 childMap 刷新，删除后 navigateToNode(parentId) |
| 删除会话 | 同上 | 同上 | 同上 |

**问题**：**移动节点**是文档要求但**当前未实现**！ADR 提到 `move_subtree_to_conversation` 但前端没有 move 入口。

### 5.2 消息 CRUD

| 操作 | 入口 | API |
|------|------|-----|
| 发送 | ChatInput → `ensureConv` + `sendMessage` | `POST /tree/conversation/{cid}/message` (SSE) |
| 编辑（user 消息） | MessageActions "编辑" → `MessageEditArea` | `PUT /tree/message/{mid}` + `POST /tree/message/{mid}/reply` |
| 删除 | MessageActions "删除" | `DELETE /tree/message/{mid}` + 重载 messages |
| 复制 | MessageActions "复制" | `navigator.clipboard.writeText` |
| 版本切换 | MessageActions "上一版本/下一版本" | 纯前端（`_findVersionGroup` + `setTip`） |

### 5.3 流式响应

| 阶段 | 状态 |
|------|------|
| 用户发消息 | optimistic write（user msg + asst 占位符） |
| `chatStream.send` POST | `set({isLoading:true, statusMessage:"正在连接..."})` |
| SSE `token` 事件 | `_handleToken` 追加到 `streamingId.content_blocks` |
| SSE `tool_calls` | `_handleToolCalls` 插入 ToolBlock (status:pending) |
| SSE `tool_call_update` | `pending→running` |
| SSE `block_update` | `running→done` + result_content |
| SSE `reasoning` | 追加 ReasoningBlock |
| SSE `done` | `_handleDone` 替换消息 ID + 合并 response_blocks |
| SSE `error` | ErrorBanner + 移除乐观消息 + 写入 err 节点 |
| 中断/重发 | `chatStream.stop` → 等 done → `set({isLoading:false})` |

**问题**：流式连接状态 UI 反馈只有顶部三点 + statusMessage。Loading 状态信息密度低。

### 5.4 引用 / 解释 / 子支

| 交互 | 实现 |
|------|------|
| 选中文本 | `useTextSelection` 监听 mouseup/contextmenu |
| 引用 | `TextSelectionToolbar.onQuote` → `setPendingQuote` |
| 解释 | `TextSelectionToolbar.onExplain` → `createCard`（写入 useExplainStore） |
| 笔记 | `TextSelectionToolbar.onNote` → `setNoteCard` |
| 子支（创建子会话） | `onQuote` with `createSubBranch` + ChatInput 双按钮模式 |

---

## 6. 现有 E2E 覆盖

### 6.1 Pytest E2E（`backend/tests/test_conversation_e2e_full.py`）

**51 个测试，全部通过**（Task #80 完成）。覆盖：

| 测试类 | 数量 | 覆盖 |
|--------|------|------|
| TestTreeDirectoryCRUD | 8 | 树节点 CRUD + 多级嵌套 |
| TestConversationCRUD | 3 | 对话 CRUD |
| TestMessageOperations | 6 | 消息 CRUD + 版本切换 |
| TestUnifiedMessageEndpoint | 4 | `/message` 端点（send/replay/stop/tool-result） |
| TestSubBranch | 3 | 子支 |
| TestEmotionEndpoints | 3 | 情绪 |
| TestSSEStream | 4 | SSE 端点 dead-code 状态 |
| TestKnowledgeTreeConversations | 9 | knowledge-tree/conversations 9 个端点 |
| TestCrossModuleEvents | 3 | AssistantReplied / SessionCompleted |
| TestDataIsolation | 5 | 跨用户隔离 |
| TestFullLifecycle | 3 | 完整生命周期 |

**后端覆盖完整。** 前端浏览器 E2E 缺失。

### 6.2 现有 Browser E2E

`scripts/browser_e2e_test.py` — 7 模块 × 3 viewport = 21 截图（emotion/flashcard/interest/liveroom/planning/project/reading）。**不含 conversation**。

### 6.3 Playwright

- 系统全局 Python Playwright 1.61.0 已安装 (`/home/deploy/.local/bin/playwright`)
- **前端项目无 @playwright/test 依赖**
- 需要新增 `frontend/tests/e2e/conversation.spec.ts` + 安装 devDep

---

## 7. 已知问题 + 待优化点

### 7.1 Bug / 异常

| # | 位置 | 描述 |
|---|------|------|
| 1 | `MessageList.tsx:1053-1057` | `getElementsByClassName('rounded-[14px]')` 用 `closest('[class*="rounded-\\[14px\\]"]')` 选中冒泡容器，对 className 哈希变化敏感（脆弱） |
| 2 | `SidebarTreeNode.tsx:177` | `borderWidth` 计算 `[Math.max(3.25, 4/(depth+2)+3.25)]` 始终返回 3.25+，因为 `4/(depth+2)+3.25` 几乎都 > 3.25 → 死代码 |
| 3 | `ChatInput.tsx:142-143` | `await new Promise(r => setTimeout(r, 100))` 是 magic number 等待渲染，脆弱（应监听 state） |
| 4 | `useConversation.ts:191` | 刷新页面恢复流式时 `tempAsstId` 用了 `Math.random().toString(36).substr(2, 9)` —— `substr` 已 deprecated |
| 5 | `useChatStream.ts` 多处 | `Math.random().toString(36).substr(2, 9)` 同样问题 |
| 6 | `SidebarTreeNode.tsx:198` | `onKeyDown` 处理 Enter/Space/Arrow 但 `tabIndex={0}` 仅在 row 上，菜单按钮本身不可键盘聚焦（a11y） |
| 7 | `ChatInput.tsx:189` | 文件名截断 "max-w-[120px]" 在小屏过宽（应 max-w-[80px]） |
| 8 | `FlatConversationList.tsx:188` | `<div role="button" tabIndex={0}>` 缺 `aria-label` |

### 7.2 性能待优化

| # | 优化点 | 预期收益 |
|---|--------|----------|
| 1 | MessageList 100+ 消息时虚拟化 | DOM 节点 100+ → 20+ |
| 2 | 媒体（图片/video）懒加载 | 首次加载体积 -30% |
| 3 | QuestionBlock (1058 行) + KnowledgeExplainCard 代码分割 | 首屏 JS bundle -15% |
| 4 | React.memo SidebarTreeNode | 大树场景 30%+ 减少重渲染 |
| 5 | React.memo FlatConversationList row | 50 行列表 50%+ 减少重渲染 |
| 6 | useExplainStore 增量订阅 | 解释卡变更不重渲染整 MessageList |
| 7 | 路由级 dynamic import（lazy ConversationPanel） | 首屏 -20% |

### 7.3 UI/UX 待优化

| # | 优化点 |
|---|--------|
| 1 | 统一 loading skeleton（`StudySidebar` / `FlatConversationList` 都用文字） |
| 2 | 统一 empty state（inline 实现 → 用 `EmptyState` 组件） |
| 3 | 统一 error 展示（FlatConversationList 错误用 ErrorBanner 风格） |
| 4 | Toast 反馈：复制成功 / 删除成功 / 重命名成功 |
| 5 | SidebarTreeNode 选中色 hover 视觉反馈不一致 |

### 7.4 移动端待优化

| # | 优化点 |
|---|--------|
| 1 | `MobileBottomSheet` 加 swipe-to-close（touch 监听） |
| 2 | 侧边栏加 swipe-from-left-to-open |
| 3 | ChatInput 键盘弹起时 padding-bottom: env(safe-area-inset-bottom) |
| 4 | 全局 safe-area CSS 适配（iPhone notch） |
| 5 | 长按节点触发菜单（移动端 hover 替换） |

### 7.5 缺失功能

| # | 功能 | 备注 |
|---|------|------|
| 1 | **节点移动（drag/drop）** | ADR 提到但未实现 |
| 2 | **多选节点** | 无 |
| 3 | **节点搜索** | 无 |
| 4 | **导出对话** | 无 |
| 5 | **键盘快捷键** | 部分（Enter 发送、Esc 关闭对话框），无全局 |

---

## 8. 优化范围（Part B）总览

按优先级 + 收益分三档：

**P0（必做，影响最大）**：
1. `MessageList` React.memo 化 + 增量订阅
2. `FlatConversationList` 行 React.memo + 大列表时限制
3. 媒体（图片）懒加载 + 代码分割大组件
4. `EmptyState` 组件统一替代 inline
5. `MobileBottomSheet` swipe-to-close
6. ChatInput 键盘弹起 + safe area

**P1（应该做）**：
7. Toast 反馈
8. SidebarTreeNode React.memo + 三点菜单 a11y
9. 统一 loading skeleton

**P2（nice to have）**：
10. 路由级 dynamic import
11. 跨会话消息缓存

**不做**：
- 节点移动（无后端 endpoint，前端无法实现）
- 改 design-language

---

## 9. 路径汇总（绝对路径）

### 9.1 前端文件
- 主页面：`/home/deploy/edu-companion/frontend/src/app/conversation/page.tsx`
- Loading：`/home/deploy/edu-companion/frontend/src/app/conversation/loading.tsx`
- 主面板：`/home/deploy/edu-companion/frontend/src/components/conversation/core/ConversationPanel.tsx`
- 消息列表：`/home/deploy/edu-companion/frontend/src/components/conversation/core/MessageList.tsx`
- 消息区：`/home/deploy/edu-companion/frontend/src/components/conversation/core/ConversationMessageArea.tsx`
- 输入框：`/home/deploy/edu-companion/frontend/src/components/conversation/core/ChatInput.tsx`
- 侧边栏：`/home/deploy/edu-companion/frontend/src/components/conversation/panels/StudySidebar.tsx`
- 移动底栏：`/home/deploy/edu-companion/frontend/src/components/conversation/panels/MobileBottomSheet.tsx`
- 扁平列表：`/home/deploy/edu-companion/frontend/src/components/conversation/panels/FlatConversationList.tsx`
- 树节点：`/home/deploy/edu-companion/frontend/src/components/conversation/tree/SidebarTreeNode.tsx`
- Store 根：`/home/deploy/edu-companion/frontend/src/store/conversation/conversation-store.ts`
- 树 store：`/home/deploy/edu-companion/frontend/src/store/conversation/tree-store.ts`
- 消息 store：`/home/deploy/edu-companion/frontend/src/store/conversation/message-store.ts`
- 树 helpers：`/home/deploy/edu-companion/frontend/src/store/conversation/tree-helpers.ts`
- 路由 hook：`/home/deploy/edu-companion/frontend/src/hooks/conversation/useConversation.ts`
- 流 hook：`/home/deploy/edu-companion/frontend/src/hooks/conversation/useChatStream.ts`

### 9.2 文档
- 设计语言：`/home/deploy/edu-companion/docs/design-language.md`
- 前端设计文档：`/home/deploy/edu-companion/docs/modules/conversation-system/frontend-design.md`
- 前任务审计：`/home/deploy/edu-companion/docs/temp/task-80-conversation-audit.md`

### 9.3 测试
- 后端 E2E：`/home/deploy/edu-companion/backend/tests/test_conversation_e2e_full.py`（51 passed）
- 现有 Browser E2E：`/home/deploy/edu-companion/scripts/browser_e2e_test.py`（不含 conversation）
- 新建目标：`/home/deploy/edu-companion/frontend/tests/e2e/conversation.spec.ts`

### 9.4 工具脚本
- 重建：`/home/deploy/edu-companion/rebuild.sh`
- 设计 token：`/home/deploy/edu-companion/frontend/src/app/globals.css`
- Tailwind config：`/home/deploy/edu-companion/frontend/tailwind.config.js`
- Playwright（Python 1.61.0）：`/home/deploy/.local/bin/playwright`
