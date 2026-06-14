# Frontend — 苹果果前端

Next.js 14 (App Router) 前端应用，提供 AI 对话、练习中心、知识图谱、驾驶舱看板、秘书面板等知识管理功能界面。

## Store Architecture

2025-06-14: 将 God Store（ConversationStore ~100 字段）拆分为三个独立 Zustand store：

- **useTreeStore** (`tree-store.ts`) — 树/图谱数据
  - State: `childMap`, `expandedSet`, `loadingSet`, `rootLoaded`, `rootId`, `treeRefreshKey`
  - Actions: `loadRootNodes`, `loadChildren`, `toggleExpand`, `setChildMap`
  - 专注树节点加载和展开/折叠，不涉 UI 状态或消息数据
  - _Avoid_: 选中状态、UI 标志

- **useMessageStore** (`message-store.ts`) — 消息/响应块数据
  - State: `messages`, `responseBlocks`, `loadingMessages`, `convError`
  - Actions: `loadMessages`, `deleteMessage`, `editMessage`, `versionSwitch`
  - 通过 conversation-store 的跨 store subscribe 自动同步流式更新
  - _Avoid_: 发送消息（sendMessage 横跨 pipeline + UI）

- **useConversationStore** (`conversation-store.ts`) — UI 状态 + 跨领域协调
  - State: `dirList`, `selectedNodeId`, `isLoading`, `statusMessage`, `switchBanner`, `sidebarCollapsed`, 子分支状态等
  - 作为 coordinator，委托树操作到 tree-store、消息操作到 message-store
  - 向后兼容：re-export useTreeStore + useMessageStore；保留 childMap/expandedSet/loadingSet 等代理字段
  - _Avoid_: 纯树/消息数据（应使用专用 store）

迁移路径：新组件直接用 `useTreeStore` / `useMessageStore`；旧组件逐步从 `useConversationStore` 迁移。

## Graph Node Actions

2025-06-14: 抽取 `useGraphNodeActions` hook (`hooks/graph/useGraphNodeActions.ts`)，封装 KnowledgeTreePage / NodeDetailPanel / TreeChatPanel 之间重复的图谱节点操作：

- `deleteNode(nodeId, nodeLabel)` — DELETE .../node/{id}
- `editNode(nodeId, { label, description, tags })` — PATCH .../node/{id}
- `createNode({ label, parent_id })` — POST .../node
- `aiExpand(nodeId, { depth, direction })` — POST .../ai-expand
- `aiEdit(nodeId)` — POST .../ai-edit
- `aiChat(nodeId, message, convId?)` — POST .../ai-chat，返回 `{ response, conversationId }`
- `generateGraph()` — POST .../graph/{partitionId}/generate

### 迁移情况
- KnowledgeTreePage.tsx: 替换了 6 处 authedFetch（delete/edit/create/aiExpand/aiEdit）
- NodeDetailPanel.tsx: 替换了 4 处 authedFetch（edit/delete/aiExpand/aiChat）
- TreeChatPanel.tsx: 保留 `authedFetch` 直调 ai-chat（需访问 conversation_recommendation 原始字段）

## Hooks 目录约定

2025-06-14: 统一 hooks 放置约定，消除 `src/lib/hooks/` 和组件内 hooks 的混乱分布。

### 约定
- **通用 hooks** → `src/hooks/*.ts`（如 `useMediaQuery`、`useCurrentUserId`、`useRenderedContent`）
- **领域 hooks** → `src/hooks/<domain>/`（如 `src/hooks/conversation/`、`src/hooks/graph/`、`src/hooks/study/`、`src/hooks/practice/`）
- **组件独有 hook** → 保留在组件目录内（如 `components/conversation/hooks/useTextSelection.ts`）

### 迁移情况
| Hook | 旧位置 | 新位置 |
|------|--------|--------|
| `useMediaQuery` | `components/conversation/hooks/` | `src/hooks/useMediaQuery.ts` |
| `useRenderedContent` | `src/lib/hooks/` | `src/hooks/useRenderedContent.ts` |
| `useConversation` | `components/conversation/hooks/` | `src/hooks/conversation/useConversation.ts` |
| `useTextSelection` | 保留原位 | 组件独有 hook |
| `useSocraticMode` | 保留原位 | 组件独有 hook |

旧位置保留 `@deprecated` 重导出，保持向后兼容。

