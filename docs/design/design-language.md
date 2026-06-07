# Edu-Companion Design Language

> **智能伴学系统** 多风格设计语言 — 同一套交互骨架，五种视觉表达。

---

## Overview

智能伴学系统是面向深度学习的 AI 对话平台。本设计语言采用 **通用 Design Token + 风格变体** 的架构：

- **一套交互骨架** — 消息流、侧边栏、知识图、秘书面板的布局与行为在所有风格中保持一致。
- **五套视觉风格** — 每套风格通过 Token 映射定义独立的色彩、排版、圆角、阴影、动效。
- **每套风格双主题** — 浅色 (Light) / 深色 (Dark) 预设，保留未来自定义主题扩展能力。

### 五套风格

| 风格 | 代号 | 灵感来源 | 适用场景 |
|------|------|----------|----------|
| 现代专业风 | `professional` | Linear, Notion | 高效学习、知识管理、专业场景 |
| 活力趣味风 | `playful` | Duolingo, Google Material 3 | K12、轻松学习、游戏化引导 |
| 紧凑知识风 | `knowledge` | Obsidian, Logseq | 深度阅读、知识图谱、长时间沉浸 |
| 柔和数据风 | `soft-data` | Apple Health, Apple Books | 学习数据分析、进度追踪、温和反馈 |
| 游戏化激励风 | `gamified` | 游戏化学习平台 | 成就驱动、进度激励、强反馈场景 |

### 架构原则

```
┌─────────────────────────────────────────┐
│           Interaction Skeleton          │
│  (Layout, Behavior, Component Structure)│
├─────────────────────────────────────────┤
│         Design Token Abstraction        │
│  (color.*, typography.*, spacing.*, ...)│
├──────┬──────┬──────┬──────┬─────────────┤
│Pro   │Play  │Know  │Soft  │Gamified     │
│Style │Style │Style │Style │Style        │
│+Light│+Light│+Light│+Light│+Light       │
│+Dark │+Dark │+Dark │+Dark │+Dark        │
└──────┴──────┴──────┴──────┴─────────────┘
```

---

## Design Token System

### Color Tokens

颜色系统分为 **语义层**（所有风格共用）和 **值层**（各风格映射不同值）。

#### Semantic Color Roles

| Token | 用途 |
|-------|------|
| `color.page` | 页面主背景 |
| `color.page-secondary` | 侧边栏、面板背景 |
| `color.surface` | 卡片、消息气泡（浮起层） |
| `color.surface-alt` | 交替表面（AI 消息气泡等） |
| `color.surface-hover` | 悬停态背景 |
| `color.surface-elevated` | 弹出层、模态框 |
| `color.ink-primary` | 正文、标题文字 |
| `color.ink-secondary` | 辅助说明、时间戳 |
| `color.ink-muted` | 占位符、禁用文字 |
| `color.ink-on-dark` | 深色背景上的文字 |
| `color.ink-link` | 链接文字 |
| `color.accent` | 主交互色（按钮、选中态） |
| `color.accent-soft` | 选中背景、标签底色 |
| `color.accent-hover` | 主交互色 hover 态 |
| `color.success` | 成功、掌握达标 |
| `color.warning` | 警告、薄弱提醒 |
| `color.danger` | 错误、删除 |
| `color.info` | 中性提示 |
| `color.divider` | 常规分割线 |
| `color.divider-soft` | 柔和分割线 |

#### Graph-Specific Colors

| Token | 用途 |
|-------|------|
| `color.graph-node` | 认知节点主色 |
| `color.graph-edge-active` | 高置信度边 |
| `color.graph-edge-pending` | 待确认边 |
| `color.graph-edge-suggested` | 建议边 |
| `color.graph-node-mastered` | 已掌握节点 |
| `color.graph-node-weak` | 薄弱节点 |

### Typography Tokens

排版系统在所有风格中**共享同一套语义 Token**，各风格可选择不同的字体栈和字号基准。

#### Semantic Typography Roles

| Token | 用途 |
|-------|------|
| `text-hero` | 学习报告大标题 |
| `text-title` | 面板标题、侧边栏分区 |
| `text-heading` | 对话标题、卡片标题 |
| `text-subhead` | 消息内小标题、秘书提案标题 |
| `text-body` | 对话正文、讲解内容 |
| `text-body-strong` | 重点强调 |
| `text-caption` | 辅助说明、时间戳、边标签 |
| `text-caption-strong` | 徽章、标签、掌握度数字 |
| `text-fine` | 脚注、法律文字 |
| `text-code` | 代码块、公式 |

#### Font Stack

| Token | 默认值 | 用途 |
|-------|--------|------|
| `font-sans` | `'Inter', system-ui, -apple-system, sans-serif` | 主字体 |
| `font-mono` | `'JetBrains Mono', 'Fira Code', monospace` | 代码、数据 |

各风格可覆盖 `font-sans` 以改变整体气质。

### Spacing Tokens

| Token | Value | 用途 |
|-------|-------|------|
| `space-1` | 4px | 图标与文字间距、紧密元素 |
| `space-2` | 8px | 气泡内 padding、列表项间距 |
| `space-3` | 12px | 卡片内 padding |
| `space-4` | 16px | 组件间标准间距 |
| `space-5` | 24px | 段落间距、面板 section 间距 |
| `space-6` | 32px | 大标题下间距 |
| `space-8` | 48px | 页面级 section 间距 |

### Radius Tokens

| Token | Value | 用途 |
|-------|-------|------|
| `radius-sm` | 6px | 徽章、标签 |
| `radius-md` | 10px | 卡片、按钮、选项芯片 |
| `radius-lg` | 14px | 消息气泡、大卡片 |
| `radius-xl` | 20px | 模态框 |
| `radius-full` | 9999px | 环形进度、圆形节点、pill 输入框 |

各风格可覆盖 radius 值以改变整体圆润度。

### Shadow Tokens

仅用于浮层（模态框、下拉菜单、tooltip），**不用于卡片和气泡**：

| Token | Value | 用途 |
|-------|-------|------|
| `shadow-sm` | `0 1px 3px rgba(0,0,0,0.06)` | Tooltip, popover |
| `shadow-md` | `0 4px 16px rgba(0,0,0,0.08)` | 模态框、下拉菜单 |

