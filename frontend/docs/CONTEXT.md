# Frontend — 智能伴学系统前端

Next.js 14 (App Router) 前端应用（23,072 行 TS/TSX），提供 AI 对话、练习中心、知识图谱、驾驶舱看板、秘书面板等学习功能界面。

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
全局设置页面（路由 `/settings`）。含子路由：`/settings/data`（数据管理：导出/导入/重置）。支持设计风格切换（professional / playful / knowledge / soft-data / gamified）、亮暗主题切换。

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

**Zustand Store (conversation-store)**:
全局状态仓库（873 行）。管理对话状态：selectedNode / partitions / messages / responseBlocks / wsConnected / isLoading / switchBanner / treeRefreshKey 等。action 拆分到 `actions/` 目录（send-message / partition-ops / nav-ops / tree-ops / sub-branch）。

**Streaming Refs (streaming.ts)**:
WebSocket 流式数据和连接管理的模块级 refs（367 行）。包含：`streamBufferRef`（累积 token）、`streamingMsgIdRef`（当前流式消息 ID）、`streamingContextRef`（当前流上下文）。管理 WS 生命周期 & 重连（指数退避 1s→2s→4s→...→30s）。

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

**Next.js Rewrites (API 代理)**:
Next.js rewrites 将所有 `/api/*` 和 `/ws/*` 请求转发到后端（127.0.0.1:8000）。实现前后端同源访问，避免 CORS。

**WebSocket Proxy**:
独立的 WS 升级代理路径：`/api/conversations/ws` 和 `/ws/:path*`。前端通过 `connectConversationWS()` 建立连接，6 个回调处理 WS 事件（onStatus / onToken / onDone / onError / onBlockUpdate / onContextSwitch）。
_Avoid_: 直连后端 WS（生产环境不使用）

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