## Notification System

2025-06-14: 解耦通知系统 — 将非流式事件（context_switch / tree_recommendation / temp_recommendation / job_update）的 NotificationStore 写入责任从旧的 `streaming.ts` 移至 `pipeline/setup.ts`（`bindPipelineToStore`）。

- **setup.ts**: 每个事件订阅中**同时**设置 conversation-store 状态（banner）和 NotificationStore 记录
- **streaming.ts**: 移除了 6 个 notification-service 调用（handleContextSwitch / handleWSTreeRecommendation / handleTempRecommendation / handleJobUpdate / handleSecretaryInline / handleSecretaryProposalUpdate），不再依赖 notification-service
- **notification-service.ts**: 4 个旧 handler 标记为 `@deprecated`，保留供测试用
- **关键决策**: NotificationStore 是纯数据层（Zustand），不直接依赖 React。消息的来源从旧 SSE 路径统一到 StreamPipeline，消除双重真相源

## 路由清理

2025-06-14: 消除重定向迷宫，减少无效路由 6 个。

### 删除的页面
| 路由 | 原因 | 处理方式 |
|------|------|---------|
| `/graph` → `/knowledge-tree` | 与 `/knowledge-tree` 重复 | next.config 已重定向 + 删除 page.tsx |
| `/learn/graph` → `/knowledge-tree` | 与 `/knowledge-tree` 重复 | next.config 已重定向 + 删除 page.tsx |
| `/achievements` → `/analytics?tab=achievements` | 合并到 analytics | next.config 已重定向 + 提取为 `AchievementsTab` 组件 |
| `/calendar` → `/analytics?tab=calendar` | 合并到 analytics | next.config 已重定向 + 提取为 `CalendarTab` 组件 |
| `/stats` → `/analytics?tab=stats` | 合并到 analytics | next.config 已重定向 + 提取为 `StatsTab` 组件 |
| `/progress` → `/analytics?tab=stats` | 与 `/stats` 重复 | next.config 已重定向 + 删除 page.tsx |

### Dashboard 运行时重定向 → next.config
原 `dashboard/page.tsx` 通过 `useEffect` + `router.replace()` 处理 9 种 `?tab=X` 参数，改为 next.config 的 `has` 条件重定向，简化页面为纯 `OverviewTab` 渲染。

### 清理后的路由
38 个 → 32 个页面路由，重定向链全部收敛为 next.config 单跳。

## Conversation 目录合并

2025-06-14: 合并 `renderers/` 到 `blocks/`，消除 `blocks/` 与 `renderers/` 之间的模糊边界。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `renderers/ResponseBlockRenderer.tsx` | → `blocks/ResponseBlockRenderer.tsx` | 分发器，属于 blocks |
| `renderers/QuoteBlockRenderer.tsx` | → `blocks/QuoteBlockRenderer.tsx` | 引文块，属于 blocks |
| `renderers/MarkdownRenderer.tsx` | → `blocks/MarkdownRenderer.tsx` | 渲染工具，blocks 共享 |
| `renderers/` 目录 | 🗑️ 删除 | 3 个文件全部迁移，import 更新完成 |

### 更新后的 conversation 目录
```
conversation/
├── banners/   5 files  — 横幅提示
├── blocks/    19 files — 全部响应块渲染器（含原 renderers）
├── cards/     4 files  — 知识卡片
├── core/      7 files  — 核心组件
├── hooks/     3 files  — 组件独有 hooks
├── input/     3 files  — 输入组件
├── media/     2 files  — 媒体组件
├── panels/    4 files  — 面板布局
└── tree/      4 files  — 侧边栏树
```

### 不做的事
- 不拆分 `blocks/` 为子目录（过度工程，16 文件可管理）
- 不合并 `cards/` 到 `blocks/`（语义不同：card ≠ block）
- 不移除组件内 hooks（`useTextSelection`、`useSocraticMode` 是组件独有）

## KnowledgeTreePage 重构

2025-06-14: 将 KnowledgeTreePage (1581 行) 拆分为编排器 + hook + 独立子组件。