### Motion Tokens

| Token | Value | 用途 |
|-------|-------|------|
| `motion-fast` | 100ms | 按钮 press、微交互 |
| `motion-normal` | 150ms | 消息进入、状态切换 |
| `motion-slow` | 200ms | 侧边栏展开/折叠 |
| `motion-slower` | 300ms | 知识图边确认、复杂过渡 |
| `ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | 进入动画 |
| `ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | 展开/折叠 |
| `ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | 弹性反馈（可选） |

---

## Layout Architecture

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

- 侧边栏可折叠，折叠后主对话区居中，最大宽度 720px
- 消息气泡宽度自适应内容，最大 80% 容器宽度
- 代码块、数学公式块可以超出气泡至 100% 容器

### Responsive

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Mobile | < 640px | 侧边栏隐藏，汉堡菜单呼出；消息气泡全宽；知识图不可见 |
| Tablet | 640–1024px | 侧边栏可折叠；消息最大宽 90% |
| Desktop | ≥ 1024px | 完整三栏或两栏布局；知识图可并排展示 |

---

## Component Specifications

> 以下组件规范在所有风格中共享结构，视觉表现通过 Token 映射自动适配各风格。

### Conversation

#### Message Bubble (User)
- 背景：`color.surface`
- 圆角：`radius-lg`，右下角为直角
- 对齐：右对齐
- 最大宽度：80% 容器宽度
- 内边距：`space-3` 垂直 × `space-4` 水平

#### Message Bubble (AI)
- 背景：`color.surface-alt`
- 圆角：`radius-lg`，左下角为直角
- 对齐：左对齐
- 最大宽度：80% 容器宽度
- 内边距：`space-3` 垂直 × `space-4` 水平

#### Content Blocks
- 图片、代码块、数学公式、知识卡片、练习组件嵌入在气泡内
- 可超出气泡至满宽
- 代码块背景：`color.page-secondary`，圆角 `radius-md`

#### Secretary Whisper
- 非阻断的顶部 banner
- 背景：`color.accent-soft`
- 文字：`text-caption`
- 圆角：`radius-md`
- 3秒自动消失
- 进入动画：`opacity 0→1` + `translateY(-8px→0)`，`motion-normal ease-out`

#### Typing Indicator
- 三个小圆点，`color.ink-muted` 颜色
- 依次闪烁动画，间隔 400ms

### Knowledge Sidebar

#### Tree Node
- 逐层懒加载，点击展开请求子节点
- 节点高度：40px
- 内边距：`space-2` 水平
- 悬停背景：`color.surface-hover`
- 选中背景：`color.accent-soft`
- 圆角：`radius-sm`

#### Preview Node
- 临时展开的 `suggested` 节点
- 边框：灰色虚线 1px
- 文字：`color.ink-muted`，斜体
- 刷新后消失

#### "+" Placeholder
- 无子节点时显示
- 点击创建新专题
- 图标 + `text-caption` 文字

### Classification Path Cards
- **Mode 1 (Multi-Topic)**: 消息下方展示 1~3 个可多选的路径卡片
  - 背景：`color.surface`
  - 圆角：`radius-md`
  - 左边框：4px `color.accent`
  - 底部按钮："在新会话中开启多主题讨论"
- **Mode 2 (Topic Switch)**: 展示新路径 + 确认/修改按钮
- **Mode 3 (Continue)**: 无 UI 变化

### Knowledge Graph Visualization
- **Node**: 圆形
  - 大小：按 mastery 映射（36px~48px）
  - 颜色：`color.graph-node` 默认，`color.graph-node-mastered` 已掌握，`color.graph-node-weak` 薄弱
  - 悬停：Tooltip 显示节点名、掌握度、建议操作
- **Edge**: 线条
  - `color.graph-edge-active` 实线
  - `color.graph-edge-pending` 虚线
  - `color.graph-edge-suggested` 虚线（更淡）

### Secretary Panel

#### Diagnosis Summary
- 顶部概览卡片组（薄弱点数量、整体掌握度、认知负荷、待处理建议）
- 卡片背景：`color.surface`
- 圆角：`radius-lg`
- 边框：1px `color.divider`
- 内边距：`space-4`

#### Proposal List
- 卡片堆叠
- 左侧颜色条标识优先级
- 卡片背景：`color.surface`
- 圆角：`radius-md`

#### Activity Timeline
- 紧凑时间线
- 采纳/忽略/提醒记录
- 节点颜色：`color.success` / `color.warning` / `color.ink-muted`

#### Settings
- 模块开关、勿扰时段、每日上限、自定义规则
- 折叠展示
- 开关组件：`color.accent` 激活态

### Cards & Panels

#### Diagnosis Card
- 背景：`color.surface`
- 圆角：`radius-lg`
- 边框：1px `color.divider`
- 内边距：`space-4`

#### Proposal Card
- 左边缘：`color.accent` 4px 条
- 背景：`color.surface`
- 圆角：`radius-md`

#### Stat Card
- 居中数字 + 标签
- 背景：`color.surface`
- 圆角：`radius-lg`

### Practice Components

#### Quiz
- 题目 + 选项列表
- 选中态：`color.accent-soft` 背景
- 正确动画：绿色闪烁 + 对勾
- 错误动画：红色闪烁 + 叉号

#### Progress Ring
- 环形进度
- 主色：`color.accent`
- 底色：`color.divider-soft`
- 线宽：4px
- 动画：`stroke-dashoffset` 过渡，`motion-slower ease-in-out`

### Input

#### Message Input
- 背景：`color.surface`
- 圆角：`radius-full` (pill)
- 边框：1px `color.divider`
- 内边距：`space-3`
- 支持多行自动增高，最大 6 行
- 焦点态：边框变为 `color.accent`

#### Search
- 背景：`color.surface`
- 圆角：`radius-full`
- 边框：1px `color.divider`
- 搜索图标前置

### Buttons

#### Primary
- 背景：`color.accent`
- 文字：`color.ink-on-dark`
- 圆角：`radius-md`
- 内边距：`space-2` 垂直 × `space-4` 水平
- Hover：`color.accent-hover`
- Press：`scale(0.97)`，`motion-fast`

#### Secondary
- 背景：透明
- 文字：`color.accent`
- 边框：1px `color.divider`
- 圆角：`radius-md`
- Hover：`color.surface-hover`

#### Ghost
- 背景：透明
- 文字：`color.ink-secondary`
- Hover：`color.surface-hover`

#### Icon
- 最小触摸区：44×44px
- 圆角：`radius-full`
- Hover：`color.surface-hover`

### Empty States
- 柔和插画 + `color.ink-muted` 引导文字
- 不展示空白区域

---

## Interaction & Motion

### Animation Principles

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 消息进入 | `opacity 0→1` + `translateY(8px→0)` | `motion-normal` | `ease-out` |
| 侧边栏展开/折叠 | `max-height` 动画 | `motion-slow` | `ease-in-out` |
| 轻声提示 | `opacity` + `height` 动画 | `motion-normal` | `ease-out` |
| 按钮 press | `scale(0.97)` | `motion-fast` | `ease-out` |
| 知识图边确认 | 虚线 → 实线过渡 | `motion-slower` | `ease-in-out` |
| 进度环更新 | `stroke-dashoffset` 过渡 | `motion-slower` | `ease-in-out` |
| Quiz 正确/错误 | 颜色闪烁 + 图标动画 | `motion-slow` | `ease-spring` |

### Feedback Patterns

| 类型 | 行为 | 适用场景 |
|------|------|----------|
| Whisper | 顶部 banner，非阻断，自动消失 | 秘书提示、状态通知 |
| Confirm Dialog | 模态框，`color.surface-elevated` 背景 | 删除、合并等不可逆操作 |
| Skeleton | 占位加载，避免空白 | 数据加载中 |
| Toast | 底部/顶部短暂提示，手动关闭 | 操作成功/失败 |
| Badge Update | 数字变化动画 | 成就、积分、掌握度 |

---

## Accessibility

### Contrast Requirements

- 所有 `color.ink-primary` / `color.page` 组合必须达到 **WCAG AA** (4.5:1)
- 大文字 (18px+) 可达到 **WCAG AA Large** (3:1)
- 状态色 (success/warning/danger) 必须与背景达到 AA 级对比度

### Focus States

- 所有交互元素必须有可见焦点指示器
- 焦点环：2px `color.accent` 外扩，4px 偏移
- 键盘导航顺序：从左到右，从上到下

### Reduced Motion

- 用户开启 `prefers-reduced-motion` 时：
  - 所有动画时长 × 0（直接切换状态）
  - 保留必要的加载指示器
  - 禁用弹性缓动

### Screen Reader

- 所有图标按钮必须有 `aria-label`
- 知识图节点必须有文本替代
- 进度环必须有 `aria-valuenow` / `aria-valuemin` / `aria-valuemax`

---

## Theme Extension

### Custom Theme Structure

```
{
  "name": "Custom Theme Name",
  "baseStyle": "professional" | "playful" | "knowledge" | "soft-data" | "gamified",
  "mode": "light" | "dark",
  "overrides": {
    "color": {
      "accent": "#custom-value",
      // ... 其他颜色覆盖
    },
    "radius": {
      "radius-md": 12,
      // ... 其他圆角覆盖
    },
    "typography": {
      "font-sans": "'Custom Font', sans-serif",
      // ... 其他排版覆盖
    }
  }
}
```

### Extension Rules

1. 必须指定 `baseStyle`，继承该风格的所有 Token
2. `overrides` 中的值会覆盖基础 Token
3. 颜色覆盖必须同时提供 hover 态（或系统自动计算 ±8% 亮度）
4. 自定义主题必须通过对比度检查
5. 未来可扩展：渐变、纹理、背景图案

---

## Do's and Don'ts

### Do
- 使用 Token 引用，不内联硬编码颜色/排版值
- 保持交互骨架一致，视觉差异仅通过 Token 映射实现
- 对话气泡用背景色差区分人机，不加阴影
- 秘书提示用温和 banner，不弹窗
- 知识图边按置信度用不同线型
- 掌握度数据用环形进度条
- 侧边栏预览节点用临时虚线样式
- 按钮 `scale(0.97)` 作为 press 反馈
- 消息进入用轻微位移 + 透明度动画
- 空状态用引导文案 + 插画

### Don't
- 不要在组件中硬编码颜色值
- 不要给卡片或气泡加投影（浮层除外）
- 不要用弹窗打断学习心流
- 不要在侧边栏一次性递归加载全部节点
- 不要在加载中展示空白 — 用 Skeleton
- 不要混用不同风格的 Token 值
- 不要让自定义主题破坏对比度要求
- 不要在 Reduced Motion 模式下播放动画

---

## Style Variants

> 以下仅列出各风格与主设计的**差异部分**。未列出的组件、交互、动画均遵循主设计规范。

### Style 1: Professional (现代专业风)

> 灵感：Linear, Notion — 高对比、低装饰、专业工具感。

#### Color Mapping

| Token | Light | Dark |
|-------|-------|------|
| `color.page` | `#ffffff` | `#0d0d0d` |
| `color.page-secondary` | `#f7f7f5` | `#141414` |
| `color.surface` | `#ffffff` | `#1a1a1a` |
| `color.surface-alt` | `#fafafa` | `#1e1e1e` |
| `color.surface-hover` | `#f2f2f2` | `#252525` |
| `color.surface-elevated` | `#ffffff` | `#1a1a1a` |
| `color.ink-primary` | `#171717` | `#ededed` |
| `color.ink-secondary` | `#525252` | `#a3a3a3` |
| `color.ink-muted` | `#a3a3a3` | `#525252` |
| `color.ink-on-dark` | `#ededed` | `#ededed` |
| `color.ink-link` | `#2563eb` | `#60a5fa` |
| `color.accent` | `#2563eb` | `#3b82f6` |
| `color.accent-soft` | `#eff6ff` | `#1e3a5f` |
| `color.accent-hover` | `#1d4ed8` | `#60a5fa` |
| `color.success` | `#16a34a` | `#4ade80` |
| `color.warning` | `#d97706` | `#fbbf24` |
| `color.danger` | `#dc2626` | `#f87171` |
| `color.info` | `#0891b2` | `#22d3ee` |
| `color.divider` | `#e5e5e5` | `#262626` |
| `color.divider-soft` | `#f0f0f0` | `#1f1f1f` |
| `color.graph-node` | `#2563eb` | `#3b82f6` |
| `color.graph-edge-active` | `#1e40af` | `#60a5fa` |
| `color.graph-edge-pending` | `#d97706` | `#fbbf24` |
| `color.graph-edge-suggested` | `#d4d4d4` | `#404040` |
| `color.graph-node-mastered` | `#16a34a` | `#4ade80` |
| `color.graph-node-weak` | `#dc2626` | `#f87171` |

