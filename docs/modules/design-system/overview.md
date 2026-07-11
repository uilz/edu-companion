# Design System 1.0

> 模块：design-system
> 状态：Phase 1 建设中
> 目标：统一全产品视觉与交互语言，为秘书仪表盘和各壳改造提供一致的组件基础。

---

## 1. 设计原则

1. **专业克制**：以 slate 中性色为底，单一强调色引导操作。
2. **信息密度适中**：教育工具需要展示大量状态，卡片、列表、标签体系优先。
3. **响应式优先**：同一套组件在 desktop/tablet/mobile 三端可复用。
4. **动效克制**：过渡 150ms，主要用于状态反馈，不喧宾夺主。

---

## 2. 设计令牌

设计令牌定义在 `frontend/src/app/globals.css` 中，并通过 `frontend/tailwind.config.js` 映射为 Tailwind 类名。

### 2.1 颜色

| Token | Tailwind | 用途 |
|-------|----------|------|
| `--color-page` | `bg-page` / `text-page` | 页面背景 |
| `--color-surface` | `bg-surface` | 卡片/面板背景 |
| `--color-surface-hover` | `bg-surface-hover` | 悬停背景 |
| `--color-surface-elevated` | `bg-surface-elevated` | 浮层面板 |
| `--color-ink-primary` | `text-ink-primary` | 主文本 |
| `--color-ink-secondary` | `text-ink-secondary` | 次级文本 |
| `--color-ink-muted` | `text-ink-muted` | 弱化文本 |
| `--color-accent` | `bg-accent` / `text-accent` | 主强调色 |
| `--color-accent-hover` | `text-accent-hover` | 强调悬停 |
| `--color-success` | `bg-success` / `text-success` | 成功/已掌握 |
| `--color-warning` | `bg-warning` / `text-warning` | 警告/紧急 |
| `--color-danger` | `bg-danger` / `text-danger` | 错误/删除 |
| `--color-info` | `bg-info` / `text-info` | 信息提示 |
| `--color-divider` | `border-divider` | 边框 |

### 2.2 间距

| Token | 值 |
|-------|-----|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 24px |
| `--space-6` | 32px |

### 2.3 圆角

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | 6px | 小按钮/标签 |
| `--radius-md` | 8px | 按钮/输入框 |
| `--radius-lg` | 12px | 卡片 |
| `--radius-xl` | 20px | 大面板 |

### 2.4 动效

| Token | 值 |
|-------|-----|
| `--motion-fast` | 100ms |
| `--motion-normal` | 150ms |
| `--motion-slow` | 200ms |

---

## 3. 组件清单

### 3.1 基础组件

| 组件 | 路径 | 说明 |
|------|------|------|
| Button | `components/ui/Button.tsx` | variant/size/loading |
| Card | `components/ui/Card.tsx` | 简单 + 复合组件 API |
| Dialog | `components/ui/Dialog.tsx` | 通用对话框 |
| ConfirmDialog | `components/ui/ConfirmDialog.tsx` | 基于 Dialog 的确认弹窗 |
| Toast | `components/ui/Toast.tsx` | 操作反馈提示 |
| Skeleton | `components/ui/Skeleton.tsx` | 骨架屏 + 多种变体 |
| Badge | `components/ui/Badge.tsx` | 标签徽章 |
| Progress | `components/ui/Progress.tsx` | 进度条 |
| StatCard | `components/ui/StatCard.tsx` | 数据卡片 |
| EmptyState | `components/ui/EmptyState.tsx` | 空状态 |
| ErrorBoundary | `components/ui/ErrorBoundary.tsx` | 错误边界 |

### 3.2 表单组件

| 组件 | 路径 | 说明 |
|------|------|------|
| FormField | `components/ui/FormField.tsx` | 表单字段包装 |
| Input | `components/ui/Input.tsx` | 文本输入 |
| Textarea | `components/ui/Textarea.tsx` | 多行文本 |
| Select | `components/ui/Select.tsx` | 下拉选择 |
| Tabs | `components/ui/Tabs.tsx` | 标签切换 |
| Switch | `components/ui/Switch.tsx` | 开关 |
| RadioGroup | `components/ui/RadioGroup.tsx` | 单选组 |
| CheckboxGroup | `components/ui/CheckboxGroup.tsx` | 多选组 |

### 3.3 浮层与展示组件

| 组件 | 路径 | 说明 |
|------|------|------|
| DropdownMenu | `components/ui/DropdownMenu.tsx` | 下拉菜单 |
| Tooltip | `components/ui/Tooltip.tsx` | 工具提示 |
| Avatar | `components/ui/Avatar.tsx` | 头像 |
| Timeline | `components/ui/Timeline.tsx` | 时间线 |
| ActivityItem | `components/ui/ActivityItem.tsx` | 学习活动项 |

---

## 4. 使用规范

### 4.1 按钮层级

```tsx
<Button variant="primary">主行动</Button>
<Button variant="secondary">次行动</Button>
<Button variant="outline">低优先级</Button>
<Button variant="ghost">图标/工具</Button>
<Button variant="danger">删除</Button>
<Button variant="link">文字链接</Button>
```

### 4.2 卡片层级

```tsx
<Card>
  <CardHeader>
    <CardTitle>标题</CardTitle>
    <CardDescription>说明文字</CardDescription>
  </CardHeader>
  <CardContent>内容</CardContent>
  <CardFooter>操作</CardFooter>
</Card>
```

### 4.3 表单字段

```tsx
<FormField label="节点名称" required error={errors.label}>
  <Input value={label} onChange={...} placeholder="输入名称" />
</FormField>
```

### 4.4 禁止项

- 禁止在业务代码中直接使用 `window.prompt` / `window.confirm` / `window.alert`。
- 禁止自行组合非语义色（如 `bg-gray-100` / `text-gray-500`）。
- 禁止在组件外使用硬编码间距，优先使用 Design Tokens。

---

## 5. 迁移策略

1. 新页面/新组件必须使用 Design System 1.0 组件。
2. 旧页面在改造时同步替换为 Design System 组件。
3. 不兼容的自定义样式逐步收敛到 `globals.css` 或删除。

---

## 6. 相关文档

- `docs/temp/task0100-unified-design-system-and-secretary-dashboard.md`
- `frontend/tailwind.config.js`
- `frontend/src/app/globals.css`
