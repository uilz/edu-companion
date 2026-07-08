# 设计语言规范

> 苹果果多风格设计语言 — 同一套交互骨架，五种视觉表达。

---

## 架构原则

```
┌─────────────────────────────────────────┐
│           Interaction Skeleton          │
│  (Layout, Behavior, Component Structure)│
├─────────────────────────────────────────┤
│           Design Token Layer            │
│  (Color / Typography / Radius / Shadow) │
├─────────────────────────────────────────┤
│         Style Variant Presets           │
│  (professional / playful / knowledge /  │
│   soft-data / gamified)                 │
└─────────────────────────────────────────┘
```

## 五套风格

| 风格 | 代号 | 灵感来源 | 适用场景 |
|------|------|----------|----------|
| 现代专业风 | `professional` | Linear, Notion | 高效学习、知识管理、专业场景 |
| 活力趣味风 | `playful` | Duolingo, Google Material 3 | 基础学习、轻松学习、游戏化引导 |
| 紧凑知识风 | `knowledge` | Obsidian, Logseq | 深度阅读、知识图谱、长时间沉浸 |
| 柔和数据风 | `soft-data` | Apple Health, Apple Books | 学习数据分析、进度追踪 |
| 游戏化激励风 | `gamified` | 游戏化学习平台 | 成就驱动、进度激励 |

每套风格支持浅色/深色双主题，通过 CSS 变量动态切换。

## 实现位置

- **Tailwind 令牌配置**: `frontend/tailwind.config.js` — 语义化颜色、字号、间距、圆角、阴影、动画
- **CSS 变量定义**: `frontend/src/app/globals.css` — 五套风格主题变量 + 组件层样式
- **主题切换**: `frontend/src/contexts/ThemeContext.tsx` — 风格/暗亮/衬线字体偏好管理
- **UI 原语组件**: `frontend/src/components/ui/` — Button, Badge, Card, Toast, Skeleton, EmptyState 等

## 语义令牌

设计令牌使用语义化命名，避免直接引用颜色值：

| 令牌类别 | 示例 | 说明 |
|----------|------|------|
| 页面背景 | `bg-page` | 页面底色 |
| 容器表面 | `bg-surface`, `bg-surface-elevated` | 卡片/面板底色 |
| 文字颜色 | `text-ink-primary`, `text-ink-muted` | 主/次文字 |
| 强调色 | `bg-accent`, `text-accent` | 品牌色 |
| 状态色 | `bg-success`, `text-danger`, `text-warning` | 成功/错误/警告 |
| 分割线 | `border-divider` | 边框/分割线 |
| 字号 | `text-hero`, `text-heading`, `text-body`, `text-caption` | 9 级语义字号 |
| 间距 | `p-space-2`, `m-space-4` | 8 级语义间距 |
| 圆角 | `rounded-card`, `rounded-bubble` | 语义化圆角 |