#### Typography Override

| Token | Value |
|-------|-------|
| `font-sans` | `'Inter', 'SF Pro Display', system-ui, sans-serif` |
| `text-body` | 15px / 400 / 1.6 / 0 |
| `text-body-strong` | 15px / 500 / 1.6 / 0 |

#### Radius Override

| Token | Value |
|-------|-------|
| `radius-md` | 8px |
| `radius-lg` | 12px |

#### Spacing Override

| Token | Value |
|-------|-------|
| `space-3` | 10px |
| `space-4` | 14px |
| `space-5` | 20px |

#### Layout Differences

| 区域 | 差异 |
|------|------|
| 侧边栏 | 宽度 260px（比默认窄 20px）；无顶部标题栏；折叠后完全隐藏 |
| 主对话区 | 消息流最大宽度 780px；消息间距 `space-4` (14px)；无顶部标题栏 |
| 知识图 | 默认折叠，通过侧边栏节点右键菜单呼出；无网格线；节点标签 hover 时显示 |

#### Component Differences

| 组件 | 差异 |
|------|------|
| Message Bubble | 无边框；无头像；时间戳 hover 时显示 |
| Button | Primary 无渐变；Icon 按钮 24x24px 图标区 |
| Input | 无边框，底部 1px `color.divider` 线条；焦点态线条 2px `color.accent`；最大高度 4 行 |
| Card | 无边框，用 `color.divider` 分割线分隔；无阴影 |
| Sidebar Tree Node | 高度 36px；无图标，文字缩进；`+` / `-` 符号展开 |

