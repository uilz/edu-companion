# 设计语言规范

> **苹果果** 多风格设计语言 — 同一套交互骨架，五种视觉表达。
>
> 完整内容详见 [design/design-language.md](design/design-language.md)（迁移中）。
> 设计子分支方案详见 [archive/2025-early-designs/](archive/2025-early-designs/)。

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

## 通用 Design Token

每套风格通过 Token 映射定义独立的色彩、排版、圆角、阴影、动效，每套风格支持浅色/深色双主题。

> 详细 Token 定义见 [design/design-language.md](design/design-language.md)。
