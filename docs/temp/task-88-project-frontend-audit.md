# Project 模块前端设计审查 (Task #88)

**审计日期**: 2026-07-05
**审计范围**: `/project` `/project/[id]` `/project/templates` `/project/[id]/view/{outline,timeline,knowledge}`
**审计账号**: apple492210 (apple123)
**审计视口**: 1600×900 桌面 + 375×667 移动

---

## 一、问题清单

### 🔴 P0：按钮文字竖排/截断

**根因**: 按钮容器在 flex 父级被挤压时，内部文本会按字符竖排或被截断。缺少 `whitespace-nowrap` + `flex-shrink-0` 防护。

#### 1.1 `/project` 列表页 — 创建按钮

- **现象**: 标题区"长期主题性研究的工作台 — 树形大纲、字段级版本、@引用、跨模块输出"占据大量横向空间，挤压右侧操作区
- **截图表现**:
  - "从模板创建" → "从"/"模板创"/"建" 三行竖排
  - "新建项目" → "+ 新建项"/"目" 两行竖排
- **触发视口**: 全屏 (1280+)，但工作台中央区域约 800px
- **代码位置**: `frontend/src/app/project/page.tsx:208-222`
- **修复方案**: 右侧操作容器加 `flex-shrink-0`，按钮加 `whitespace-nowrap`

#### 1.2 `/project/[id]` 详情页 — 里程碑按钮

- **现象**: 标题"审计测试项目" + 描述"用于审计测试"占满左半区，"里程碑"按钮在右边缘
- **截图表现**: "里程碑"文字右侧被裁切到看不见"里"字
- **代码位置**: `frontend/src/app/project/[id]/page.tsx:925-932`
- **修复方案**: 操作容器加 `flex-shrink-0`，按钮加 `whitespace-nowrap`

#### 1.3 `/project/templates` 模板页 — 分类 Tabs

- **现象**: 6 个分类按钮（全部/主题研究/解题分析/项目实践/长篇阅读/长期训练）共占一排
- **截图表现**:
  - 1600 宽度：正常单行
  - 中等宽度 (< 1400)：每个按钮变窄，4 字文字会拆成 "主题研"/"究" 竖排
- **代码位置**: `frontend/src/app/project/templates/page.tsx:159-184`
- **修复方案**: 按钮加 `whitespace-nowrap` + 容器 `flex-wrap` 允许换行

### 🟡 P1：版本号布局混乱

#### 1.4 `/project/[id]` 大纲视图 — v1 位置

- **现象**: 节点行右侧显示"v1"+ 完成状态圆圈，但 v1 在中间，与 radio 视觉割裂
- **代码位置**: `frontend/src/app/project/[id]/page.tsx`（大纲节点行）
- **修复方案**: 重新组织为 [title] [v1 标签] [完成切换] 三段式

---

## 二、根因分析

### Flex 挤压问题
在 Tailwind/CSS Flexbox 中，当 flex 容器空间不足时：
1. 子元素默认 `flex-shrink: 1`（可压缩）
2. 按钮内文本默认 `white-space: normal`（可换行）
3. 中文按字符作为换行点，导致每个字单独换行

**防御性修复（推荐全项目推广）**:
```tsx
// 模式 1: 右侧操作区
<div className="flex items-center gap-2 flex-shrink-0">
  <button className="... whitespace-nowrap">操作</button>
</div>

// 模式 2: 多按钮顶部
<div className="flex items-center gap-2 flex-wrap">
  {tabs.map(...)}  // 允许换行而非压缩
</div>
```

---

## 三、修复方案

### 3.1 `/project` 列表页

```tsx
// Before
<div className="flex items-center gap-2">
  <button ... 从模板创建</button>
  <button ... 新建项目</button>
</div>

// After
<div className="flex items-center gap-2 flex-shrink-0">
  <button className="... whitespace-nowrap">从模板创建</button>
  <button className="... whitespace-nowrap">+ 新建项目</button>
</div>
```

### 3.2 `/project/[id]` 详情页

```tsx
// Before
<div className="flex items-center gap-2">
  <button ... 里程碑</button>
</div>

// After
<div className="flex items-center gap-2 flex-shrink-0">
  <button className="... whitespace-nowrap">里程碑</button>
</div>
```

### 3.3 `/project/templates` 模板页

```tsx
// Before
<div className="flex items-center gap-2 mb-4">
  {categories.map(...)}
</div>

// After
<div className="flex items-center gap-2 flex-wrap mb-4">
  {categories.map(...)}  // 按钮 + whitespace-nowrap
</div>
```

### 3.4 大纲视图 v1 布局 (P1)

重新组织节点行结构，让 v1 紧贴完成状态：
```tsx
<div className="flex items-center gap-3 flex-1 min-w-0">
  <Icon /> <Title truncate /> <span className="text-xs text-ink-secondary">v{n.version}</span>
</div>
<div className="flex items-center gap-2 flex-shrink-0">
  <CompletionToggle />
</div>
```

---

## 四、回归测试

- [ ] 桌面 1600×900：所有按钮单行显示
- [ ] 平板 768×1024：分类 tabs 自动换行而非压缩
- [ ] 移动 375×667：详情页标题过长时按钮不被截断
- [ ] 长项目名 (30+ 字符)：右侧操作按钮保持完整

---

## 五、相关模块可推广

发现 P0 根因是通用 flex 挤压问题，建议对以下模块同时审计：
- `/flashcard/stats` 顶部操作区
- `/reading` 顶部模式切换
- `/liveroom` 顶部场景/角色切换
- `/planning/daily` 时间轴工具栏
- `/files` 上传/管理工具栏
- `/knowledge-tree` 工具栏

（推广实施将作为后续 Task #89+ 跟进）