#### Interaction Differences

| 场景 | 差异 |
|------|------|
| 消息操作 | 无确认对话框，删除直接执行 + toast（可撤销 3 秒） |
| 侧边栏 | 拖拽节点重新排序（按住 200ms 后进入拖拽态） |
| 输入 | 无发送按钮，输入内容后自动显示发送图标 |

#### Animation Override

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 消息进入 | `opacity 0→1` | 80ms | `linear` |
| 侧边栏展开 | 直接切换 | 0ms | - |
| 菜单弹出 | `scale(0.95→1)` + `opacity 0→1` | 100ms | `ease-out` |
| 按钮 press | `scale(0.98)` | 50ms | `linear` |
| Toast 进入 | `translateY(100%→0)` | 150ms | `ease-out` |
| Toast 离开 | `opacity 1→0` | 100ms | `linear` |

**原则**：极简动画，大多数交互直接切换；无弹性缓动；时长 50-200ms。

---

### Style 2: Playful (活力趣味风)

> 灵感：Duolingo, Google Material 3 — 明亮色彩、大圆角、友好亲和。

#### Color Mapping

| Token | Light | Dark |
|-------|-------|------|
| `color.page` | `#fefce8` | `#1a1a2e` |
| `color.page-secondary` | `#fef9c3` | `#16213e` |
| `color.surface` | `#ffffff` | `#1e293b` |
| `color.surface-alt` | `#fefce8` | `#233148` |
| `color.surface-hover` | `#fef9c3` | `#2d3f56` |
| `color.surface-elevated` | `#ffffff` | `#1e293b` |
| `color.ink-primary` | `#1c1917` | `#f1f5f9` |
| `color.ink-secondary` | `#78716c` | `#94a3b8` |
| `color.ink-muted` | `#a8a29e` | `#64748b` |
| `color.ink-on-dark` | `#fefce8` | `#f1f5f9` |
| `color.ink-link` | `#7c3aed` | `#a78bfa` |
| `color.accent` | `#7c3aed` | `#8b5cf6` |
| `color.accent-soft` | `#ede9fe` | `#2e1065` |
| `color.accent-hover` | `#6d28d9` | `#a78bfa` |
| `color.success` | `#22c55e` | `#4ade80` |
| `color.warning` | `#f59e0b` | `#fbbf24` |
| `color.danger` | `#ef4444` | `#f87171` |
| `color.info` | `#06b6d4` | `#22d3ee` |
| `color.divider` | `#e7e5e4` | `#334155` |
| `color.divider-soft` | `#f5f5f4` | `#2d3748` |
| `color.graph-node` | `#7c3aed` | `#8b5cf6` |
| `color.graph-edge-active` | `#6d28d9` | `#a78bfa` |
| `color.graph-edge-pending` | `#f59e0b` | `#fbbf24` |
| `color.graph-edge-suggested` | `#d6d3d1` | `#475569` |
| `color.graph-node-mastered` | `#22c55e` | `#4ade80` |
| `color.graph-node-weak` | `#ef4444` | `#f87171` |

#### Typography Override

| Token | Value |
|-------|-------|
| `font-sans` | `'Nunito', 'Quicksand', system-ui, sans-serif` |
| `text-body` | 16px / 500 / 1.65 / 0 |
| `text-body-strong` | 16px / 700 / 1.65 / 0 |
| `text-title` | 24px / 700 / 1.3 / 0 |
| `text-heading` | 20px / 700 / 1.35 / 0 |

#### Radius Override

| Token | Value |
|-------|-------|
| `radius-sm` | 8px |
| `radius-md` | 14px |
| `radius-lg` | 18px |
| `radius-xl` | 24px |

#### Spacing Override

| Token | Value |
|-------|-------|
| `space-3` | 14px |
| `space-4` | 18px |
| `space-5` | 28px |

#### Layout Differences

| 区域 | 差异 |
|------|------|
| 侧边栏 | 宽度 300px；顶部欢迎语 + 用户头像（圆形 40px）；节点带 emoji 图标；底部学习进度条；折叠后保留 60px 窄栏 |
| 主对话区 | 消息流最大宽度 800px；消息间距 `space-5` (28px)；顶部话题标签 pill；底部快捷回复按钮组 |
| 知识图 | 默认右侧面板并排展示；暖黄渐变背景；节点带 emoji 图标，标签始终显示；底部图例卡片 |