### 新结构
```
components/knowledge-tree/
├── KnowledgeTreePage.tsx   ← 编排器 (~200 行): 渲染 + 子组件组合
├── TopBar.tsx              ← 从原文件提取的顶部导航栏
├── StatusBar.tsx           ← 从原文件提取的状态栏
├── FloatDialogWrapper.tsx  ← 从原文件提取的浮动对话气泡
├── PanelLayout.tsx         ← AutoCollapsePanel + ResizeHandle
├── LayerPanel.tsx          ← (不变)
├── DialogContainer.tsx     ← (不变)
├── ContextMenu.tsx         ← (不变)
├── EmptyState.tsx          ← (仍留在主文件，仅此使用)
└── index.ts                ← barrel export

hooks/graph/
├── useGraphCanvas.ts       ← 新: 图谱画布全部状态 + 逻辑 (~300 行)
└── useTreeLayout.ts        ← 新: LayoutPreference + localStorage 持久化
```

### 编排器职责
- 调用 `useTreeLayout()` 获取/持久化布局偏好
- 调用 `useGraphCanvas(layoutPref, setLayoutPref)` 获取画布状态和操作
- 根据 loading/error/empty 状态渲染对应的子组件
- 将 hook 的输出传递给子组件

### 剩余子组件（仍在主文件）
- `LoadingSkeleton` / `EmptyState` / `NoPartitionState` / `ErrorState` — 状态占位
- `FocusBreadcrumb` — 聚焦面包屑
- `ZoomControls` — 缩放控件
- `AddNodeDialog` — 添加节点弹窗

## SSE 解析统一

2025-06-14: 抽取共享 SSE 行解析器 `sse-parser.ts`，消除 `useChatStream` 与 `StreamPipeline` 之间的 SSE 解析重复。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `store/pipeline/sse-parser.ts` | ✨ 新建 | 共享 `parseSSEStream()` 函数 + `SSE_EVENTS` 常量 |
| `chat-shared/useChatStream.ts` | 🔧 修改 | 内联 SSE 解析 → `parseSSEStream()`，消除 ~30 行重复代码 |
| `AgentFloat.tsx` | — 不变 | 接口未变，无需改动 |

### parsed 的 SSE 协议
```
event: token\ndata: {"delta":"..."}
event: tool_call\ndata: {"name":"...","arguments":{...}}
event: conversation\ndata: {"conversation_id":"..."}
```

### 不做的事
- 不统一传输层（`useChatStream` 用 `fetch POST`，`StreamPipeline` 用 `EventSource GET`，各有用途）
- 不强制 AgentFloat 改用 StreamPipeline（事件模型不同：Agent 是 POST 请求/响应式，主对话是持久 SSE 流）

## Practice 目录扁平化

2025-06-14: 合并 `practice/components/` 和 `practice/shared/` 为 `practice/components/`。

### 变更
- `SecretaryProposals.tsx` → 删除（孤儿文件，0 引用）
- `panels/ReferencePanel.tsx` → 删除（孤儿文件，0 引用）
- `shared/*` (11 文件) → `components/`（合并）
- 14 个外部 import `shared/` → `components/` 批量替换

### 结果
```
components/practice/
├── panels/        (2 文件: PracticePanel, ExamPanel)
└── components/    (12 文件: QuestionStem, QuestionCard, OptionButton, 
                   FeedbackPanel, HintPanel, ExplanationPanel, ReferencePanel,
                   SummaryPanel, ProgressBar, SessionTimer,
                   QuestionPreviewModal, QuestionEditorModal)
```
删除 `shared/` 目录名（无意义命名），单层结构更清晰。

## FocusPage 图谱数据层共享

2025-06-14: 抽取 `useGraphData` hook，消除 FocusPage 与 useGraphCanvas 之间的 graph data fetching + ResizeObserver 重复。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `hooks/graph/useGraphData.ts` | ✨ 新建 | 共享 hook：`fetchGraphData` + 重试 + ResizeObserver |
| `focus/FocusPage.tsx` | 🔧 修改 | 内联 fetch+retry+ResizeObserver → `useGraphData()` (-35 行) |
| `hooks/graph/useGraphCanvas.ts` | — 不变 | 数据层与 partition 逻辑交互紧密，保持自有管理 |

### useGraphData API
```typescript
const { graphData, loading, error, graphContainerRef, graphSize, reload }
  = useGraphData({ partitionId?, maxRetries?, autoLoad? });
```

