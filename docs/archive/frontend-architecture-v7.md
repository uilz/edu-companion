# 前端架构文档

> 总行数: 23,072 行 (TS/TSX)
> 生成日期: 2026-06-02

---

## 1. 整体架构概览

```
app/ (5,056 行)    → 路由层 + 页面组合
components/         → UI 组件层
  conversation/     → 对话系统 (5,719 行)
  dashboard/        → 驾驶舱面板 (4,585 行)
  graph/            → 知识图谱可视化 (3,403 行)
  layout/           → 全局布局 (339 行)
  ui/               → 通用 UI 组件 (446 行)
store/ (1,396 行)   → 全局状态 (Zustand)
lib/ (777 行)       → 工具函数 + API 客户端
types/ (205 行)     → 类型定义
```

### 数据流

```
用户输入 → page.tsx → 组件 → store(action) → API → store(state) → 组件(re-render)
                                  ↕
                          streaming.ts (WebSocket)
```

### 状态管理

- **Zustand**: 仅 `conversation-store.ts` (873行) 一个 Store
- **模块级 refs**: `streaming.ts` (367行) — WebSocket、流式缓存
- **组件内 state**: 大量使用 `useState` 持有局部状态

---

## 2. 路由结构 (app/)

| 路由 | 文件 | 行数 | 描述 |
|------|------|------|------|
| `/` | `page.tsx` | 346 | 首页 |
| `/learn` | `learn/page.tsx` | 21 | 学习空间 (ConversationPanel) |
| `/learn/graph` | `learn/graph/page.tsx` | — | 图谱学习 |
| `/dashboard` | `dashboard/page.tsx` | 107 | 驾驶舱 (含 tab 系统) |
| `/practice` | `practice/page.tsx` | 528 | 练习 |
| `/study` | `study/page.tsx` | 393 | 学习规划 |
| `/focus` | `focus/page.tsx` | — | 专注模式 (redirect → /learn) |
| `/graph` | `graph/page.tsx` | — | 知识图谱 |
| `/files` | `files/page.tsx` | 335 | 文件管理 |
| `/progress` | `progress/page.tsx` | 341 | 学习进度 |
| `/calendar` | `calendar/page.tsx` | 388 | 日历 |
| `/quality` | `quality/page.tsx` | 438 | 质量报告 |
| `/errors` | `errors/page.tsx` | 363 | 错题本 |
| `/analytics` | `analytics/page.tsx` | — | 数据分析 |
| `/achievements` | `achievements/page.tsx` | — | 成就系统 |
| `/stats` | `stats/page.tsx` | 249 | 统计数据 |
| `/secretary` | `secretary/page.tsx` | 253 | 秘书设置 |
| `/secretary/settings` | `secretary/settings/page.tsx` | 294 | 秘书详细设置 |
| `/settings` | `settings/page.tsx` | — | 全局设置 |

---

## 3. 对话系统 (conversation/)

### 3.1 组件层级

```
ConversationPanel (293行)
├── Phase8Sidebar (450行) — 左侧树形导航
│   └── SidebarTreeNode (207行) — 树节点
├── ConversationMessageArea (137行) — 共享消息区域
│   ├── SubBranchBanner (32行)
│   ├── SwitchBanner (51行)
│   ├── ErrorBanner (12行)
│   ├── MessageList (565行) — 消息渲染 + 操作
│   ├── SocraticFollowUpBar (43行)
│   ├── ChatInput (282行) — 输入框
│   └── [renderBottomControls]
└── MobileBottomSheet (30行) — 移动端导航

FocusModePanel (212行)
├── PartitionPicker (122行)
├── ConversationMessageArea (同上)
└── GraphPanel (102行) — 图谱面板
    ├── FocusGraph (309行) — 思维导图
    └── ForceGraph — 力导向图

其他组件 (同级):
  blocks/  — 内容块渲染器 (TextBlock, ImageBlock, VideoBlockRouter, etc.)
  ws.ts — WebSocket 客户端
  useConversation.ts — store facade hook
  useSocraticMode.ts — 苏格拉底模式 hook
  ...
```

### 3.2 状态层

```
streaming.ts (367行)
├── 模块级 refs (_activeConvId, _streamBuffer, etc.)
├── sessionStorage 流式缓存
├── URL + localStorage 同步
├── WebSocket 初始化
└── isSending flag

tree-helpers.ts (156行)
├── apiFetch / v2Fetch
├── fireClassify
└── ensureConversationAtLevel

conversation-store.ts (873行)
├── ConversationState 接口 (90行)
├── Zustand store init (30行)
├── Navigation actions (70行)
├── Partition actions (50行)
├── Message actions:
│   ├── loadMessages (40行)
│   ├── sendMessage (280行) ← 最大的单一方法
│   ├── deleteMessage (30行)
│   ├── editMessage (40行)
│   └── versionSwitch (50行)
├── Conversation creation: handleNewConversation (100行)
└── Sub-branch actions: enter, exit, create, load (80行)
```

---

## 4. 驾驶舱 (dashboard/)

### 4.1 Tab 结构