#### Component Differences

| 组件 | 差异 |
|------|------|
| Message Bubble | 2px 边框（用户紫色，AI 暖黄）；四角全圆 18px；带头像 32px；时间戳在气泡下方居中 |
| Button | Primary 渐变背景 `linear-gradient(135deg, #7c3aed, #6d28d9)`；hover 上浮 2px + 阴影；Icon 按钮 48x48px 圆形 |
| Input | 全边框 2px `color.divider`，18px 圆角 pill；焦点态外发光 `0 0 0 3px #ede9fe`；右侧发送按钮圆形紫色 |
| Card | 14px 圆角；可选渐变背景；hover 上浮 2px + 紫色阴影；可选顶部彩色条 |
| Sidebar Tree Node | 高度 44px；带 emoji 图标 20px；动画箭头展开；选中态紫色左边框 3px |
| Progress Ring | 环宽 6px，渐变填充 `conic-gradient(#7c3aed, #a78bfa)`；数字滚动动画 |

#### Interaction Differences

| 场景 | 差异 |
|------|------|
| 消息操作 | 长按/右键弹出菜单（弹簧动画）；删除需确认模态框；支持表情反应 |
| 侧边栏 | 展开/折叠带高度动画 + 弹簧缓动；拖拽节点放大 1.05 倍；"+" 创建弹出模态框 |
| 知识图 | 点击节点弹出详情卡片（放大弹出）；拖拽带磁吸效果 |
| 输入 | 发送按钮点击后变对勾动画；支持 `:` 唤起表情面板 |

#### Animation Override

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 消息进入 | `opacity 0→1` + `translateY(12px→0)` + `scale(0.95→1)` | 200ms | spring |
| 侧边栏展开 | `max-height` + 子节点依次延迟进入 | 300ms | spring |
| 菜单弹出 | `scale(0.8→1)` + `opacity 0→1` + 弹簧回弹 | 250ms | spring |
| 按钮 press | `scale(0.95)` + 下沉 1px | 100ms | spring |
| 按钮 hover | `translateY(-2px)` + 阴影出现 | 150ms | spring |
| Card hover | `translateY(-2px)` + 阴影出现 | 150ms | spring |
| Toast 进入 | `translateY(100%→0)` + 弹簧 | 300ms | spring |
| 进度环更新 | `stroke-dashoffset` 过渡 + 数字滚动 | 500ms | spring |
| 表情反应 | `scale(0→1.2→1)` 弹入 | 300ms | spring |
| 发送成功 | 按钮变对勾 + 粒子扩散 | 400ms | spring |
| 拖拽开始 | `scale(1→1.05)` + 阴影 + 旋转 2° | 150ms | spring |

**原则**：大量弹簧缓动；时长 100-500ms；微交互丰富；数字滚动；成功操作有粒子反馈。

---

### Style 3: Knowledge (紧凑知识风)

> 灵感：Obsidian, Logseq — 深色优先、低饱和、信息密度高。

#### Color Mapping

| Token | Light | Dark |
|-------|-------|------|
| `color.page` | `#f5f5f0` | `#111111` |
| `color.page-secondary` | `#eeece6` | `#1a1a1a` |
| `color.surface` | `#ffffff` | `#1e1e1e` |
| `color.surface-alt` | `#f5f5f0` | `#252525` |
| `color.surface-hover` | `#e8e6e0` | `#2a2a2a` |
| `color.surface-elevated` | `#ffffff` | `#1e1e1e` |
| `color.ink-primary` | `#2c2c2c` | `#d4d4d4` |
| `color.ink-secondary` | `#6b6b6b` | `#888888` |
| `color.ink-muted` | `#999999` | `#555555` |
| `color.ink-on-dark` | `#d4d4d4` | `#d4d4d4` |
| `color.ink-link` | `#6d8fad` | `#89b4d6` |
| `color.accent` | `#6d8fad` | `#89b4d6` |
| `color.accent-soft` | `#e8edf2` | `#1e2d3d` |
| `color.accent-hover` | `#5a7a96` | `#a3c4e0` |
| `color.success` | `#5a8a5e` | `#7ab87e` |
| `color.warning` | `#b8860b` | `#d4a843` |
| `color.danger` | `#b84a4a` | `#d46a6a` |
| `color.info` | `#4a7a8a` | `#6aa0b0` |
| `color.divider` | `#d8d6d0` | `#2a2a2a` |
| `color.divider-soft` | `#e5e3de` | `#222222` |
| `color.graph-node` | `#6d8fad` | `#89b4d6` |
| `color.graph-edge-active` | `#5a7a96` | `#a3c4e0` |
| `color.graph-edge-pending` | `#b8860b` | `#d4a843` |
| `color.graph-edge-suggested` | `#c8c6c0` | `#333333` |
| `color.graph-node-mastered` | `#5a8a5e` | `#7ab87e` |
| `color.graph-node-weak` | `#b84a4a` | `#d46a6a` |

#### Typography Override

| Token | Value |
|-------|-------|
| `font-sans` | `'Source Serif 4', 'Merriweather', Georgia, serif` |
| `text-body` | 15px / 400 / 1.65 / 0 |
| `text-body-strong` | 15px / 600 / 1.65 / 0 |
| `text-caption` | 12px / 400 / 1.4 / 0 |
| `text-code` | 12px / 400 / 1.5 / 0 |

#### Radius Override

| Token | Value |
|-------|-------|
| `radius-sm` | 4px |
| `radius-md` | 8px |
| `radius-lg` | 10px |
| `radius-xl` | 16px |

#### Spacing Override

| Token | Value |
|-------|-------|
| `space-2` | 6px |
| `space-3` | 10px |
| `space-4` | 12px |
| `space-5` | 18px |
| `space-6` | 24px |

#### Layout Differences