### 为何不强制 FocusPage 复用完整 useGraphCanvas
- FocusPage 图谱需求简单（无 partition/搜索/缩放/对话框）
- 完整 useGraphCanvas 携带 ~30 个 FocusPage 不需要的状态变量
- 共享数据层（useGraphData）恰好消除重复，又不过度耦合

## Agent Store → Zustand

2025-06-14: 将 Agent Store 从 class + singleton 模式迁移到 Zustand。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `store/agent/agent-store.ts` | 🔧 重写 | class singleton → `create()` from Zustand |
| `agent/AgentFloat.tsx` | 🔧 修改 | 使用 `useAgentStore` hook 实现 reactive 订阅 |
| `store/agent/__tests__/agent-store.test.ts` | 🔧 修改 | 使用 `createAgentStoreForTest` |

### API 变化
```typescript
// 旧
const store = getAgentStore();  // class singleton

// 新
const messages = useAgentStore(s => s.messages);           // reactive hook
const store = getAgentStore();                              // backward-compat imperative access
```

### 导出说明
- `useAgentStore` — Zustand hook，用于 reactive 订阅
- `getAgentStore()` — `useAgentStore.getState()` 的别名，用于回调中读取最新状态
- `createAgentStoreForTest()` — 测试用工厂函数

## 图谱类型重命名（DashboardNode）

2025-06-14: 将 Dashboard 的 `GraphNode` / `GraphEdge` 重命名为 `DashboardNode` / `DashboardEdge`，消除与 `graph-types.ts` 中 `GraphNode` 的命名碰撞。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `components/dashboard/graph-layout.ts` | 🔧 修改 | `GraphNode` → `DashboardNode`, `GraphEdge` → `DashboardEdge` |
| `components/dashboard/NodeDetailCard.tsx` | 🔧 修改 | 更新 import 和使用处 |

### 两个 GraphNode 的区别
```
graph-types.ts:    GraphNode (level/mastery/trend/children)         — 知识图谱渲染
graph-layout.ts:   DashboardNode (subject/confidence/blocked_by)    — 驾驶舱学习分析
```

## Conversation-store 向后兼容清理

2025-06-14: 移除 ConversationStore 中的 6 个树代理字段和 2 个向后兼容 re-export。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `store/conversation/conversation-store.ts` | 🔧 修改 | 移除 `childMap`/`expandedSet`/`loadingSet`/`rootLoaded`/`rootId`/`treeRefreshKey` 代理字段和初始值 |
| | | 移除 `loadRootNodes`/`loadChildren`/`setChildMap` 委托方法 |
| | | 移除 `subscribeToNavigation()`/`syncActiveRefs()` re-export |
| | | 移除跨 store subscribe 同步 |
| `hooks/graph/useTreeNavigation.ts` | 🔧 修改 | 树数据读取/操作从 `useConversationStore` → `useTreeStore` |
| `components/conversation/panels/StudySidebar.tsx` | 🔧 修改 | `rootLoaded`/`loadRootNodes` 从 `useConversationStore` → `useTreeStore` |
| `components/conversation/core/ConversationPanel.tsx` | 🔧 修改 | `treeRefreshKey` 从 `useConversationStore` → `useTreeStore` |
| `components/conversation/tree/NodePathBreadcrumb.tsx` | 🔧 修改 | `childMap` 从 `useConversationStore` → `useTreeStore` |
| `store/conversation/actions/nav-ops.ts` | 🔧 修改 | `childMap`/`treeRefreshKey` 从 `get()` → `useTreeStore.getState()` |

### 移除的代理字段
```
从 ConversationState 移除:
  childMap: Map<string, GraphNode[]>      → useTreeStore
  expandedSet: Set<string>                → useTreeStore
  loadingSet: Set<string>                 → useTreeStore
  rootLoaded: boolean                     → useTreeStore
  rootId: string                          → useTreeStore
  treeRefreshKey: number                  → useTreeStore
  loadRootNodes / loadChildren / setChildMap  → useTreeStore
  subscribeToNavigation() / syncActiveRefs()  → 直接调用 streaming.ts
  跨 store subscribe (message sync)           → 移除无必要循环同步
```

### 保留的消息代理字段
- `messages` / `responseBlocks` / `loadingMessages` / `convError` — 仍被 FocusPage、FocusModePanel、ConversationPanel 使用，待后续阶段迁移

## Token 节流共享化

