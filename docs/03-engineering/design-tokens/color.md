# AppleGo Design Tokens — Color

> 从 Demo3.0 (preview.html) 提取。所有组件必须引用 Token，不得硬编码颜色值。

---

## 语义色板

### Page（页面背景）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-page` | `#f5f5f7` | 页面主背景 |
| `--color-page-secondary` | `#eeeef0` | 次级页面背景，如代码块 |

### Surface（表面色）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-surface` | `#ffffff` | 卡片、表单等表面背景 |
| `--color-surface-alt` | `#fafafa` | 表面悬停/备选色 |
| `--color-surface-hover` | `#e8e8ec` | 表面悬停状态 |

### Ink（文字色）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-ink-primary` | `#1c1c1e` | 主要文字 |
| `--color-ink-secondary` | `#6c6c78` | 次要说明文字 |
| `--color-ink-muted` | `#a0a0ab` | 最弱文字/占位符 |
| `--color-ink-link` | `#0a84ff` | 链接文字 |

### Accent（品牌色）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-accent` | `#0a84ff` | 品牌主色、按钮、链接、活跃状态 |
| `--color-accent-hover` | `#0070e0` | Accent 悬停态 |
| `--color-accent-soft` | `rgba(10,132,255,.08)` | 品牌色背景（极淡） |
| `--color-accent-glow` | `rgba(10,132,255,.12)` | 品牌色发光阴影 |

### Status（状态色）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-success` | `#34c759` | 成功/正确 |
| `--color-success-soft` | `rgba(52,199,89,.12)` | 成功背景 |
| `--color-warning` | `#ff9f0a` | 警告/部分正确 |
| `--color-warning-soft` | `rgba(255,159,10,.12)` | 警告背景 |
| `--color-danger` | `#ff3b30` | 危险/错误 |
| `--color-danger-soft` | `rgba(255,59,48,.10)` | 危险背景 |

### Accent Variants（工具/功能区色彩）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-purple` | `#af52de` | 闪卡/记忆相关 |
| `--color-purple-soft` | `rgba(175,82,222,.10)` | 紫色功能区背景 |
| `--color-teal` | `#5ac8fa` | 阅读/文件相关 |
| `--color-teal-soft` | `rgba(90,200,250,.12)` | 青色功能区背景 |
| `--color-pink` | `#ff2d92` | 语音/口语相关 |
| `--color-pink-soft` | `rgba(255,45,146,.10)` | 粉色功能区背景 |

### Divider（分割线）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-divider` | `#e5e5ea` | 分割线、边框 |
| `--color-divider-hover` | `#d1d1d6` | 分割线悬停 |
| `--color-divider-soft` | `#f0f0f2` | 最弱分割线、卡片阴影层 |

### Message（消息气泡）

| Token | 值 | 用途 |
|-------|-----|------|
| `--color-ai-msg` | `#f7f3ea` | AI 消息气泡背景 |
| `--color-ai-msg-strong` | `#efe9d8` | AI 消息强调态 |
| `--color-user-msg` | `#ebe7dd` | 用户消息气泡背景 |

---

## 使用规则

1. 所有颜色值必须引用 CSS 变量，不得硬编码 hex/rgba
2. 语义色（success/warning/danger）仅用于状态指示，不用于品牌表达
3. Accent Variants 为功能区标识色，不用于按钮/链接等交互元素
4. 消息气泡色仅用于 Session 对话区域