| 区域 | 差异 |
|------|------|
| 侧边栏 | 宽度 240px；顶部搜索框（无边框，底部线条）；节点无图标纯文字；支持面包屑导航；折叠后完全隐藏，快捷键 `Cmd+B` 呼出 |
| 主对话区 | 消息流最大宽度 900px；消息间距 `space-3` (10px)；顶部面包屑导航；底部输入区无圆角底部线条；支持分栏模式 |
| 知识图 | 默认全屏覆盖，快捷键 `Cmd+K` 呼出；淡色网格线背景；节点紧凑 28px~40px；标签始终显示；支持大纲模式切换 |
| 分栏布局 | 左栏对话 60%，右栏笔记/知识图 40%；中间可拖拽分割线；右栏可切换 tab |

#### Component Differences

| 组件 | 差异 |
|------|------|
| Message Bubble | 无边框；10px 圆角；无头像；时间戳在右侧 `text-fine`；最大宽度 85%；代码块 4px 圆角 + 行号 |
| Button | Primary 8px 圆角无渐变；Icon 按钮 36x36px，4px 圆角 |
| Input | 无边框，底部 1px `color.divider` 线条；焦点态线条变 `color.accent`；透明背景；最大高度 8 行；无发送按钮 |
| Card | 4px 圆角；用 `color.divider` 分割线；无阴影无彩色条；紧凑 padding `space-3` |
| Sidebar Tree Node | 高度 28px；无图标，文字缩进 2 空格/级；`▶` / `▼` 文字符号；支持双击内联编辑 |
| Knowledge Graph Node | 圆形 28px~40px；无边框纯色填充；标签始终显示 `text-fine` |

#### Interaction Differences

| 场景 | 差异 |
|------|------|
| 消息操作 | 右键菜单紧贴鼠标位置，无动画；支持 Markdown 语法高亮；链接直接跳转 |
| 侧边栏 | 点击直接展开/折叠无动画；双击内联编辑；拖拽直接移动无动画；键盘导航 `↑↓` 切换 `←→` 展开；输入即搜 |
| 知识图 | 快捷键呼出；点击节点右侧滑入详情面板；`Cmd+F` 搜索节点 |
| 输入 | 支持 `[[` 唤起知识节点引用；支持 `#` 唤起标签输入；无字数限制 |
| 分栏 | 拖拽分割线调整宽度；tab 切换无动画；支持全屏右栏 |

#### Animation Override

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 消息进入 | `opacity 0→1` | 60ms | `linear` |
| 侧边栏展开 | 直接切换 | 0ms | - |
| 知识图呼出 | `opacity 0→1` + `scale(0.98→1)` | 120ms | `ease-out` |
| 详情面板滑入 | `translateX(100%→0)` | 150ms | `ease-out` |
| 按钮 press | 直接变色 | 0ms | - |
| Tab 切换 | 直接切换 | 0ms | - |
| 搜索过滤 | 节点淡入淡出 | 80ms | `linear` |

**原则**：极简动画，大多数操作直接切换；仅知识图和面板有过渡；无弹性缓动；时长 60-150ms。

---

### Style 4: Soft-Data (柔和数据风)

> 灵感：Apple Health, Apple Books — 柔和渐变、数据可视化友好、温和反馈。

#### Color Mapping

| Token | Light | Dark |
|-------|-------|------|
| `color.page` | `#faf8f5` | `#0f0f0f` |
| `color.page-secondary` | `#f3f0eb` | `#161616` |
| `color.surface` | `#ffffff` | `#1c1c1e` |
| `color.surface-alt` | `#faf8f5` | `#222224` |
| `color.surface-hover` | `#f0ede8` | `#2c2c2e` |
| `color.surface-elevated` | `#ffffff` | `#1c1c1e` |
| `color.ink-primary` | `#1d1d1f` | `#f5f5f7` |
| `color.ink-secondary` | `#6e6e73` | `#98989d` |
| `color.ink-muted` | `#aeaeb2` | `#636366` |
| `color.ink-on-dark` | `#f5f5f7` | `#f5f5f7` |
| `color.ink-link` | `#0071e3` | `#2997ff` |
| `color.accent` | `#0071e3` | `#2997ff` |
| `color.accent-soft` | `#e8f2ff` | `#1a2a3f` |
| `color.accent-hover` | `#005bb5` | `#40a0ff` |
| `color.success` | `#34c759` | `#30d158` |
| `color.warning` | `#ff9f0a` | `#ffb340` |
| `color.danger` | `#ff3b30` | `#ff453a` |
| `color.info` | `#5ac8fa` | `#64d2ff` |
| `color.divider` | `#d2d2d7` | `#38383a` |
| `color.divider-soft` | `#e5e5ea` | `#2c2c2e` |
| `color.graph-node` | `#0071e3` | `#2997ff` |
| `color.graph-edge-active` | `#005bb5` | `#40a0ff` |
| `color.graph-edge-pending` | `#ff9f0a` | `#ffb340` |
| `color.graph-edge-suggested` | `#d2d2d7` | `#3a3a3c` |
| `color.graph-node-mastered` | `#34c759` | `#30d158` |
| `color.graph-node-weak` | `#ff3b30` | `#ff453a` |

#### Typography Override

| Token | Value |
|-------|-------|
| `font-sans` | `'SF Pro Display', 'SF Pro Text', system-ui, -apple-system, sans-serif` |
| `text-body` | 16px / 400 / 1.6 / 0 |
| `text-body-strong` | 16px / 500 / 1.6 / 0 |
| `text-title` | 28px / 600 / 1.25 / -0.02em |
| `text-heading` | 22px / 600 / 1.3 / -0.015em |

#### Radius Override

| Token | Value |
|-------|-------|
| `radius-md` | 12px |
| `radius-lg` | 16px |
| `radius-xl` | 22px |

#### Spacing Override

| Token | Value |
|-------|-------|
| `space-3` | 14px |
| `space-4` | 18px |
| `space-5` | 28px |
| `space-6` | 36px |

#### Layout Differences

| 区域 | 差异 |
|------|------|
| 侧边栏 | 宽度 280px；顶部用户头像（圆形 44px）+ 欢迎语；节点带 SF Symbols 风格图标；底部学习概览卡片（渐变背景 16px 圆角）；折叠后保留 70px 图标栏 |
| 主对话区 | 消息流最大宽度 760px；消息间距 `space-5` (28px)；顶部大标题样式对话标题（负字间距）；底部 pill 输入框 + 柔和阴影；上方快捷操作栏 |
| 知识图 | 默认右侧面板并排（65:35）；柔和渐变背景 `linear-gradient(180deg, #faf8f5, #f3f0eb)`；节点径向渐变 + 柔和阴影；底部统计摘要卡片 |
| 数据面板 | 可切换全屏数据视图；顶部大标题 + 日期选择器；统计卡片网格 2-3 列；环形进度 + 折线图 + 柱状图 |

