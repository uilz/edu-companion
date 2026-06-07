# Phase 11：知识树重构 — 独立页面 + 全局对话 + 交互升级

> 版本: v1.0
> 最后更新: 2026-06-06
> 状态: 设计提案

---

## 目录

- [1. 背景与动机](#1-背景与动机)
- [2. PRD：产品需求](#2-prd产品需求)
  - [2.1 核心目标](#21-核心目标)
  - [2.2 关键决策](#22-关键决策)
  - [2.3 功能全景](#23-功能全景)
- [3. 页面布局设计](#3-页面布局设计)
  - [3.1 布局架构](#31-布局架构)
  - [3.2 两栏模式](#32-两栏模式)
  - [3.3 三栏模式](#33-三栏模式)
  - [3.4 图层面板](#34-图层面板)
- [4. 交互详细设计](#4-交互详细设计)
  - [4.1 C1：画布操作](#41-c1画布操作)
  - [4.2 C2：节点编辑](#42-c2节点编辑)
  - [4.3 C5：信息浏览](#43-c5信息浏览)
  - [4.4 C6：搜索与聚焦](#44-c6搜索与聚焦)
- [5. 对话系统设计](#5-对话系统设计)
  - [5.1 全局对话 vs 节点探索对话](#51-全局对话-vs-节点探索对话)
  - [5.2 对话展现形态](#52-对话展现形态)
  - [5.3 对话能力矩阵](#53-对话能力矩阵)
  - [5.4 后端 API 增量](#54-后端-api-增量)
- [6. 后端变更](#6-后端变更)
  - [6.1 新增 API](#61-新增-api)
  - [6.2 现有 API 适配](#62-现有-api-适配)
- [7. 前端变更](#7-前端变更)
  - [7.1 文件变动清单](#71-文件变动清单)
  - [7.2 新增组件](#72-新增组件)
  - [7.3 修改组件](#73-修改组件)
  - [7.4 废弃组件](#74-废弃组件)
- [8. 数据模型变更](#8-数据模型变更)
- [9. 实现路径](#9-实现路径)
  - [9.1 Phase 1：基础重构](#91-phase-1基础重构)
  - [9.2 Phase 2：画布交互升级](#92-phase-2画布交互升级)
  - [9.3 Phase 3：全局对话能力](#93-phase-3全局对话能力)
  - [9.4 Phase 4：体验打磨](#94-phase-4体验打磨)

---

## 1. 背景与动机

当前知识树位于 `/resources` 页面的一个 tab（`knowledge-tree`）中，使用全屏 `fixed` 布局覆盖在资源页之上。主要问题：

1. **对话门槛高**：对话面板隐藏在左侧面板的 tab 中，必须选中节点才能展示，且只能操作当前节点及其子孙节点（作用域约束）
2. **缺少全局视角对话**：无法对整个知识树进行总结、提问、获取学习路径推荐
3. **画布交互薄弱**：节点点击热区小、不支持拖拽布局、无右键菜单/双击编辑等高效操作
4. **信息浏览卡顿**：查看节点详情需要打开右侧面板，无法在图上游走式浏览
5. **搜索定位不足**：层级多时容易迷路，缺少鱼眼聚焦、层级折叠等辅助导航

## 2. PRD：产品需求

### 2.1 核心目标

| 目标 | 描述 |
|------|------|
| G1 | 知识树成为独立页面，脱离 `/resources` 下的 tab 嵌套 |
| G2 | 全局对话随时可用，两种形态（侧栏/浮动），用户可切换 |
| G3 | 画布交互达到专业图谱工具水准（拖拽、双击、右键、快捷键） |
| G4 | 信息浏览流畅，悬停速览 + 点击聚焦 + 键盘游走 |
| G5 | 搜索定位无死角，鱼眼聚焦 + 层级折叠 + 自动缩放 |

### 2.2 关键决策

| 决策 | 选项 | 结论 |
|------|------|------|
| 页面定位 | `/resources` tab vs 独立路由 | **独立路由** `/knowledge-tree` |
| 左侧面板 | 保留 tab 式 vs 抽走 | **抽走左侧面板**，对话变成两种可切换形态 |
| 布局 | 固定三栏 vs 可切换 | **两栏/三栏可切换** |
| 对话范围 | 仅节点作用域 vs 全局+节点 | **两者兼有**，全局对话默认，选中节点可切换上下文 |
| 布局持久化 | 不保存 vs 保存 | **保存到 localStorage**（布局模式、面板宽度、画布位置） |

### 2.3 功能全景

```
知识树独立页面 (/knowledge-tree)
├── 顶部导航栏
│   ├── 分区选择器（下拉切换）
│   ├── 视图模式切换（思维导图/力导向/依赖图）
│   ├── 两栏/三栏切换按钮
│   ├── 对话形态切换（侧栏/浮动）
│   └── 搜索框
│
├── 图谱画布（核心区域）
│   ├── 拖拽布局（自由排列 + 布局持久化）
│   ├── 鼠标悬停 → Tooltip 摘要
│   ├── 点击 → 居中 + 详情浮层
│   ├── 双击 → 内联编辑
│   ├── 右键 → 上下文菜单
│   ├── 键盘方向键 → 相邻节点跳转
│   ├── 鱼眼聚焦（搜索后自动放大匹配子图）
│   ├── 层级折叠（折叠/展开子树）
│   └── 缩放至适配（选中节点后自动调整比例）
│
├── 对话（两种形态可切换）
│   ├── A1：侧栏式（固定在左侧/右侧）
│   └── A3：浮动气泡式（可拖拽小窗）
│   ├── 全局模式（默认）：对整个知识树提问
│   └── 节点模式（选中后可选）：对当前节点及其子树提问
│
├── 右侧详情面板（三栏模式下显示）
│   └── NodeDetailPanel（现有组件适配）
│
└── 底部状态栏
    └── 节点统计（总数/已掌握/学习中/平均掌握度）
```

## 3. 页面布局设计

### 3.1 布局架构

```
┌──────────────────────────────────────────────────────────────┐
│  顶部导航栏（分区选择 | 视图切换 | 布局切换 | 搜索 | ... ） │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────┬────────────────────────┬──────────────┐   │
│   │              │                        │              │   │
│   │   对话面板    │      图谱画布          │  节点详情    │   │
│   │   (侧栏式)   │   (核心区域)           │  (三栏模式)  │   │
│   │              │                        │              │   │
│   │  隐藏/显示   │  可切换三种视图        │  隐藏/显示   │   │
│   │              │                        │              │   │
│   └──────────────┴────────────────────────┴──────────────┘   │
│                                                              │
│   ┌────────────────────────────────────────────────────┐     │
│   │  状态栏（节点统计信息）                              │     │
│   └────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘

浮动气泡模式（A3）：
         ┌──────┐
         │  💬   │ ← 可拖拽浮动按钮
         └──────┘
              ↓ 点击展开
         ┌──────────────┐
         │ 对话浮窗      │ ← 独立小窗，不占布局
         │ 输入框        │
         │ 消息列表      │
         └──────────────┘
```

### 3.2 两栏模式

| 区域 | 宽度 | 说明 |
|------|------|------|
| 对话面板 | 320px（可拖拽调整） | 侧栏式对话，可折叠为图标 |
| 图谱画布 | `calc(100% - 320px)` 或 `100%`（折叠时） | 核心图谱区域 |

**布局来源**：`/home/deploy/edu-companion/frontend/src/components/graph/pages/GraphDialoguePage.tsx`

**两栏触发条件**：
- 用户点击"两栏"按钮
- 三栏模式下用户关闭右侧详情面板

### 3.3 三栏模式

| 区域 | 宽度 | 说明 |
|------|------|------|
| 对话面板 | 280px（可折叠） | 更窄以适应三栏 |
| 图谱画布 | `flex: 1` | 自适应 |
| 节点详情 | 320px（可折叠） | 使用现有 `NodeDetailPanel` |

**三栏触发条件**：
- 用户点击"三栏"按钮
- 选中节点时自动展开右侧详情（可选，用户偏好设置）

**布局偏好持久化**：
```typescript
// localStorage key: "knowledge-tree-layout"
interface LayoutPreference {
  mode: "two-column" | "three-column";
  dialogWidth: number;      // 对话面板宽度（px）
  detailWidth: number;      // 详情面板宽度（px）
  dialogStyle: "sidebar" | "float";
  graphMode: "mindmap" | "force" | "dag";
  // 画布状态
  canvasPosition?: { x: number; y: number; zoom: number };
  // 对话侧边位置
  dialogSide: "left" | "right";
}
```

### 3.4 图层面板

用于搜索/聚焦/层级折叠：

```
┌──────────────┐
│  🔍 搜索节点 │ ← 全局搜索，结果高亮
├──────────────┤
│  📂 层级树   │ ← 树形目录，点击定位
│  ├─ 微积分   │
│  │  ├─ 极限   │
│  │  └─ 导数   │
│  └─ 线性代数 │
├──────────────┤
│  显示控制     │
│  ☑ 已掌握     │
│  ☑ 学习中     │
│  ☑ 未接触     │
└──────────────┘
```

图层面板可叠加在画布左上角，默认收起，点击展开。

## 4. 交互详细设计

### 4.1 C1：画布操作

#### 4.1.1 节点拖拽

**当前现状**：`ForceGraph` 和 `FocusGraph` 不支持手动拖拽节点位置。

**改造方案**：

| 视图 | 拖拽支持 | 说明 |
|------|---------|------|
| 思维导图（FocusGraph） | ✅ 支持 | 拖拽叶子节点微调位置，根节点和主干固定 |
| 力导向（ForceGraph） | ✅ 支持 | D3 力模拟 + 拖拽固定（drag 后 pin 住位置） |
| 依赖图（DAGGraph） | ❌ 不支持 | DAG 布局由拓扑排序决定，不适合手动拖拽 |

**布局持久化**：
- 用户拖拽后的位置保存到 `localStorage`
- 下一次打开同一分区知识树时恢复
- 提供"重置布局"按钮回到默认布局

**涉及文件**：
- `/home/deploy/edu-companion/frontend/src/components/graph/graphs/ForceGraph.tsx` — 添加 D3 drag + pin
- `/home/deploy/edu-companion/frontend/src/components/graph/graphs/FocusGraph.tsx` — 添加叶子节点拖拽

#### 4.1.2 点击热区扩大

**当前现状**：`KnowledgeCardNode` 的可点击区域仅为文字标签和掌握度环。

**改造方案**：
- 节点卡片整体作为点击热区（包含 padding 和 margin）
- `cursor: pointer` + hover 背景高亮
- 点击区域至少 44x44px（WCAG 无障碍标准）

**涉及文件**：
- `/home/deploy/edu-companion/frontend/src/components/graph/nodes/KnowledgeCardNode.tsx`

#### 4.1.3 画布平移与缩放

**当前现状**：三种视图各自实现平移缩放，行为不完全一致。

**改造方案**：
- 统一使用 D3 zoom behavior
- 缩放范围：0.2x ~ 3x（当前 0.3x~2x 偏保守）
- 缩放跟随鼠标位置（pinch zoom 中心点）
- 滚轮操作时不触发页面滚动（已有实现，保持）
- 添加缩略图导航（minimap，画布右下角）

**涉及文件**：
- `/home/deploy/edu-companion/frontend/src/components/graph/graphs/ForceGraph.tsx`
- `/home/deploy/edu-companion/frontend/src/components/graph/graphs/FocusGraph.tsx`
- `/home/deploy/edu-companion/frontend/src/components/graph/graphs/DAGGraph.tsx`
- 新增：`Minimap.tsx` (组件)

### 4.2 C2：节点编辑

#### 4.2.1 双击内联编辑

**行为**：
- 双击节点 → 标签变为可编辑 `<input>`
- Enter 或失焦 → 保存
- Escape → 取消
- 支持同时编辑标签和描述（双击后展开快速编辑浮层）

```
双击前：          双击后：
┌──────────┐     ┌──────────┐
│ 极限与连续 │     │ [极限与连续]│ ← input 框
│          │     │ 理解极限  │ ← 描述也可编辑
└──────────┘     │ 概念...   │
                  └──────────┘
```

**API 复用**：
```
PATCH /api/knowledge/graph/{pid}/node/{nid}
Body: { "label": "新名称", "description": "新描述" }
```

**涉及文件**：
- `/home/deploy/edu-companion/frontend/src/components/graph/nodes/KnowledgeCardNode.tsx`
- `/home/deploy/edu-companion/frontend/src/components/graph/pages/GraphDialoguePage.tsx`

#### 4.2.2 右键上下文菜单

**菜单项**：

| 菜单项 | 操作 | 后端 API |
|--------|------|---------|
| 编辑节点 | 触发内联编辑模式 | — |
| 添加子节点 | 弹出添加弹窗，预设父节点 | `POST /api/knowledge/graph/{pid}/node` |
| AI 扩充子节点 | 调用 AI 生成子节点 | `POST /api/knowledge/graph/{pid}/ai-expand` |
| AI 编辑内容 | 调用 AI 优化节点描述 | `POST /api/knowledge/graph/{pid}/ai-edit` |
| 关联会话 | 弹出会话搜索/选择框 | `POST /api/knowledge/graph/{pid}/link-conversation` |
| 删除节点 | 确认后删除（级联删边） | `DELETE /api/knowledge/graph/{pid}/node/{nid}` |
| 复制节点 ID | 复制到剪贴板 | — |
| 请求讲解 | 触发 AI 讲解 | 前端事件转发 |

**涉及文件**：
- 新增：`ContextMenu.tsx`（通用右键菜单组件）
- 修改：`KnowledgeCardNode.tsx` — 右键事件绑定

### 4.3 C5：信息浏览

#### 4.3.1 悬停 Tooltip

**行为**：
- 鼠标悬停节点 300ms → 显示 Tooltip
- Tooltip 内容：节点名称 + 掌握度 + 简要描述（前 50 字）
- 离开节点区域 → Tooltip 消失（300ms 延迟）

```
┌─────────────────┐
│ 极限与连续        │
│ 掌握度: 85% ✅   │
│ 理解极限概念，掌握 │
│ 连续函数性质...   │
└─────────────────┘
   ▲
   │
┌──────┐
│ 节点  │ ← 鼠标悬停
└──────┘
```

**涉及文件**：
- 新增：`NodeTooltip.tsx`
- 修改：`KnowledgeCardNode.tsx` — 添加 hover 事件

#### 4.3.2 点击居中 + 详情浮层

**行为**：
- 点击节点 → 画布动画居中到该节点 + 缩放至合适比例
- 同时弹出轻量详情浮层（overlay，非侧栏）
- 浮层内容：完整描述 + 标签 + 优先级 + 关联会话数
- 浮层上的操作按钮：编辑 / AI 扩充 / 请求讲解 / 打开右侧详情面板
- 点击空白处或关闭按钮 → 浮层消失

```
                    ┌─────────────────────┐
                    │ 极限与连续            │
                    │ ─────────────       │
                    │ 理解极限概念，掌握     │
                    │ 连续函数性质...       │
                    │ 标签: 📐微积分 🎯基础  │
                    │ 优先级: ⭐⭐⭐⭐       │
                    │ 关联: 3个会话         │
                    │                      │
                    │ [编辑] [AI扩充] [讲解] │
                    └─────────────────────┘
                              ▲
                              │ 点击居中 + 浮层
                    ┌──────────┐
                    │   节点     │
                    └──────────┘
```

**涉及文件**：
- 新增：`NodeDetailPopover.tsx` — 详情浮层组件
- 修改：`GraphDialoguePage.tsx` — 点击事件重定向到浮层而非侧栏

#### 4.3.3 键盘导航

**行为**：
- 选中一个节点后：
  - `↑/↓`/`←/→`：跳转到相邻节点（根据图谱布局的最近邻）
  - `Enter`：选中并触发详情浮层
  - `Tab`/`Shift+Tab`：按拓扑顺序跳转前一个/后一个节点
  - `Escape`：取消选中
  - `F2`：进入内联编辑模式
  - `Delete`/`Backspace`：删除节点（需确认）

**涉及文件**：
- 新增：`useKeyboardNavigation.ts` — 键盘导航 hook
- 修改：`GraphDialoguePage.tsx` — 全局键盘事件监听

### 4.4 C6：搜索与聚焦

#### 4.4.1 搜索交互

**当前现状**：已有搜索框（`graphSearch` + `matchedNodeIds`），但仅高亮匹配节点。

**改造方案**：
- 搜索框从顶部工具栏移动到"图层面板"中（参见 3.4），同时在顶部保留快捷搜索入口
- 输入实时过滤（300ms debounce）
- 匹配节点高亮 + 自动聚焦第一个匹配节点

#### 4.4.2 鱼眼聚焦

**行为**：
- 用户选中一个节点或点击搜索结果 → 触发鱼眼聚焦
- 画布放大到该节点为中心
- 周围 2 层以内的节点保持可见，外层节点透明度降低或隐藏
- 提供"退出聚焦"按钮或 Escape 退出

```
聚焦前：                    聚焦后：
┌──────────────────┐       ┌──────────────────┐
│  o  o  o  o  o   │       │    o  o          │
│  o  [目标] o  o  │  →    │  o [目标] o      │ ← 放大+聚焦
│  o  o  o  o  o   │       │    o  o          │
│  o  o  o  o  o   │       │  (外层淡出)      │
└──────────────────┘       └──────────────────┘
```

**涉及文件**：
- 修改：三种 Graph 组件 — 添加聚焦模式
- 新增：`useFishEye.ts` — 鱼眼聚焦逻辑

#### 4.4.3 层级折叠

**行为**：
- 根节点和中间层节点可折叠/展开子树
- 折叠后子节点隐藏，节点上显示"已折叠 N 个节点"标签
- 图层面板中的层级树同步折叠状态

```
折叠前：              折叠后：
┌──────┐            ┌──────┐
│ 微积分 │            │ 微积分 │
│ ├─极限 │            │ [+]  │ ← 显示 + 图标
│ ├─导数 │            │ 已折叠 │
│ └─积分 │            │ 3项   │
└──────┘            └──────┘
```

**涉及文件**：
- 修改：三种 Graph 组件 — 添加折叠状态
- 修改：`GraphDialoguePage.tsx` — 管理折叠状态

#### 4.4.4 缩放至适配

**行为**：
- 选中节点后，自动计算合适的缩放比例使该节点及其子节点完整可见
- 动画过渡（300ms ease-in-out）
- 已有实现：`FocusGraph` 的 `focusOnNode` 能力，统一到所有视图

## 5. 对话系统设计

### 5.1 全局对话 vs 节点探索对话

| 维度 | 全局对话（新） | 节点探索对话（现有） |
|------|---------------|-------------------|
| 作用域 | 整个知识树 | 当前节点及其子孙节点 |
| 能力 | 总结、推荐路径、操作任意节点 | 编辑/扩充当前子树 |
| 入口 | 页面默认展示 | 选中节点 + 切换上下文 |
| API | 新增 `POST /api/knowledge/graph/{pid}/ai-global-chat` | 现有 `POST .../ai-chat` |

**上下文切换逻辑**：
- 默认：全局对话
- 用户选中节点后，对话上方出现切换按钮："切换到此节点的探索对话"
- 切换后，对话上下文限定到该节点及子树
- 节点取消选中时，自动切回全局对话
- 对话历史：全局和节点各自独立保存

```
┌──────────────────────────┐
│ 💬 全局对话（当前）       │ ← 上下文标识
│                          │
│ ┌──────────────────────┐ │
│ │ AI: 这棵树覆盖了...   │ │
│ │ User: 我该从哪开始？  │ │
│ └──────────────────────┘ │
│                          │
│ [输入框...                │
│ [发送]                    │
│                          │
│ [切换到「极限与连续」探索] │ ← 切换按钮（当选中节点时出现）
└──────────────────────────┘
```

### 5.2 对话展现形态

#### A1：侧栏式（默认）

- 固定在页面左侧（用户可配置为右侧）
- 宽度 280-320px，可拖拽调整
- 可折叠为窄图标（40px）
- 与顶部导航栏平齐高度

#### A3：浮动气泡式

- 浮动按钮在页面右下角（可拖拽改变位置）
- 点击展开为独立的对话浮窗
- 浮窗默认尺寸：360x500px（可调整）
- 浮窗位置保存到 localStorage
- 浮窗与侧栏是同一套对话组件，只是渲染容器不同

**组件复用**：
```
DialogContainer (抽象层)
├── SidebarDialog (侧栏式)
│   ├── 固定定位 + 可折叠
│   └── 使用 DialogHeader + DialogBody + DialogInput
│
└── FloatDialog (浮动气泡式)
    ├── 浮动按钮 + 弹窗
    └── 使用 DialogHeader + DialogBody + DialogInput (复用)
```

### 5.3 对话能力矩阵

| 能力 | 全局对话 | 节点探索对话 |
|------|---------|-------------|
| 知识树总结（"这棵树覆盖了哪些内容？"） | ✅ | ✅ (当前子树) |
| 学习路径推荐（"我接下来应该学什么？"） | ✅ | ✅ (子树内路径) |
| 自然语言操作节点（"把 X 的优先级设为 5"） | ✅ | ✅ |
| 创建节点（"在 Y 下加一个子节点 Z"） | ✅ | ✅ |
| 删除节点（"删除过时的 W 节点"） | ✅ | ✅ |
| 编辑节点内容（"把 V 的描述改得更通俗"） | ✅ | ✅ |
| 创建/删除边（"在 A 和 B 之间加一条依赖边"） | ✅ | ✅ |
| 跨分区操作（"把 C 节点移到另一个分区"） | ❌ | ❌ |
| 关联会话到节点 | ✅ | ✅ |
| 掌握度分析（"我哪些部分掌握得不好？"） | ✅ | ✅ (子树内) |

### 5.4 后端 API 增量

#### 新增：全局对话端点

```
POST /api/knowledge/graph/{pid}/ai-global-chat

Request:
{
  "message": "总结一下这棵树",
  "conversation_id": "可选，不传则创建新会话"
}

Response (streaming):
{
  "type": "text" | "operation" | "recommendation",
  "content": "..."
}
```

**System Prompt 设计**：

```
你是一个知识树 AI 助手。你有完全的读写权限访问当前知识树的所有节点和边。
你可以：
1. 查询和总结知识树结构
2. 推荐学习路径
3. 根据用户指令创建/编辑/删除节点和边
4. 分析掌握度分布

操作输出格式：
<!--OPERATION-->
{"action": "create_node" | "update_node" | "delete_node" | "create_edge" | "delete_edge", ...}
<!--/OPERATION-->

推荐输出格式：
<!--RECOMMEND-->
{"type": "learning_path" | "deep_dive" | "parent", ...}
<!--/RECOMMEND-->
```

#### 后端处理流程

```
ai-global-chat 请求
  → 加载知识树全量节点+边到 context
  → 发送给 LLM（含 system prompt + 历史 + 用户消息）
  → 流式解析 text / OPERATION / RECOMMEND 标记
  → text → 直接流式返回
  → OPERATION → 执行树操作 + 返回操作结果
  → RECOMMEND → 返回推荐数据
```

**涉及文件**：
- 新增：`/home/deploy/edu-companion/backend/app/api/knowledge/knowledge_routes/global_chat.py`
- 修改：`/home/deploy/edu-companion/backend/app/api/knowledge/knowledge.py` — 注册新路由

## 6. 后端变更

### 6.1 新增 API

| 方法 | 路由 | 功能 | 文件 |
|------|------|------|------|
| `POST` | `/api/knowledge/graph/{pid}/ai-global-chat` | 全局对话（流式） | `knowledge_routes/global_chat.py` |

### 6.2 现有 API 适配

无需修改现有 API。现有 `ai-chat` 端点保留作为节点探索对话使用。全局对话是新端点，共享相同的树操作能力但作用域不同。

## 7. 前端变更

### 7.1 文件变动清单

```
新增文件：
├── frontend/src/app/knowledge-tree/page.tsx          # 独立页面路由
├── frontend/src/components/knowledge-tree/           # 新组件目录
│   ├── KnowledgeTreePage.tsx                          # 主页面（替代 GraphDialoguePage）
│   ├── DialogContainer.tsx                            # 对话容器抽象层
│   ├── SidebarDialog.tsx                              # 侧栏式对话
│   ├── FloatDialog.tsx                                # 浮动气泡对话
│   ├── ContextMenu.tsx                                # 右键菜单
│   ├── NodeTooltip.tsx                                # 悬停 tooltip
│   ├── NodeDetailPopover.tsx                          # 点击详情浮层
│   ├── LayerPanel.tsx                                 # 图层面板（搜索+层级+筛选）
│   ├── Minimap.tsx                                    # 缩略图导航
│   └── LayoutToggle.tsx                               # 布局切换按钮
├── frontend/src/hooks/knowledge-tree/
│   ├── useKeyboardNavigation.ts                       # 键盘导航
│   ├── useFishEye.ts                                  # 鱼眼聚焦
│   └── useLayoutPreference.ts                         # 布局偏好持久化

修改文件：
├── frontend/src/components/graph/pages/GraphDialoguePage.tsx  # → 重构为 KnowledgeTreePage
├── frontend/src/components/graph/nodes/KnowledgeCardNode.tsx  # 双击编辑 + 右键 + 热区扩大
├── frontend/src/components/graph/graphs/ForceGraph.tsx        # 拖拽 + 聚焦模式 + 层级折叠
├── frontend/src/components/graph/graphs/FocusGraph.tsx        # 拖拽 + 聚焦模式 + 层级折叠
├── frontend/src/components/graph/graphs/DAGGraph.tsx          # 聚焦模式 + 层级折叠
├── frontend/src/components/graph/panels/NodeDetailPanel.tsx   # 适配新布局
├── frontend/src/components/graph/panels/TreeChatPanel.tsx     # → 适配 DialogContainer 接口
├── frontend/src/app/resources/page.tsx                        # 移除 knowledge-tree tab
├── frontend/src/hooks/graph/useGraphDialogue.ts               # → 适配新状态

废弃/重定向：
├── frontend/src/app/graph/page.tsx               # → 301 重定向到 /knowledge-tree
├── frontend/src/app/learn/graph/page.tsx          # → 301 重定向到 /knowledge-tree
```

### 7.2 新增组件

#### KnowledgeTreePage.tsx（主页面）

替代现有 `GraphDialoguePage.tsx`，主要变化：
- 不再包裹在 `/resources` 的 fullscreen fixed 布局中
- 独立页面路由 `/knowledge-tree`
- 顶部导航栏整合所有操作
- 布局管理（两栏/三栏切换）
- 对话管理（侧栏/浮动切换）

```typescript
// 组件接口
interface KnowledgeTreePageProps {
  // 无 props，所有状态通过 useKnowledgeTreeStore 管理
}

// 核心状态（Zustand store）
interface KnowledgeTreeState {
  // 数据
  partitionId: string | null;
  partitions: Partition[];
  graphData: KGTreeResponse | null;
  selectedNode: GraphNode | null;
  loading: boolean;
  error: string | null;

  // 布局
  layoutMode: "two-column" | "three-column";
  dialogStyle: "sidebar" | "float";
  dialogSide: "left" | "right";
  dialogOpen: boolean;
  detailOpen: boolean;

  // 对话
  dialogMode: "global" | "node";  // 全局 vs 节点探索
  dialogMessages: ChatMessage[];
  globalConvId: string;

  // 图层面板
  layerOpen: boolean;
  searchQuery: string;
  matchedNodeIds: string[];
  collapsedNodeIds: Set<string>;
  focusMode: boolean;
  focusNodeId: string | null;

  // 画布
  graphMode: "mindmap" | "force" | "dag";
  graphFullscreen: boolean;

  // 操作
  loadGraph: () => Promise<void>;
  selectNode: (node: GraphNode | null) => void;
  // ...
}
```

#### DialogContainer.tsx（对话容器抽象层）

```typescript
interface DialogContainerProps {
  style: "sidebar" | "float";
  onStyleChange: (style: "sidebar" | "float") => void;
  mode: "global" | "node";    // 全局 vs 节点探索
  onModeChange: (mode: "global" | "node") => void;
  nodeContext?: GraphNode;    // 节点探索模式下的绑定节点
  // 对话内容由内部 TreeChatPanel 或 GlobalChatPanel 管理
}
```

### 7.3 修改组件

#### KnowledgeCardNode.tsx

当前 464 行，需新增/修改：

| 功能 | 改动量 | 说明 |
|------|--------|------|
| 点击热区扩大 | ~20 行 | 外层 div 增加 padding 和 cursor |
| 双击编辑 | ~60 行 | 双击切换为 input，Enter/Escape 处理 |
| 右键菜单 | ~30 行 | 绑定 onContextMenu，弹出 ContextMenu |
| 悬停 Tooltip | ~20 行 | onMouseEnter/Leave 延迟显示 Tooltip |

#### ForceGraph.tsx / FocusGraph.tsx / DAGGraph.tsx

| 功能 | ForceGraph | FocusGraph | DAGGraph |
|------|-----------|-----------|---------|
| 节点拖拽 | ✅ 新增（D3 drag+pin） | ✅ 新增（叶子节点） | ❌ |
| 鱼眼聚焦 | ✅ 新增 | ✅ 新增 | ✅ 新增 |
| 层级折叠 | ✅ 新增 | ✅ 新增 | ✅ 新增 |
| 统一 zoom | ✅ 调整 | ✅ 调整 | ✅ 调整 |
| minimap | ✅ 新增 | ✅ 新增 | ❌ |

### 7.4 废弃组件

| 组件 | 文件 | 替代方案 |
|------|------|---------|
| `GraphDialoguePage`（旧） | `components/graph/pages/GraphDialoguePage.tsx` | `KnowledgeTreePage.tsx` |
| `useGraphDialogue` 部分状态 | `hooks/graph/useGraphDialogue.ts` | 新 Zustand store |

## 8. 数据模型变更

### 8.1 后端

无数据模型变更。现有 `KGNode`、`KGEdge`、`KnowledgeGraph` 模型满足所有新需求。

### 8.2 前端

新增以下类型（或合并到已有类型）：

```typescript
// 布局偏好（localStorage）
interface LayoutPreference {
  mode: "two-column" | "three-column";
  dialogWidth: number;
  detailWidth: number;
  dialogStyle: "sidebar" | "float";
  dialogSide: "left" | "right";
  graphMode: "mindmap" | "force" | "dag";
  canvasPosition?: { x: number; y: number; zoom: number };
}

// 对话消息（全局对话使用）
interface GlobalChatMessage {
  role: "user" | "assistant";
  text: string;
  id: string;
  operations?: TreeOperation[];  // LLM 执行的操作记录
}

// 树操作（LLM OPERATION 标记解析结果）
interface TreeOperation {
  action: "create_node" | "update_node" | "delete_node" | "create_edge" | "delete_edge";
  status: "pending" | "success" | "error";
  detail: string;
}
```

## 9. 实现路径

### 9.1 Phase 1：基础重构

**目标**：知识树独立页面 + 新布局框架

| 任务 | 涉及文件 | 预估工时 |
|------|---------|---------|
| 创建 `/knowledge-tree` 独立路由 | `frontend/src/app/knowledge-tree/page.tsx` | 1h |
| 创建 `KnowledgeTreePage.tsx` 骨架 | `KnowledgeTreePage.tsx` | 4h |
| 创建 `LayoutToggle.tsx` | `LayoutToggle.tsx` | 1h |
| 实现两栏/三栏切换逻辑 | `KnowledgeTreePage.tsx` | 2h |
| 实现布局偏好持久化 | `useLayoutPreference.ts` | 1h |
| 移除 `/resources` 中 knowledge-tree tab | `resources/page.tsx` | 0.5h |
| 旧路由 301 重定向 | `next.config.mjs` | 0.5h |
| 创建 `LayerPanel.tsx` 骨架 | `LayerPanel.tsx` | 2h |

### 9.2 Phase 2：画布交互升级

**目标**：拖拽、双击、右键、悬停、聚焦

| 任务 | 涉及文件 | 预估工时 |
|------|---------|---------|
| ForceGraph 添加拖拽 pin | `ForceGraph.tsx` | 4h |
| FocusGraph 添加叶子拖拽 | `FocusGraph.tsx` | 3h |
| KnowledgeCardNode 扩大热区 | `KnowledgeCardNode.tsx` | 1h |
| 双击内联编辑 | `KnowledgeCardNode.tsx` | 4h |
| 右键菜单组件 | `ContextMenu.tsx` | 3h |
| 悬停 Tooltip | `NodeTooltip.tsx`, `KnowledgeCardNode.tsx` | 2h |
| 点击居中 + 详情浮层 | `NodeDetailPopover.tsx` | 4h |
| 键盘导航 | `useKeyboardNavigation.ts` | 3h |
| 统一 D3 zoom 行为 | 三个 Graph 组件 | 3h |
| Minimap 缩略图 | `Minimap.tsx`, ForceGraph/FocusGraph | 4h |

### 9.3 Phase 3：全局对话能力

**目标**：全局对话端点 + 两种形态切换

| 任务 | 涉及文件 | 预估工时 |
|------|---------|---------|
| 后端全局对话端点 | `global_chat.py` | 6h |
| 全局对话 system prompt 设计 | `global_chat.py`（prompt 模板） | 2h |
| OPERATION 标记解析与执行 | `global_chat.py` | 4h |
| DialogContainer 抽象层 | `DialogContainer.tsx` | 3h |
| SidebarDialog 组件 | `SidebarDialog.tsx` | 2h |
| FloatDialog 组件 | `FloatDialog.tsx` | 3h |
| 全局/节点上下文切换 | `KnowledgeTreePage.tsx`, `DialogContainer.tsx` | 3h |
| TreeChatPanel 适配新接口 | `TreeChatPanel.tsx` | 2h |

### 9.4 Phase 4：体验打磨

**目标**：搜索、鱼眼聚焦、层级折叠、测试

| 任务 | 涉及文件 | 预估工时 |
|------|---------|---------|
| 搜索高亮 + 自动聚焦 | `LayerPanel.tsx`, 三个 Graph | 3h |
| 鱼眼聚焦模式 | `useFishEye.ts`, 三个 Graph | 5h |
| 层级折叠 | `KnowledgeTreePage.tsx`, 三个 Graph | 4h |
| 缩放至适配 | 三个 Graph | 2h |
| NodeDetailPanel 适配三栏 | `NodeDetailPanel.tsx` | 2h |
| 跨浏览器/设备兼容测试 | — | 4h |
| 性能优化（大数据集渲染） | 三个 Graph | 4h |

**总计预估工时**：约 **80-100 小时**（单人全栈）