```
DashboardShell (模板)
├── OverviewTab (388行) — 概览
├── AnalyticsTab (351行) — 分析
├── ProgressTab (341行) — 进度
├── GraphTab (628行) — 图谱 ← 最大 Tab
├── CalendarTab (398行) — 日历
├── StudyTab (246行) — 学习
├── PlanTab (381行) — 计划
├── QualityTab (426行) — 质量
├── ErrorsTab (384行) — 错题
├── StatsTab (—) — 统计
├── AchievementsTab (—) — 成就
└── FocusTab (—) — 专注
```

### 4.2 各 Tab 独立架构

每个 Tab 是自包含组件，直接从 API 获取数据，不共享状态。部分 Tab 有子目录:
- `analytics/` — 子组件: DailySummaryCard, HeatmapGrid, TrendChart, etc.

---

## 5. 知识图谱 (graph/)

```
GraphDialoguePage (588行) — 图谱对话页面
├── FocusGraph (309行) — 思维导图布局
├── ForceGraph — 力导向布局
├── KnowledgeCardNode (464行) — 知识卡片节点
├── DialogueCardList (—) — 对话卡片列表
├── ProjectsPanel (252行) — 项目面板
├── GoalSettingModal (255行) — 目标设置
├── ReflectionModal (300行) — 反思弹窗
├── NoteSidebar (—) — 笔记侧栏
├── DeepReadToolbar (—) — 深度阅读工具栏
├── ExplainModal (—) — 解释弹窗
├── AggregateNotesModal (—) — 笔记聚合
└── MindMapGraph (—) — 思维导图
```

---

## 6. 跨模块依赖分析

```
conversation ← store  ← conversation (双向依赖!)
    (组件调用 store)     (store 引用 ws.ts)

dashboard → graph
    (GraphTab 引用 FocusGraph)

conversation → types
conversation → lib (api.ts, graph-api.ts)
conversation → ui (NewNodeDialog)
```

---

## 7. 优化建议

### 🚨 优先级 P0 — 必须优化

| 问题 | 文件 | 现状 | 建议 |
|------|------|------|------|
| **超级 Store** | `conversation-store.ts` (873行) | 单文件包含全部 action 实现，`sendMessage` 280 行 | 拆分为 `actions/` 子模块：`send-message.ts`, `load-messages.ts`, `tree-ops.ts`, `sub-branch.ts` |
| **超大渲染器** | `MessageList.tsx` (565行) | 消息渲染、引用选择、版本切换、编辑全部内联 | 提取 `MessageRow.tsx`(渲染)、`MessageActions.tsx`(操作)、`MessageQuote.tsx`(引用) |
| **Maxi Tab** | `GraphTab.tsx` (628行) | dashboard 内最大文件，混合图谱 + 对话 + 节点操作 | 拆分至少 3 个逻辑区域，部分逻辑复用 graph/ 组件 |

### ⚠️ 优先级 P1 — 重要

| 问题 | 现状 | 建议 |
|------|------|------|
| **Store 单一化** | 仅 1 个 Zustand store，所有 conversation 状态集中 | 拆分领域 Store: `chat-store.ts`, `sidebar-store.ts`, `partitions-store.ts`（useShallow 按需组合） |
| **app/page 过大** | `practice/page.tsx`(528行)、`study/page.tsx`(393行) 内联大量逻辑 | 提取页面逻辑到 `usePracticePage`, `useStudyPage` hooks；页面只做组合 |
| **Dashboard Tab 缺乏共享层** | 每个 Tab 独立 fetch、独立 loading | 引入 `useTabData` 通用 hook 或 SWR/React Query 做缓存 + 状态管理 |
| **双向依赖** | `store → ws.ts`, `ws.ts → store types` | 拆分 `ws.ts` 类型到独立文件，store 只依赖类型 |

### 💡 优先级 P2 — 建议

| 问题 | 现状 | 建议 |
|------|------|------|
| **组件层级扁平** | conversation/ 下 40+ 个文件同级 | 按逻辑分组: `layout/`(Panel, FocusMode), `messages/`(List, Input, blocks), `sidebar/`(Sidebar, Tree, Picker) |
| **graph/ 与 conversation/ 边界模糊** | FocusGraph 引用 conversation store，GraphDialoguePage 混合图谱+对话 | 定义 graph 领域的独立 store，通过事件桥接或 callback 通信 |
| **缺少组件测试** | 0 个组件测试 | 优先为 banners/ 和 blocks/ 添加 Storybook 或 vitest 测试 |
| **API 客户端重复** | tree-helpers.ts 和 lib/api.ts 各自实现 fetch 封装 | 统一为一个 API 客户端，支持 interceptor/middleware |
| **渲染性能** | MessageList 每次 store 更新全量 re-render | MessageList 使用 React.memo + 虚拟列表（react-window） |

### 📊 按模块统计

| 模块 | 行数 | 占比 | P0 问题 | P1 问题 |
|------|------|------|---------|---------|
| conversation | 5,719 | 24.8% | 2 | 1 |
| dashboard | 4,585 | 19.9% | 1 | 1 |
| app/ | 5,056 | 21.9% | — | 1 |
| graph | 3,403 | 14.8% | — | 1 |
| store | 1,396 | 6.0% | 1 | 2 |
| layout | 339 | 1.5% | — | — |
| lib | 777 | 3.4% | — | 1 |
| types | 205 | 0.9% | — | — |