#### Component Differences

| 组件 | 差异 |
|------|------|
| Message Bubble | 无边框；16px 圆角；带头像 36px 柔和阴影；时间戳在气泡下方居中 `text-caption` |
| Button | Primary 12px 圆角；hover 上浮 1px；Icon 按钮 44x44px 圆形 |
| Input | pill 样式 `radius-full`；无边框，柔和阴影 `0 2px 8px rgba(0,0,0,0.04)`；焦点态阴影加深；右侧圆形发送按钮 |
| Card | 16px 圆角；柔和阴影 `0 2px 12px rgba(0,0,0,0.04)`；hover 阴影加深 + 上浮 1px |
| Stat Card | 渐变背景按状态：Primary `linear-gradient(135deg, #e8f2ff, #faf8f5)`；Success `linear-gradient(135deg, #e6f9ed, #faf8f5)`；Warning `linear-gradient(135deg, #fff3e0, #faf8f5)`；大数字居中负字间距 |
| Progress Ring | 环宽 8px；渐变填充 `conic-gradient(from 0deg, #0071e3, #5ac8fa, #0071e3)`；中心数字负字间距 |
| Sidebar Tree Node | 高度 40px；带 SF Symbols 图标 20px；动画箭头；hover 圆角 8px；选中态左边框 3px |

#### Interaction Differences

| 场景 | 差异 |
|------|------|
| 消息操作 | 长按/右键弹出菜单（弹簧动画）；菜单圆角 16px；支持表情反应；删除需确认 |
| 侧边栏 | 展开/折叠带高度动画 + 弹簧缓动；拖拽节点放大 1.02 倍 + 阴影加深 |
| 知识图 | 点击节点弹出详情卡片（放大弹出）；拖拽带磁吸效果；双击高亮路径；底部卡片点击筛选数据 |
| 数据面板 | 日期选择器滑动切换；统计卡片点击展开详情；图表手势缩放 |
| 输入 | 发送按钮点击后变对勾动画；输入时显示字数统计 |

#### Animation Override

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 消息进入 | `opacity 0→1` + `translateY(8px→0)` | 180ms | `ease-out` |
| 侧边栏展开 | `max-height` + 内容渐显 | 250ms | `ease-in-out` |
| 菜单弹出 | `scale(0.9→1)` + `opacity 0→1` | 200ms | spring |
| 按钮 press | `scale(0.97)` | 80ms | `ease-out` |
| 按钮 hover | `translateY(-1px)` + 阴影加深 | 150ms | `ease-out` |
| Card hover | `translateY(-1px)` + 阴影加深 | 150ms | `ease-out` |
| Stat Card 进入 | `scale(0.95→1)` + `opacity 0→1` | 250ms | spring |
| Progress Ring 更新 | `stroke-dashoffset` 平滑过渡 | 600ms | `ease-in-out` |
| 数据面板切换 | 滑动过渡 | 300ms | `ease-in-out` |
| Toast 进入 | `translateY(100%→0)` | 250ms | spring |

**原则**：平滑温和动画；主要 `ease-out` / `ease-in-out`；弹簧仅用于弹出类交互；数据更新动画较长 600ms；hover 有位移 + 阴影变化。

---

### Style 5: Gamified (游戏化激励风)

> 灵感：Duolingo, Kahoot! — 成就驱动、进度激励、强视觉反馈。

#### Color Mapping

| Token | Light | Dark |
|-------|-------|------|
| `color.page` | `#f8f7ff` | `#0d0d1a` |
| `color.page-secondary` | `#f0eeff` | `#12122a` |
| `color.surface` | `#ffffff` | `#1a1a35` |
| `color.surface-alt` | `#f8f7ff` | `#1e1e3a` |
| `color.surface-hover` | `#ede9ff` | `#252548` |
| `color.surface-elevated` | `#ffffff` | `#1a1a35` |
| `color.ink-primary` | `#1a1a2e` | `#e8e8f0` |
| `color.ink-secondary` | `#5c5c7a` | `#9898b0` |
| `color.ink-muted` | `#9898b0` | `#5c5c7a` |
| `color.ink-on-dark` | `#f8f7ff` | `#e8e8f0` |
| `color.ink-link` | `#6366f1` | `#818cf8` |
| `color.accent` | `#6366f1` | `#818cf8` |
| `color.accent-soft` | `#eef2ff` | `#1e1b4b` |
| `color.accent-hover` | `#4f46e5` | `#a5b4fc` |
| `color.success` | `#10b981` | `#34d399` |
| `color.warning` | `#f59e0b` | `#fbbf24` |
| `color.danger` | `#ef4444` | `#f87171` |
| `color.info` | `#3b82f6` | `#60a5fa` |
| `color.divider` | `#e2e0f0` | `#2a2a45` |
| `color.divider-soft` | `#ede9ff` | `#222240` |
| `color.graph-node` | `#6366f1` | `#818cf8` |
| `color.graph-edge-active` | `#4f46e5` | `#a5b4fc` |
| `color.graph-edge-pending` | `#f59e0b` | `#fbbf24` |
| `color.graph-edge-suggested` | `#d4d0e8` | `#3a3a55` |
| `color.graph-node-mastered` | `#10b981` | `#34d399` |
| `color.graph-node-weak` | `#ef4444` | `#f87171` |

#### Typography Override

| Token | Value |
|-------|-------|
| `font-sans` | `'Poppins', 'Inter', system-ui, sans-serif` |
| `text-body` | 16px / 500 / 1.6 / 0 |
| `text-body-strong` | 16px / 700 / 1.6 / 0 |
| `text-title` | 26px / 700 / 1.25 / 0 |
| `text-heading` | 20px / 700 / 1.3 / 0 |
| `text-caption-strong` | 13px / 700 / 1.4 / 0 |

#### Radius Override

| Token | Value |
|-------|-------|
| `radius-sm` | 8px |
| `radius-md` | 12px |
| `radius-lg` | 16px |
| `radius-xl` | 24px |