2025-06-14: 抽取共享 `createTokenThrottle`，消除了 StreamPipeline 和 useChatStream 之间 token flush 节流逻辑的重复。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `store/pipeline/token-throttle.ts` | ✨ 新建 | 共享 `createTokenThrottle()` — 200ms 窗口累积 → 一次 flush |
| `chat-shared/useChatStream.ts` | 🔧 修改 | 每个 token 直接 `onToken(delta)` → `throttle.add(delta)` |
| `store/pipeline/StreamPipeline.ts` | — 不变 | 节流逻辑与 msgId+cache 绑定较紧，保留内联实现 |

### 效果
```
before: useChatStream → 每个 token 触发 onToken → 高频 setState → React 重渲染
after:  useChatStream → throttle.add(delta) → 200ms flush → 低频 onToken
```

### 不做的事
- 不强制 useChatStream 改用 SSESource 接口（POST vs EventSource GET 传输机制不同）
- 不将 AgentFloat 路由到 StreamPipeline（事件模型不同）

## 秘书对话持久化

2025-06-14: 将 AgentFloat 的秘书对话从纯内存存储改为树持久化。

### 变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `store/agent/agent-store.ts` | 🔧 修改 | 新增 `secretaryDirId`、`secretaryConvs`、`activeConvId`、`loadingSecretary`、`loadingMessages` 状态 + 相关 actions |
| `components/agent/AgentFloat.tsx` | 🔧 修改 | 新增 5 个辅助函数 + 打开时初始化 + 消息双向持久化 + 历史对话切换 UI |

### 树结构
```
学习空间
├── 📁 微 calculus               (kind: "general")
├── 📁 线性代数                  (kind: "general")
└── 🤖 秘书对话                  (dir, kind: "secretary")
    ├── 💬 6/14 14:30            (conv, kind: "secretary")
    └── 💬 6/13 10:15            (conv, kind: "secretary")
```

### 流程
1. 打开面板 → 确保 `kind="secretary"` 的 dir 存在 → 加载 conv 列表 → 选最新 conv → 从 tree 加载消息
2. 发送消息 → `POST /tree/conversation/{cid}/message { role:"user" }` 持久化 → SSE `/api/secretary/agent/chat` 流式回复 → `onDone` 时 `POST { role:"assistant" }` 持久化
3. 对话切换 → `switchConv` 清空本地 messages → 从 tree 加载新 conv 的历史消息
4. 新建对话 → `POST /tree/directory { kind:"secretary", name:日期 }` → 空消息列表

### 效果
```
before: 纯内存 → 刷新丢失，后端有存档但前端看不到
after:  树持久化 → 刷新恢复，侧栏可见，对话可切换，消息双向保存
```

## Language

### 路由与页面

**LearnPage (学习空间)**:
核心对话页面（路由 `/learn`）。主状态容器（~20 个 state 变量），管理 WebSocket 连接、路由/URL 同步、事件处理器。包含 PartitionSidebar / MessageList / ChatInput / SwitchBanner 等子组件。URL 格式 `/learn?p={partitionId}&c={conversationId}`。
_Avoid_: 聊天页、对话页

**Dashboard (驾驶舱)**:
学习概览仪表盘（路由 `/dashboard`）。含 tab 切换系统：Overview（概览）/ Graph（图谱）/ Analytics（分析）/ Plan（规划）/ Calendar（日历）/ Errors（错题）/ Achievements（成就）/ Quality（质量）。`/dashboard?tab=analytics` 通过 URL 控制。
_Avoid_: 仪表盘（中文用"驾驶舱"）

**Practice Page (练习中心)**:
练习功能入口（路由 `/practice`）。含子路由：`/practice/banks/[id]`（题库详情）、`/practice/sessions/[id]`（练习会话）。支持多种练习面板：PracticePanel、ExamPanel。

**Focus Mode (专注模式)**:
沉浸式学习模式（路由 `/focus`，重定向至 `/learn`）。隐藏导航，全屏对话 + 图谱。包含 FocusPage 组件（663 行），含 FocusGraph 图谱可视化。

**Knowledge Graph Page (图谱页)**:
知识树可视化页面（路由 `/resources`，早期 `/graph` 已重定向到 Dashboard Graph Tab）。`GraphDialoguePage` 为图谱主页面，包含图谱视图 + 左侧树面板 + 右侧节点详情。

