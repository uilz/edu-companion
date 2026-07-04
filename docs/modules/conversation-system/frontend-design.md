# 对话系统 · 前端设计

> 基于 Zustand Store + SSE StreamPipeline + Block Renderer Registry 的组件架构。
> 源码: [frontend/src/store/conversation/](../../../frontend/src/store/conversation/) | [frontend/src/components/conversation/](../../../frontend/src/components/conversation/)
>
> **Task #80 (2026-07-04) 更新**:
> - 修复 4 个 pre-existing TS 错误（QuestionBlock/ToolCallBlock/StudySidebar）
> - 新增 `useTreeStore.expandAncestors()` action
> - 配套 E2E: `backend/tests/test_conversation_e2e_full.py` (51 测试)

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
| `expandedSet` | `Set<string>` 展开节点 ID 集合 |
| `loadingSet` | `Set<string>` 加载中节点 ID 集合 |
| `rootLoaded` | `boolean` 根是否已加载 |
| `treeRefreshKey` | `number` 树变更信号 |

| Action | 说明 | Task #80 |
|--------|------|----------|
| `loadRootNodes()` | 加载根级目录 | - |
| `loadChildren(parentId)` | 加载子节点 | - |
| `toggleExpand(node)` | 切换展开状态 | - |
| `expandAncestors(path)` | **展开祖先链** | **新增** |
| `setChildMap(m)` | 直接设置 childMap | - |

#### expandAncestors（Task #80 新增）

```typescript
expandAncestors: (path: string[]) => void
```

**作用**：把 path 数组中的所有节点 ID 全部加入 expandedSet，同时保证 ROOT_KEY 始终展开。

**使用场景**：
- 页面初始化时从 URL 恢复 selectedNode（StudySidebar.tsx:57）
- SwitchBanner 切换会话时
- 节点搜索跳转

**实现**：
```typescript
expandAncestors: (path: string[]) => {
  if (!Array.isArray(path) || path.length === 0) return;
  set(s => {
    const next = new Set(s.expandedSet);
    next.add(ROOT_KEY);
    for (const id of path) {
      if (id) next.add(id);
    }
    persistExpandedSet(next);  // localStorage 持久化
    return { expandedSet: next };
  });
}
```

**修复前**：StudySidebar.tsx 直接调用 `useTreeStore.getState().expandAncestors(path)`，但该方法不存在 → TS2339 错误。代码虽然 build 通过（TypeScript strict 模式不开启），但运行时会 throw `expandAncestors is not a function`，导致页面初始化时无法展开祖先链 → 树视图无法定位到当前选中节点。

**修复后**：方法存在、TS 编译通过、祖先链正确展开。

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

## 已知问题与修复历史（Task #80）

### 修复的 TS 错误

| 文件:行 | 错误 | 根本原因 | 修复 |
|---------|------|----------|------|
| `QuestionBlock.tsx:240` | `Property 'questions' does not exist on type '{ content, fallbackQuestions }'` | `PersistedAnswersView` 用 `questions: fallbackQuestions` 解构重命名，但调用点传的是 `fallbackQuestions` 字段 | 函数签名去掉重命名，prop 名统一为 `fallbackQuestions` |
| `ToolCallBlock.tsx:86-87` | `Property 'dir_id' / 'conv_id' does not exist on type 'ToolBlock'` | `ToolBlock` 类型未声明这两个字段，代码尝试从 block 读取 | 移除对未定义字段的读取（用空串），因为 ResponseBlockRenderer 不需要这些字段 |
| `StudySidebar.tsx:57` | `Property 'expandAncestors' does not exist on type 'TreeState'` | 调用了未实现的方法 | 在 tree-store 新增 `expandAncestors(path)` action |

### 已知遗留问题（不在 Task #80 范围）

