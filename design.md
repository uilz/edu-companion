# Edu-Companion Design Skill

> **智能伴学系统** 前端设计语言 — 让思考成为焦点，让界面成为陪伴。

---

## Overview

智能伴学系统是面向深度学习的 AI 对话平台。设计上借鉴 Apple 式“让产品说话”的克制哲学，但场景从营销展示转向**长时间、高专注的学习阅读**。界面必须像一本摊开的精装书——安静、温暖、有呼吸感，让学生在面对复杂知识时感到从容而非压迫。

核心设计决策：
- **纸墨质感替代纯白纯黑** — 长时阅读需要柔和对比度，而非广告冲击力。
- **知识图谱可视化** — 学习路径、认知节点、边关系需要轻量但不失严谨的图可视化。
- **对话作为核心载体** — 对话气泡、消息流、多模态内容块是主要交互形式。
- **侧边栏知识树** — 层级懒加载、渐进可见、预览模式。
- **秘书面板与诊断卡片** — 数据密集但不焦虑，用呼吸感排版消解数字压力。
- **系统反馈温和** — 轻声提示替代弹窗轰炸，动画平滑但不喧宾夺主。

---

## Colors

> **设计目标**：长时阅读友好的暖色调纸墨系统，对比度达到 WCAG AA 级以上。

### Surface & Canvas

| Token | Value | Use |
|-------|-------|-----|
| `page` | `#fbfaf7` | 主对话区背景 — 暖白书页，比纯白柔和 |
| `page-secondary` | `#f5f3ef` | 侧边栏、面板背景 — 微暖的羊皮纸色 |
| `surface-card` | `#ffffff` | 卡片、消息气泡（用户消息）— 干净浮起 |
| `surface-card-alt` | `#faf9f5` | AI 消息气泡 — 微暖，区分于人 |
| `surface-hover` | `#f0ede8` | 悬停态 — 暖灰底 |
| `surface-elevated` | `#ffffff` | 弹出层、模态框、下拉菜单 |

### Ink & Text

| Token | Value | Use |
|-------|-------|-----|
| `ink-primary` | `#1c1917` | 正文、标题 — 暖黑，非纯黑 |
| `ink-secondary` | `#5c5650` | 辅助说明、时间戳、次要标签 |
| `ink-muted` | `#948f89` | 占位符、禁用文字、水印 |
| `ink-on-dark` | `#fbfaf7` | 深色底上文字 |
| `ink-link` | `#2563eb` | 内联链接 |

### Accent & Status

| Token | Value | Use |
|-------|-------|-----|
| `accent` | `#2563eb` | 主交互色 — 按钮、选中态、链接 |
| `accent-soft` | `#eff3ff` | 选中背景、标签底色 |
| `success` | `#16a34a` | 掌握度达标、练习正确 |
| `warning` | `#d97706` | 薄弱提醒、待复习 |
| `danger` | `#dc2626` | 错误、删除确认 |
| `info` | `#0891b2` | 中性提示、进度信息 |

### Knowledge Graph Specific

| Token | Value | Use |
|-------|-------|-----|
| `graph-node` | `#2563eb` | 认知节点主色 |
| `graph-edge-active` | `#1e40af` | 高置信度边 |
| `graph-edge-pending` | `#d97706` | 待确认边 |
| `graph-edge-suggested` | `#cbd5e1` | 建议边 |
| `graph-node-mastered` | `#16a34a` | 已掌握节点 |
| `graph-node-weak` | `#dc2626` | 薄弱节点 |

### Dividers

| Token | Value | Use |
|-------|-------|-----|
| `divider` | `#e7e3de` | 常规分割线 |
| `divider-soft` | `#f0ede8` | 柔和分割（卡片内） |

---

## Typography

### Font Stack

```
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
```

- **Inter** 作为主字体，x-height 高，长文可读性好，支持越南文等扩展字符。
- **JetBrains Mono** 用于代码块、数学公式、数据指标。

### Scale

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|-------|------|--------|-------------|----------------|-----|
| `text-hero` | 32px | 650 | 1.2 | -0.02em | 学习报告大标题 |
| `text-title` | 24px | 600 | 1.3 | -0.015em | 面板标题、侧边栏分区 |
| `text-heading` | 20px | 600 | 1.35 | -0.01em | 对话标题、卡片标题 |
| `text-subhead` | 16px | 600 | 1.4 | 0 | 消息内小标题、秘书提案标题 |
| `text-body` | 16px | 400 | 1.65 | 0 | 对话正文、讲解内容 |
| `text-body-strong` | 16px | 600 | 1.65 | 0 | 重点强调 |
| `text-caption` | 13px | 400 | 1.5 | 0 | 辅助说明、时间戳、边标签 |
| `text-caption-strong` | 13px | 600 | 1.5 | 0 | 徽章、标签、掌握度数字 |
| `text-fine` | 11px | 400 | 1.4 | 0 | 脚注、法律文字 |
| `text-code` | 14px | 400 | 1.6 | 0 | 代码块、公式 |