**Secretary Panel (秘书面板)**:
秘书系统前端（路由 `/secretary`）。展示 Proposal 列表（待处理/已采纳/已忽略），支持分页。子路由 `/secretary/settings` 为模块配置页（复习提醒/疲劳管理/日简报等模块开关）。

**Settings Page (设置页)**:
全局设置页面（路由 `/settings`）。含子路由：`/settings/data`（数据管理：导出/导入/重置）。支持设计风格切换（professional / playful / knowledge / soft-data / gamified）、亮暗主题切换。API 设置区域支持用户自定义 LLM 模型配置：API 端点 / API Key（密码输入框）/ 模型名称 / 系统提示词。配置通过 `authedFetch` 与后端 `/api/settings/llm` 交互（GET 加载 / PUT 保存 / DELETE 重置），API Key 加密存储在服务端。页面显示自定义状态指示器（"已启用自定义模型" / "使用系统默认模型"），保存/重置按钮及操作结果提示。学习偏好（系统提示词 / 苏格拉底模式 / 追问模式）单独本地存储。

**Files Page (文件管理)**:
文件管理页面（路由 `/files`）。双区设计：知识库（永久保留）+ 临时文件（跟随对话，7 天清理）。`/files/[material_id]` 展示材料详情（含 TOC 目录树）。

**Progress / Stats / Analytics Pages**:
已通过 `next.config.mjs` redirects 重定向到 `Dashboard?tab=analytics`。

### 对话系统组件

**Partition Sidebar (侧栏树)**:
左侧树形导航组件。层级：Partition → Domain → Topic → Conversation。懒加载子节点，自动展开路径追踪 activeConversationId。支持内联重命名/删除/CURD。桌面端固定 260px，可折叠；移动端通过 MobileBottomSheet 弹出。

**Mobile Bottom Sheet**:
移动端侧栏的底部弹出容器。`fixed inset-0` + `max-h-[70vh]`，选择对话后自动关闭。

**Message List**:
消息列表组件。渲染用户/助理消息，支持去重（反向遍历，同 ID 优先保留有内容版本）、内联编辑、版本切换（`<` `>`）、复制、删除、自动滚动。每 30 秒轮询刷新。响应块通过 `ResponseBlockRenderer` 分发。

**Multi-Agent Message (多 Agent 消息)**:
消息节点的 `agent_label` 字段指定 Agent 归属（`orchestrator` / `tutor` / `coach` / `secretary`）。MessageList 据此渲染不同头像和颜色气泡。Agent 代表色：Orchestrator 紫色、Tutor 蓝色、Coach 绿色、Secretary 橙色。多 Agent 协作时同一轮产生多个 assistant 节点，按 `conversation.path` 顺序渲染。

**Agent Store (agent-store.ts)**:
多 Agent 前端状态管理。含 Agent 配置（label/color/avatar/description）、当前活跃 Agent 追踪、Agent 切换事件处理。WebSocket 事件中 `agent_label` 字段驱动 Agent 气泡切换。

**Conversation Chat Input**:
聊天输入框组件。文本输入 + 文件/图片上传 + 语音录制（VoiceRecorder）+ Enter 发送。发送前自动调用 `ensureConversation()` 确保目标分区/对话存在（如无则自动创建默认链）。

**ResponseBlock Renderer**:
响应块分发渲染器。按 type + status 分派：TextBlock / VideoBlockRouter（嵌入/搜索结果）/ PracticeBlockRouter（交互式/被动式 InlinePracticeBlock）/ ImageBlock / AudioBlock / MindMapBlock / DocumentBlock / MediaSearchBlock / VideoEmbed。

**Switch Banner**:
上下文切换推荐横幅。WebSocket `context_switch` 事件触发，显示推荐切换的目标分区/对话。用户可确认切换或忽略。

**Sub-branch Banner**:
子支模式提示横幅。当用户进入子分支会话时显示，提示当前处于子分支模式及其父消息引用。

**Socratic Follow-up Bar (追问栏)**:
AI 回复下方展示 3 个递进式追问。点击即发送（调用 `store.sendMessage(question)`）。数据来自 `assistant_message.metadata.follow_up_questions`。

**Recommendation Banner**:
WebSocket `tree_recommendation` 事件触发的知识树推荐横幅。在对话流式结束时显示，引导用户前往知识树扩展。