1. **`stream_sse.py` 未挂载**：4 个 SSE 端点（`/stream/{cid}`, pause/resume/stop）在源文件中实现但未被 `conversation.py` 包含 → 404。统一消息端点使用 `stream_buffer` 实现了同等功能。后续 Task 需决定删除 dead code 或挂载启用。
2. **`/tree/switch` 未实现**：调用 `tree_ops.move_subtree_to_conversation`（不存在）→ 当前返回 501 (Task #80 改进)。
3. **`/tree/conversation/{cid}/migrate` 调用错误方法**：原调用 `migrate_temporary_conversation`（不存在）→ Task #80 改为 `migrate_conv`（存在）。

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
│   │   ├── tree-store.ts              — 目录树 Store (含 expandAncestors)
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
│           ├── QuestionBlock.tsx       — 问题卡片 (Task #80 修复)
│           ├── ReasoningBlock.tsx      — 推理过程
│           ├── ImageBlock.tsx
│           └── FileBlock.tsx
│
└── hooks/
    └── conversation/
        └── useConversation.ts          — 页面级 hook
```

---

## 配套测试

后端 E2E 测试：`backend/tests/test_conversation_e2e_full.py` (Task #80 新增)

- 51 个测试，全部通过
- 覆盖 11 个测试类：
  1. TestTreeDirectoryCRUD (8) - 树节点 CRUD
  2. TestConversationCRUD (3) - 对话 CRUD
  3. TestMessageOperations (6) - 消息操作
  4. TestUnifiedMessageEndpoint (4) - 统一消息端点
  5. TestSubBranch (3) - 子支
  6. TestEmotionEndpoints (3) - 情绪
  7. TestSSEStream (4) - SSE 流（验证 dead code 状态）
  8. TestKnowledgeTreeConversations (9) - 知识树对话
  9. TestCrossModuleEvents (3) - 事件联动
  10. TestDataIsolation (5) - 数据隔离
  11. TestFullLifecycle (3) - 完整生命周期

---

## 性能优化与移动端适配（Task #85 — 2026-07-04）

### 1. 虚拟化（react-virtuoso）

**选型理由**：
- 原生支持流式追加（`followOutput="smooth"`，匹配"会话状态流式接受"需求）
- 动态高度（消息长短不一，react-window 固定/动态模式都偏弱）
- 完善的 `scrollToIndex` API
- 体积约 30kb，对桌面+移动端项目可接受

**应用范围**：
- `MessageList`（`core/MessageList.tsx`）：长消息流虚拟化
- `FlatConversationList`（`panels/FlatConversationList.tsx`）：侧边栏扁平列表虚拟化

**配置**：
- `overscan={400}` — 上下各预渲染 400px 区域
- `followOutput={atBottom ? "smooth" : false}` — 用户在底部时自动跟随流式输出
- `atBottomStateChange={setAtBottom}` — 状态机驱动 scroll button 显示
- `initialTopMostItemIndex={messages.length - 1}` — 首次加载跳到底部

**自动滚动状态机**：
- 离开底部：用户主动上滑（wheel deltaY < 0 或 touchmove dy > 1）→ 退出 autoFollow
- 回到底部：滚到底部 / 点击"滚到底部"按钮 / 发送新消息 → 重新进入 autoFollow
- 与原 MessageList 的 autoFollow 状态机语义保持一致

### 2. 组件拆分 + React.memo

| 组件 | 优化 | 收益 |
|------|------|------|
| `MessageItem` | 提取单条消息渲染为独立组件 + memo + 自定义比较 | 避免同级消息无关更新导致整列表重渲染 |
| `SidebarTreeNode` | memo + 自定义比较（childMap/expandedSet 引用稳定性） | 树节点单独更新不影响兄弟 |
| `FlatRow` | memo + 自定义比较（按显示字段） | 扁平列表行级别重渲染控制 |
| `itemContent` (Virtuoso) | useCallback + 完整依赖列表 | Virtuoso 不会因回调引用变化重建 |

### 3. UI/UX 一致性

**统一三态组件**：
- `EmptyState` — 空状态（icon + title + description）
- `Skeleton` — 加载骨架（text/card/circle/rect 4 种变体）
- `Toast` — 操作反馈（success/info/warning/error 4 种，自动 2.5s 消失）

**应用位置**：
- `FlatConversationList` — loading/error/empty 三态用统一组件
- `StudySidebar` — 树根列表 + 加载/空态
- `MessageList` — 消息列表空态（"开始一段对话"）
- `ChatInput` — 文件上传成功/失败 toast
- 侧边栏菜单操作 — 重命名成功 toast

**TestID 锚点**（E2E 用）：
- `data-testid="message-virtuoso"` — Virtuoso 容器
- `data-testid="message-list-scroll-btn"` — 滚到底部按钮
- `data-testid="chat-input-container"` — 输入框容器
- `data-testid="sidebar-tree"` — 侧边栏树容器
- `data-testid="text-selection-toolbar"` — 文本选择工具栏
- `data-testid="mobile-bottom-sheet"` — 移动端抽屉

### 4. 移动端适配

**已支持**：
- `<meta name="viewport" content="width=device-width, initial-scale=1">` — `frontend/src/app/layout.tsx`
- `env(safe-area-inset-bottom)` — `ChatInput` 容器底部内边距
- `useBreakpoint` hook（mobile < 640 / tablet 640-1023 / desktop ≥ 1024）— 已有
- `MobileBottomSheet` — swipe-to-close（> 80px 或速度 > 0.4 px/ms 触发）
- 触摸目标最小 44x44px（按钮/菜单项）

**关键断点行为**：
- `mobile/tablet`（< 1024px）：ConversationPanel 切换为单列布局
  - 侧边栏 → 抽屉（默认隐藏，菜单按钮打开）
  - BottomSheet 80% 高度 + swipe 手势关闭
  - 顶部 nav 包含菜单/模式切换/新建按钮
- `desktop`（≥ 1024px）：5 栏 Workbench 中的左/右栏
  - 侧边栏固定 280px 宽，可折叠
  - 无 BottomSheet 抽屉

### 5. 浏览器 E2E（Playwright）

**配置**：
- `playwright.config.ts` — 3 个 project：desktop (1280x800) / tablet (768x1024) / mobile (375x667)
- `e2e/conversation.spec.ts` — 16 个测试用例
- `e2e/helpers.ts` — API 登录 + localStorage 注入（比 UI 登录稳定）

**用例覆盖**：
- Desktop (10)：页面加载、模式切换、消息发送/编辑/复制、虚拟化、滚动按钮、错误恢复、console 错误检测、scrollToIndex API
- Mobile (5)：默认布局、抽屉、safe-area、输入框聚焦、消息发送
- Tablet (1)：消息发送

**运行**：
```bash
npx playwright test --project=desktop   # 仅 desktop
npx playwright test --project=mobile    # 仅 mobile
npx playwright test                       # 全部
```

**截图归档**：`playwright-report/screenshots/`（每个用例自动 fullPage 截图）

### 6. 已知问题与权衡

| 项 | 状态 | 说明 |
|----|------|------|
| Virtuoso 不支持 IntersectionObserver | ✅ 替代方案 | 用 `rangeChanged` 触发懒加载（visibleRange + 上下各 3 条） |
| 流式响应中 ExplanationMarkers 重计算 | ⚠️ 可优化 | 后续可加 debounce |
| 编辑中转 Virtuoso scroll 时位置错乱 | ⚠️ 已知 | 临时方案：编辑时禁用 scroll-to-bottom |