### Principles

- **正文 16px** — 学习场景需要比营销更大的正文字号，减少眼动疲劳。
- **行高 1.65** — 中文混合内容需要比纯英文更宽松的行高。
- **字重 400/600** — 用 600 而非 700 做强调，减少视觉噪音。
- **无负字间距** — 学习阅读不需要“Apple tight”，需要清晰。
- **等宽字体用于数据** — 掌握度百分比、数字指标用 mono 保持对齐感。

---

## Spacing & Layout

### Spacing Scale

| Token | Value | Use |
|-------|-------|-----|
| `space-1` | 4px | 图标与文字间距、紧密元素 |
| `space-2` | 8px | 气泡内 padding、列表项间距 |
| `space-3` | 12px | 卡片内 padding |
| `space-4` | 16px | 组件间标准间距 |
| `space-5` | 24px | 段落间距、面板 section 间距 |
| `space-6` | 32px | 大标题下间距 |
| `space-8` | 48px | 页面级 section 间距 |

### Layout Architecture

```
┌──────────┬──────────────────────────────┐
│ 侧边栏    │  主对话区                      │
│ 280px    │  flex-1, max-w 860px          │
│          │                               │
│ 知识树    │  ┌─ 消息流 ────────────────┐  │
│ 懒加载    │  │  对话气泡、多模态内容    │  │
│          │  │  秘书轻声提示条           │  │
│          │  └──────────────────────────┘  │
│          │  ┌─ 底部 ──────────────────┐  │
│          │  │  消息输入框              │  │
│          │  └──────────────────────────┘  │
├──────────┴──────────────────────────────┤
│ 状态栏（可选：秘书摘要、学习进度）        │
└─────────────────────────────────────────┘
```

- 侧边栏可折叠，折叠后主对话区居中，最大宽度 720px。
- 消息气泡宽度自适应内容，最大 80% 容器宽度。
- 代码块、数学公式块可以超出气泡宽度至 100% 容器。

---

## Components

### Conversation
- **Message Bubble (User)**: `surface-card` 背景，1px `divider` 边框，`rounded.lg` (12px) 右下角为直角。右对齐。
- **Message Bubble (AI)**: `surface-card-alt` 背景，无边框，`rounded.lg` (12px) 左下角为直角。左对齐。
- **Content Blocks**: 图片、代码块、数学公式、知识卡片、练习组件嵌入在气泡内，可超出气泡至满宽。
- **Secretary Whisper**: 非阻断的顶部 banner，`accent-soft` 背景，`text-caption` 字体，3秒自动消失。
- **Typing Indicator**: 三个小圆点，`ink-muted` 颜色，依次闪烁动画。

### Knowledge Sidebar
- **Tree Node**: 逐层懒加载，点击展开请求子节点。
- **Preview Node**: 临时展开的 `suggested` 节点，灰色虚线边框 + 斜体 `text-muted`。
- **"+" Placeholder**: 无子节点时显示，点击创建新专题。
- **Multi-Path Indicator**: 对话属于多个 topic 时，在侧边栏各 topic 下均显示，非主归属带 `🔗` 标记。

### Classification Path Cards
- **Mode 1 (Multi-Topic)**: 消息下方展示 1~3 个可多选的路径卡片，`surface-card` 背景，`rounded.md`，带 `accent` 左边框。底部"在新会话中开启多主题讨论"按钮。
- **Mode 2 (Topic Switch)**: 展示新路径 + 确认/修改按钮。
- **Mode 3 (Continue)**: 无 UI 变化。

### Knowledge Graph Visualization
- **Node**: 圆形，大小按 mastery 映射（36px~48px）。颜色：`graph-node` 默认，`graph-node-mastered` 已掌握，`graph-node-weak` 薄弱。
- **Edge**: 线条，`graph-edge-active` 实线，`graph-edge-pending` 橙色虚线，`graph-edge-suggested` 灰色虚线。
- **Hover**: Tooltip 显示节点名、掌握度、建议操作。

### Secretary Panel
- **Diagnosis Summary**: 顶部概览卡片组（薄弱点数量、整体掌握度、认知负荷、待处理建议）。
- **Proposal List**: 卡片堆叠，左侧颜色条标识优先级。
- **Activity Timeline**: 紧凑时间线，采纳/忽略/提醒记录。
- **Settings**: 模块开关、勿扰时段、每日上限、自定义规则，折叠展示。

### Cards & Panels
- **Diagnosis Card**: `surface-card` 背景，`rounded.lg`，`divider` 边框，`space-4` padding。
- **Proposal Card**: 左边缘 `accent` 4px 条，`surface-card` 背景，`rounded.md`。
- **Stat Card**: 居中数字 + 标签，`surface-card` 背景，`rounded.lg`。