### 知识图谱组件

**GraphDialoguePage**:
图谱主页面组件（588 行）。包含图谱可视化（三种视图） + 左侧树面板 + 右侧节点详情面板。内含 EmptyState（无知识树引导页）和 NoPartitionState（无分区引导页）。

**FocusGraph**:
思维导图布局的可视化组件（309 行）。用于聚焦模式下的图谱展示。

**ForceGraph**:
力导向布局组件。D3 力导向布局。节点颜色按掌握度映射，支持交互展开/编辑模式 CRUD。

**DAGGraph**:
依赖图视图（有向无环图）。展示节点间 prerequisite / extends / applies / related 关系。

**TreeChatPanel**:
全功能探索对话面板（知识树内 AI 对话）。含消息历史 + 输入框 + 推荐按钮。每个 KGNode 拥有独立探索会话，严格按 bound_node_id 作用域约束。

**NodeDetailPanel**:
节点详情面板（336 行）。展示节点元数据（label / description / mastery / priority / tags），支持内联编辑、AI 扩充、AI 对话快捷入口。

**KnowledgeCardNode**:
知识卡片节点组件（464 行）。图谱中的可视化节点元素，含 emoji/label/brief/mastery 色标。

### 图谱数据模型

**GraphNode**:
前端图谱节点类型。含 id / label / description / level / mastery(0-1) / trend(ascending|descending|stable) / priority(1-10) / tags / children / parent / is_visible / node_type / path_id / emoji / color / brief / conversation_ids。

**GraphEdge**:
前端图谱边类型。含 source / target / label / relation（parent | prerequisite | extends | applies | related）/ strength。

**GraphData**:
图谱完整数据。`{ nodes: GraphNode[], edges: GraphEdge[] }`。通过 `kgTreeToGraphData()` 从后端 KGTreeResponse 转换。

### 驾驶舱组件

**DashboardShell**:
驾驶舱外壳组件。含 Tab 切换系统，通过 URL tab 参数控制。

**OverviewTab**:
概览 Tab。含学习概览、快速入口、薄弱项、学习建议、成就展示。

**GraphTab**:
图谱 Tab。嵌入 FocusGraph 可视化，展示知识图谱结构。

**AnalyticsTab**:
分析 Tab。含 DailySummaryCard（每日摘要）/ HeatmapGrid（热力图）/ TrendChart（趋势图）/ RadarChart（雷达图）/ RetentionPanel（保留分析）。

**PlanTab**:
学习规划 Tab。展示学习计划、复习安排、目标进度。

**CalendarTab**:
日历 Tab。学习日历视图，含事件热力图。

**ErrorsTab**:
错题本 Tab。展示错题列表（含 error_type 标签），支持展开查看 LLM 错因分析 + 针对性推荐。

**AchievementsTab**:
成就 Tab。展示 12 种成就墙（青铜/白银/黄金），含已解锁/未解锁状态。

**QualityTab**:
质量报告 Tab。学习质量综合分析报告。

### 状态管理

**Zustand Stores (conversation store split)**:
已拆分为三个独立 store（2025-06-14）：
- `useConversationStore` — UI 状态 + 跨领域协调（详见上节 Store Architecture）
- `useTreeStore` — 树/图谱节点数据 + 展开状态
- `useMessageStore` — 消息/响应块数据

**Streaming Refs (streaming.ts)**:
已废弃。参见 StreamPipeline。
_Avoid_: 模块级 mutable refs（旧架构，双重真相源）

**StreamPipeline (流管线)**:
前端流输出管理深模块，取代旧 streaming.ts 的模块级 refs。封装 SSE 连接、token 累积与节流（200ms flush）、四阶段状态机（idle→streaming→paused→completing→idle）、刷新恢复缓存。通过依赖注入的 SSESource 接口解耦网络 I/O。对外通过类型化事件发射器（`subscribe<K>(event, cb)`）与 Zustand store / 通知模块通信。
- `beginStream(convId, dirId, placeholderMsgId)` — 启动流
- `pause() / resume() / stop()` — 流控制
- `getPhase(): StreamPhase` — 查询当前阶段
- `subscribe(event, cb)` — 订阅事件，返回 unsubscribe 函数
- `recover(convId): string | null` — 刷新恢复缓存
- **状态机**: idle → streaming ↔ paused → completing → idle（completing 后 5s 超时自动 idle）
_Avoid_: Streaming Refs、模块级可变变量