#### Spacing Override

| Token | Value |
|-------|-------|
| `space-3` | 14px |
| `space-4` | 18px |
| `space-5` | 28px |
| `space-6` | 36px |

#### Layout Differences

| 区域 | 差异 |
|------|------|
| 侧边栏 | 宽度 300px；顶部用户头像（圆形 56px）+ 等级徽章 + 经验值进度条；连续学习天数（火焰图标 + 脉冲动画）；节点带任务图标；底部每日目标进度环 + 快捷任务；折叠后保留顶部状态栏 |
| 主对话区 | 消息流最大宽度 800px；消息间距 `space-5` (28px)；顶部任务标题 + 任务进度条；底部输入区 16px 圆角 + 渐变边框；上方快捷操作栏 |
| 知识图 | 默认右侧面板并排（60:40）；淡色星点装饰背景；节点带等级徽章（星星）；标签始终显示 `text-caption-strong`；底部任务进度摘要 |
| 游戏化面板 | 可切换全屏游戏化视图；顶部用户信息卡；中部成就墙网格；底部排行榜 + 每日任务 |

#### Component Differences

| 组件 | 差异 |
|------|------|
| Message Bubble | 3px 边框（用户 `color.accent`，AI `color.info`）；20px 圆角；带头像 44px 带等级边框；正确回答底部 XP 飘出动画 |
| Button | Primary 渐变背景 `linear-gradient(135deg, #6366f1, #818cf8)`，16px 圆角；hover 渐变加深 + 上浮 2px + 阴影；Secondary 2px 边框；Icon 按钮 48x48px 圆形 + 弹簧动画 |
| Input | 16px 圆角；2px `color.divider` 边框；阴影 `0 4px 12px rgba(99, 102, 241, 0.08)`；右侧发送按钮渐变背景，hover 放大 1.05 倍 |
| Card | 16px 圆角；2px `color.divider` 边框；阴影 `0 4px 12px rgba(0,0,0,0.04)`；hover 边框变 `color.accent` + 阴影加深 + 上浮 2px |
| XP Bar | 水平进度条 12px 高，6px 圆角；渐变填充 `linear-gradient(90deg, #6366f1, #818cf8)`；获取 XP 时数字飘出 `translateY(-20px)` + `opacity 1→0`；升级时满格闪烁 |
| Achievement Badge | 圆形 64px；光晕 `box-shadow: 0 0 20px rgba(99, 102, 241, 0.3)`；未解锁灰色无光晕；已解锁彩色 + 光晕 + 脉冲；解锁时 `scale(0→1.2→1)` + 粒子效果 |
| Streak Counter | 火焰图标 24px + 数字 `text-heading` `color.warning`；>3 天脉冲动画；>7 天火焰粒子效果；中断时灰色 + 抖动 |
| Progress Ring | 环宽 10px；渐变填充 `conic-gradient(from 0deg, #6366f1, #818cf8, #6366f1)`；中心数字 `text-title` `color.accent`；完成时 `scale(1→1.1→1)` + 粒子效果 |
| Sidebar Tree Node | 高度 48px；带任务图标 24px；动画箭头；hover 圆角 12px；选中态左边框 4px；已完成节点对勾图标 + 绿色 |

#### Interaction Differences

| 场景 | 差异 |
|------|------|
| 消息操作 | 长按/右键弹出菜单（弹簧动画 + 缩放）；表情反应带弹入动画；正确回答自动播放 XP 飘出 + 音效（可选） |
| 侧边栏 | 展开/折叠带高度动画 + 弹簧缓动 + 子节点依次延迟进入；完成任务节点变绿 + 对勾弹入；拖拽放大 1.05 倍 |
| 知识图 | 点击节点弹出详情卡片（放大弹出 + 弹簧动画）；拖拽带磁吸 + 放大；完成节点星星徽章闪烁；双击高亮路径动画 |
| 游戏化面板 | 成就解锁全屏庆祝动画（粒子 + 音效）；等级提升 Level Up 弹窗（底部弹入 + 粒子）；排行榜滑入动画；任务完成进度环 + XP 飘出 |
| 输入 | 发送按钮变对勾 + 弹簧效果；`/` 唤起命令菜单（弹簧动画） |
| Quiz | 选项 hover 弹性上浮 + 阴影加深；正确变绿 + 对勾弹入 + XP 飘出；错误变红 + 抖动动画 + 显示答案；结果卡片弹簧动画 |

#### Animation Override

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 消息进入 | `opacity 0→1` + `translateY(12px→0)` + `scale(0.95→1)` | 200ms | spring |
| 侧边栏展开 | `max-height` + 子节点依次延迟进入 | 300ms | spring |
| 菜单弹出 | `scale(0.8→1)` + `opacity 0→1` + 弹簧回弹 | 250ms | spring |
| 按钮 press | `scale(0.95)` | 80ms | spring |
| 按钮 hover | `translateY(-2px)` + 阴影加深 + 渐变加深 | 150ms | spring |
| Card hover | `translateY(-2px)` + 边框变色 + 阴影加深 | 150ms | spring |
| XP 飘出 | `translateY(0→-20px)` + `opacity 1→0` | 800ms | `ease-out` |
| 成就解锁 | `scale(0→1.2→1)` + 粒子效果 + 光晕 | 600ms | spring |
| 等级提升 | 全屏弹窗从底部弹入 + 粒子 + 音效 | 800ms | spring |
| 进度环更新 | `stroke-dashoffset` 平滑过渡 | 500ms | `ease-in-out` |
| 正确反馈 | 对勾弹入 + 绿色背景 + XP 飘出 | 400ms | spring |
| 错误反馈 | 红色背景 + 抖动动画 + 显示答案 | 300ms | spring |
| 火焰脉冲 | `scale(1→1.1→1)` 循环 | 1500ms | `ease-in-out` |
| Toast 进入 | `translateY(100%→0)` + 弹簧回弹 | 300ms | spring |

**原则**：大量弹簧缓动 `cubic-bezier(0.34, 1.56, 0.64, 1)`；时长 80-800ms；微交互丰富；成就/升级/正确有专属庆祝动画；粒子效果用于重要时刻；音效可选。