### Practice Components
- **Quiz**: 题目 + 选项列表，选中态 `accent-soft` 背景，正确/错误动画反馈。
- **Progress Ring**: 环形进度，`accent` 主色，`divider-soft` 底色。

### Input
- **Message Input**: `surface-card` 背景，`rounded.pill`，`divider` 边框，`space-3` padding，支持多行自动增高，最大 6 行。
- **Search**: `surface-card` 背景，`rounded.pill`，`divider` 边框，搜索图标前置。

### Buttons
- **Primary**: `accent` 背景，白字，`rounded.md`，`space-2` × `space-4` padding，hover 加深 8%。
- **Secondary**: 透明背景，`accent` 文字，`divider` 边框，`rounded.md`。
- **Ghost**: 透明背景，`ink-secondary` 文字，hover 显示 `surface-hover` 背景。
- **Icon**: 44×44px 最小触摸区，`rounded.full`，hover `surface-hover`。

### Empty States
- 使用柔和插画 + `text-muted` 引导文字，不展示空白区域。

---

## Interaction

### Animation
- 消息进入：`opacity 0 → 1` + `translateY(8px → 0)`，`duration 150ms ease-out`。
- 侧边栏展开/折叠：`max-height` 动画，`duration 200ms ease-in-out`。
- 轻声提示：`opacity` + `height` 动画，3秒后自动收起。
- 按钮 press：`scale(0.97)`，`duration 100ms`。
- 知识图边确认：虚线 → 实线过渡，`duration 300ms`。

### Feedback
- **轻声提示 (Whisper)**: 顶部 banner，非阻断，自动消失。
- **确认对话框**: 仅在删除、合并等不可逆操作时使用，`surface-elevated` 模态框。
- **Loading**: Skeleton 占位，避免空白闪烁。

---

## Shapes

### Border Radius

| Token | Value | Use |
|-------|-------|-----|
| `rounded-sm` | 6px | 徽章、标签 |
| `rounded-md` | 10px | 卡片、按钮、选项芯片 |
| `rounded-lg` | 14px | 消息气泡、大卡片 |
| `rounded-xl` | 20px | 模态框 |
| `rounded-full` | 9999px | 环形进度、圆形节点、pill 输入框 |

### Shadow

仅用于浮层（模态框、下拉菜单、tooltip），**不用于卡片和气泡**：

| Level | Value | Use |
|-------|-------|-----|
| `shadow-sm` | `0 1px 3px rgba(0,0,0,0.06)` | Tooltip, popover |
| `shadow-md` | `0 4px 16px rgba(0,0,0,0.08)` | 模态框、下拉菜单 |

卡片和气泡用**边框** (`divider`) 或**背景色差**区分层级，不加阴影。

---

## Do's and Don'ts

### Do
- 用 16px 正文和 1.65 行高保证长文阅读舒适。
- 对话气泡用背景色差区分人机，不加阴影。
- 秘书提示用温和 banner，不弹窗。
- 知识图边按置信度用不同线型（实线/虚线）。
- 掌握度数据用环形进度条，不用纯数字。
- 侧边栏预览节点用临时虚线样式，刷新消失。
- 按钮 `scale(0.97)` 作为 press 反馈。
- 消息进入用轻微位移 + 透明度动画。
- 空状态用引导文案 + 插画，不空白。

### Don't
- 不要用纯黑 `#000` 或纯白 `#fff` 作为主背景。
- 不要给卡片或气泡加投影。
- 不要用弹窗打断学习心流 — 用轻声提示。
- 不要在正文使用负 letter-spacing — 学习阅读需要宽松。
- 不要将知识图所有边都展示 — 默认折叠弱边。
- 不要让 AI 消息和用户消息外观相同。
- 不要在侧边栏一次性递归加载全部节点 — 逐层懒加载。
- 不要在加载中展示空白 — 用 Skeleton。

---

## Responsive

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Mobile | < 640px | 侧边栏隐藏，汉堡菜单呼出；消息气泡全宽；知识图不可见 |
| Tablet | 640–1024px | 侧边栏可折叠；消息最大宽 90% |
| Desktop | ≥ 1024px | 完整三栏或两栏布局；知识图可并排展示 |

---

## Iteration Guide

1. 先搭消息流和侧边栏骨架 — 这是核心交互载体。
2. 再逐步接入分类器、秘书面板、知识图 — 每个模块独立可测。
3. 使用 `token.refs` 引用颜色和字体，不内联硬编码。
4. 知识图组件初期用简化版（力导向布局 + Canvas），后续可升级为 WebGL。
5. 所有数据密集区域（诊断卡片、统计）优先保证可读性和留白，再考虑紧凑。
6. 动画保持 150–300ms，不过度使用。