**Explain Store (explain-store)**:
解释卡片状态管理。独立的 Zustand store，管理 explain cards 的加载/展示/操作。

### 设计与布局

**App Shell**:
应用外壳布局。提供全局导航（侧边栏导航菜单 + 底部导航），ClientProviders 包裹（ThemeContext + AuthContext）。桌面端显示完整侧边栏，移动端显示底部导航 + 汉堡菜单。

**Design Language**:
纸墨质感设计系统。一套交互骨架 + 五套视觉风格：professional（现代专业，参考 Linear/Notion）/ playful（活力趣味，参考 Duolingo）/ knowledge（紧凑知识，参考 Obsidian）/ soft-data（柔和数据，参考 Apple Health/Books）/ gamified（游戏化激励）。每套风格支持亮暗双主题。

**Design Token**:
语义化设计令牌。五类：color（页面背景/表面/墨水/强调色/图谱色）、typography（hero/title/heading/subhead/body/caption/fine/code）、spacing（1-8）、radius（sm/md/lg/xl/full）、shadow（sm/md 仅浮层）、motion（fast/normal/slow/slower + ease 曲线）。
_Avoid_: CSS 变量（token 是语义层，CSS var 是实现层）

**Secretary Bell Badge**:
秘书铃铛徽章组件。在导航栏显示未读提案数量。

### 通用 UI 组件

**Card**:
通用卡片容器组件。
_Avoid_: Container、Box

**Empty State**:
空状态占位组件。含 icon / title / description / action 插槽。用于空知识树引导页、空数据提示等。

**Error Boundary**:
错误边界组件。捕获子组件渲染错误，展示友好提示。

**Skeleton**:
加载骨架屏组件。

**Inline Edit**:
行内编辑组件。点击文本进入编辑模式，支持回车确认/ESC 取消。

**Confirm Dialog**:
确认对话框组件。含标题/描述/确认/取消按钮。

**Math Content**:
数学公式渲染组件。基于 KaTeX 渲染 LaTeX 公式。
_Avoid_: MathJax（技术实现不对外暴露）

**Unified Search**:
全站统一搜索组件。

### 网关与代理

**Nginx 统一网关（推荐）**:
生产环境通过 Nginx :8080 统一入口。前端使用相对路径（`/api/*`、`/api/conversations/ws`），Nginx 按路径分发：
- `/api/conversations/ws` → Auth Gateway :18001（JWT 验证 + user_id 注入 → Backend）
- `/api/auth/*` → Auth Gateway :18001（认证 API）
- `/api/*` → Backend :8000（业务 API，后端本地解码 JWT）
- `/*` → Next.js :3000（SSR）

**Next.js Rewrites (开发/备用)**:
开发环境 (`next dev`) 下，Next.js rewrites 转发 `/api/*` 到 auth-gateway :18001，WS 直连 :18001。

**WebSocket Proxy**:
WS 连接通过 `ConversationWS` 类管理，使用相对路径 `/api/conversations/ws?token=xxx`。连接失败时自动指数退避重连（1s→30s 上限，退避系数 2x）。
_Avoid_: 直连后端 WS（必须经过 auth-gateway JWT 验证）

**HTTP Fallback**:
WS 不可用时的回退机制。`sendWSMessage()` 返回 false 时自动退化为 `POST /api/conversations/message`，解析 response 中的 assistant_message。

### Flagged ambiguities

- **"侧栏"** —— 树形导航用"侧栏"或 Partition Sidebar，图谱详情面板用"详情面板"。
- **"驾驶舱"** 对应 Dashboard，非"仪表盘"。
- **"首页"**(/) 与"驾驶舱"(/dashboard) 不同 —— 首页已 redirect → /dashboard。
- **"风格"** 与 "主题" —— Design Style 是五套视觉风格（professional/playful 等），Theme 是亮暗切换（light/dark）。
- **"AI 回复"** 面向用户用"AI 回复"，代码中 role 用 "assistant"。
- **"图谱"** 指知识图谱可视化页面和组件，非"知识树"（知识树是后端存储概念）。
- **"消息"** 与 "响应块" —— 消息（TreeNode）是整个对话单元，响应块（ResponseBlock）是 AI 回复内的模块化内容。
