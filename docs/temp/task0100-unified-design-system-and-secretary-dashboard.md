# Task 0100: 统一设计系统 + 秘书仪表盘改造方案

> 版本：v1.0
> 状态：设计中
> 决策：方案 B —— 先做统一设计系统 + 秘书仪表盘，再反推各壳改造

---

## 1. 问题诊断

### 1.1 已重构模块现状

| 模块 | 当前状态 | 主要问题 |
|------|----------|----------|
| 认知中心（Phase 3） | 事件消费、投影刷新已通 | 前端无统一消费入口，认知状态散落在各壳自行查询 |
| 秘书编排器（Phase 4） | 提案、上下文、计划请求已通 | `/secretary` 是独立通知中心，没有成为学习入口 |
| 规划壳（Phase 5） | 主动生成计划项、确认池已通 | 与秘书、练习、知识树联动停留在事件通知，无统一待办视图 |
| 练习反馈（Phase 6） | 信息增益反馈已通 | 反馈面板孤立，答完题后没有自然引导到复习/规划/知识树 |
| 知识树壳（Phase 11） | G6 重构、四实体解耦已通 | 编辑体验简陋，与练习/闪卡/计划没有联动入口 |

### 1.2 根因分析

1. **没有统一设计系统**：各壳使用自己的样式类名、间距、颜色、圆角、动效，导致产品感割裂。
2. **没有统一首页/入口**：`/secretary` 是通知页，`/` 是 Cockpit 驾驶舱，两者数据重复、职责重叠。
3. **没有统一学习活动模型**：练习、阅读、闪卡、规划、知识树各自产生数据，但用户看不到一条连续的学习时间线。
4. **事件协议止于通知**：事件被消费后产生提案或计划，但用户仍需跳到各壳执行，缺少“一站式操作”。

---

## 2. 设计目标

### 2.1 总体目标

把产品从“多个能用的壳”升级为“一个统一的学习工作空间”：

- **视觉一致**：所有壳共享同一套 Design System。
- **入口统一**：秘书仪表盘成为登录后首页，替代现有 Cockpit 与 Secretary 分离的局面。
- **数据联动**：建立统一学习活动流，让练习、阅读、闪卡、规划、知识树的操作互相可见、可追溯。
- **操作闭环**：在仪表盘上即可完成采纳建议、确认计划、开始练习、查看反馈等高频动作。

### 2.2 范围边界

**在本次范围内**：
- Design System 1.0 组件规范 + 组件补齐。
- 秘书仪表盘首页改造（融合 Cockpit + Secretary）。
- 跨壳学习活动流数据模型与 API。
- 知识树壳按 Design System 规范完成编辑体验改造（作为第一个迁移示例）。

**不在本次范围内**：
- 重新设计认知算法。
- 重写所有壳页面（知识树之后的壳按阶段迁移）。
- 移动端原生 App。

---

## 3. Design System 1.0

### 3.1 设计原则

1. **专业克制**：以 slate 中性色为底，单一强调色（accent）引导操作。
2. **信息密度适中**：教育工具需要展示大量状态，卡片、列表、标签体系优先。
3. **响应式优先**：同一套组件在 desktop/tablet/mobile 三端可复用。
4. **动效克制**：过渡 150ms，主要用于状态反馈，不喧宾夺主。

### 3.2 设计令牌（Tokens）

基于现有 `globals.css` 收敛，形成 SSOT：

| Token | 用途 | 当前值示例 |
|-------|------|-----------|
| `--color-page` | 页面背景 | `#fbfaf7` / dark `#0f0f15` |
| `--color-surface` | 卡片/面板背景 | `#ffffff` / dark `#1a1a22` |
| `--color-surface-elevated` | 浮层面板 | `#ffffff` / dark `#23232d` |
| `--color-surface-hover` | 悬停背景 | `rgba(0,0,0,0.04)` |
| `--color-accent` | 主强调色 | `#2563EB` |
| `--color-accent-hover` | 强调悬停 | `#1d4ed8` |
| `--color-success` | 成功/已掌握 | `#22c55e` |
| `--color-warning` | 警告/紧急 | `#f59e0b` |
| `--color-danger` | 错误/删除 | `#ef4444` |
| `--color-info` | 信息提示 | `#3b82f6` |
| `--color-ink-primary` | 主文本 | `#0f172a` / dark `#f1f5f9` |
| `--color-ink-secondary` | 次级文本 | `#475569` / dark `#94a3b8` |
| `--color-ink-muted` | 弱化文本 | `#94a3b8` / dark `#64748b` |
| `--color-border` | 边框 | `rgba(0,0,0,0.08)` |
| `--radius-card` | 卡片圆角 | `12px` |
| `--radius-button` | 按钮圆角 | `8px` |
| `--radius-input` | 输入框圆角 | `8px` |
| `--shadow-sm` | 轻微阴影 | `0 1px 2px rgba(0,0,0,0.05)` |
| `--shadow-md` | 卡片悬停 | `0 4px 12px rgba(0,0,0,0.08)` |

### 3.3 组件清单

#### 3.3.1 已存在需规范化的组件

| 组件 | 当前文件 | 改造点 |
|------|----------|--------|
| Button | `components/ui/Button.tsx` | 统一 size/variant 命名，补齐 loading 状态 |
| Card | `components/ui/Card.tsx` | 默认圆角改为 12px，补齐 CardDescription |
| Dialog | `components/ui/ConfirmDialog.tsx` | 提取通用 `Dialog`（含 overlay/close/animation） |
| Toast | `components/ui/Toast.tsx` | 统一位置、图标、自动关闭时间 |
| Skeleton | `components/ui/Skeleton.tsx` | 补齐卡片/列表/文本变体 |
| EmptyState | `components/ui/EmptyState.tsx` | 统一空态图标、标题、引导按钮 |
| Badge | `components/ui/Badge.tsx` | 补齐 variant（default/secondary/outline/destructive） |
| Progress | `components/ui/Progress.tsx` | 统一高度、颜色、label 位置 |
| StatCard | `components/ui/StatCard.tsx` | 统一为 dashboard 数据卡样式 |

#### 3.3.2 需要新增的组件

| 组件 | 用途 | 说明 |
|------|------|------|
| `FormField` | 表单字段统一包装 | label + input + error + hint |
| `Input` | 文本输入 | 受控、clear、prefix/suffix |
| `Textarea` | 多行文本 | auto-resize、maxLength |
| `Select` | 下拉选择 | 含 search、group、disabled |
| `Tabs` | 标签切换 | 含 underline/pill 两种样式 |
| `Toggle` / `Switch` | 开关 | 用于状态切换 |
| `RadioGroup` | 单选组 | 水平/垂直布局 |
| `CheckboxGroup` | 多选组 | 批量操作使用 |
| `DropdownMenu` | 下拉菜单 | 替代手写 context menu |
| `Tooltip` | 工具提示 | 基于 title/description 的轻量提示 |
| `Avatar` | 用户头像 | 含 fallback 文字 |
| `CommandPalette` | 命令面板 | 全局搜索/跳转（后续迭代） |
| `Timeline` | 时间线 | 统一展示学习活动流 |
| `ActivityItem` | 活动项 | 学习活动流的最小单元 |

### 3.4 组件使用规范

#### 3.4.1 按钮层级

| 变体 | 用途 |
|------|------|
| `primary` | 页面主行动（开始练习、确认计划、保存） |
| `secondary` | 次行动（编辑、添加、查看更多） |
| `outline` | 低优先级行动（取消、返回、设置） |
| `ghost` | 工具栏图标按钮 |
| `danger` | 删除、解除关联 |

#### 3.4.2 卡片层级

| 类型 | 用途 |
|------|------|
| `surface` | 普通内容卡片 |
| `elevated` | 浮层/下拉面板 |
| `interactive` | 可点击卡片，带 hover 边框 |
| `accent` | 强调卡片（今日焦点、AI 推荐） |

#### 3.4.3 间距系统

统一使用 4px 基栅格：
- `xs = 4px`, `sm = 8px`, `md = 12px`, `lg = 16px`, `xl = 24px`, `2xl = 32px`
- 页面内容区最大宽度：`max-w-5xl`（1280px）用于仪表盘，`max-w-4xl` 用于详情页。

---

## 4. 秘书仪表盘（Secretary Dashboard）

### 4.1 定位

秘书仪表盘是用户登录后的默认首页（`/`），替代现有 Cockpit 与 `/secretary` 分离的局面。它是：

- **学习中枢**：展示今日该做什么、当前学习状态、AI 建议。
- **待办中心**：秘书提案、计划确认、系统通知统一处理。
- **活动入口**：一键进入练习、阅读、闪卡、知识树等具体场景。

### 4.2 信息架构

```
Secretary Dashboard
├── Header
│   ├── 问候语 + 日期
│   ├── 全局搜索（后续）
│   └── 设置入口
├── 今日焦点（Focus Card）
│   ├── 当前最优先任务
│   ├── 预计时间
│   └── 主行动按钮（开始 / 查看）
├── 状态概览（Stats Row）
│   ├── 薄弱点 / 停滞项 / 学习天数 / 认知负荷
│   ├── 累计练习 / 学习时长 / 已掌握 / 连续天数
│   └── 点击下钻到学情分析/知识树
├── 待处理（Pending Panel）
│   ├── Tab：秘书建议 / 计划确认 / 系统通知
│   ├── 列表：ProposalCard / ConfirmationCard
│   └── 批量操作栏
├── AI 推荐（Recommendations）
│   ├── 紧急补强 / 巩固提升 / 新知识
│   └── 每项带下钻链接
├── 学习活动时间线（Activity Timeline）
│   ├── 最近练习 / 阅读 / 闪卡 / 知识树 / 规划操作
│   └── 按时间倒序，支持按壳过滤
└── 快速入口（Quick Actions）
    ├── 开始对话 / 练习 / 阅读 / 闪卡 / 知识树 / 规划
    └── 根据当前状态动态排序
```

### 4.3 页面布局

桌面端：
- 左侧固定 280px 窄边栏（Sidebar）：导航入口 + 用户信息。
- 右侧主内容区：分栏布局。
  - 左侧 2/3：今日焦点、待处理、AI 推荐、时间线。
  - 右侧 1/3：状态概览、快速入口、最近成就。

平板/移动端：
- 顶部 header + 抽屉导航。
- 单列堆叠：今日焦点 → 状态概览 → 待处理 → AI 推荐 → 时间线 → 快速入口。

### 4.4 API 契约

#### 4.4.1 获取仪表盘数据

```http
GET /api/secretary/dashboard
```

响应：

```json
{
  "greeting": "早上好，橙子",
  "date": "2026-07-11",
  "focus": {
    "id": "plan_xxx",
    "type": "plan_item",
    "title": "复习 线性代数基础",
    "description": "基于遗忘曲线，建议今日复习",
    "estimated_minutes": 15,
    "action": { "type": "navigate", "target": "/practice?node=kn_xxx" }
  },
  "stats": {
    "weak_count": 3,
    "stagnant_count": 2,
    "streak_days": 5,
    "cognitive_load": 0.42,
    "total_questions": 128,
    "study_minutes": 340,
    "mastered_count": 12,
    "today_questions": 8
  },
  "pending": {
    "proposals": [...],
    "confirmations": [...],
    "notifications": [...]
  },
  "recommendations": {
    "urgent": [...],
    "building": [...],
    "new_topic": [...]
  },
  "activities": [
    {
      "id": "act_xxx",
      "activity_type": "practice_answer",
      "module": "practice",
      "title": "完成 3 道练习题",
      "description": "线性代数基础 · 正确率 67%",
      "timestamp": 1720700000,
      "status": "completed",
      "deep_link": "/practice/session/xxx",
      "metadata": { "accuracy": 0.67, "node_id": "kn_xxx" }
    }
  ]
}
```

#### 4.4.2 采纳建议 / 确认计划

复用现有 API：
- `POST /api/secretary/proposals/{id}/accept`
- `POST /api/planning/confirmations/{id}/accept`

#### 4.4.3 获取学习活动流

```http
GET /api/activities?limit=20&module=&cursor=
```

用于时间线独立分页加载。

---

## 5. 跨壳学习活动流（Learning Activity Stream）

### 5.1 问题

当前各壳产生的事件（`AnswerSubmitted`、`PlanItemRequested`、`TreeNodeCreated` 等）被不同 handler 消费，但没有一个统一的地方记录“用户今天做了什么”。

### 5.2 统一模型

新增 `learning_activities` 表：

```sql
CREATE TABLE learning_activities (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    activity_type VARCHAR(32) NOT NULL, -- practice_answer, session_completed, flashcard_reviewed, reading_progress, plan_item_confirmed, tree_node_created, ...
    module VARCHAR(32) NOT NULL,        -- practice, flashcard, reading, planning, knowledge_tree, secretary
    source_event_id VARCHAR(64),        -- 来源事件 ID（如 AnswerSubmitted.event_id）
    source_event_type VARCHAR(64),      -- AnswerSubmitted
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'completed', -- completed / pending / failed
    timestamp TIMESTAMPTZ NOT NULL,
    deep_link VARCHAR(512) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_learning_activities_user_time ON learning_activities(user_id, timestamp DESC);
CREATE INDEX idx_learning_activities_module ON learning_activities(user_id, module, timestamp DESC);
CREATE INDEX idx_learning_activities_type ON learning_activities(user_id, activity_type, timestamp DESC);
```

### 5.3 事件映射

| 来源事件 | activity_type | module | 说明 |
|----------|---------------|--------|------|
| `AnswerSubmitted` | `practice_answer` | `practice` | 每答一题生成一条 |
| `SessionCompleted` | `session_completed` | `practice` | 练习/考试完成 |
| `FlashCardReviewed` | `flashcard_reviewed` | `flashcard` | 闪卡复习 |
| `ReadingProgressUpdated` | `reading_progress` | `reading` | 阅读进度更新 |
| `PlanItemRequested` | `plan_item_suggested` | `planning` | 系统建议计划项 |
| PlanItemConfirmed | `plan_item_confirmed` | `planning` | 用户确认计划项 |
| `TreeNodeCreated` | `tree_node_created` | `knowledge_tree` | 创建知识树节点 |
| `TreeNodeLinkedToCognitiveNode` | `tree_node_linked` | `knowledge_tree` | 关联认知节点 |
| `SecretaryProposalGenerated` | `proposal_generated` | `secretary` | 生成秘书建议 |
| SecretaryProposalAccepted | `proposal_accepted` | `secretary` | 采纳秘书建议 |

### 5.4 消费方式

1. **仪表盘时间线**：按时间倒序展示最近 20 条，支持按 module 过滤。
2. **秘书编排器**：基于活动流判断用户状态，生成更准确的建议。
3. **知识树壳**：在节点详情面板展示该节点相关的学习活动。

### 5.5 实现位置

- 后端：`backend/app/services/learning_activity_service.py` + `backend/app/infrastructure/db/models/learning_activity.py`
- 事件 handler：`backend/app/domain/learning_activity/event_handler.py`
- API：`backend/app/api/activities.py`
- 前端：`frontend/src/lib/api/activity-api.ts` + `frontend/src/hooks/useLearningActivities.ts`

---

## 6. 知识树壳编辑体验改造（Design System 1.0 首个迁移示例）

### 6.1 目标

把知识树页从“demo 级编辑”升级到符合 Design System 1.0 的“产品级编辑”。

### 6.2 改造清单

| 改造项 | 说明 |
|--------|------|
| 节点编辑对话框 | 使用 `Dialog` + `FormField` + `Input` + `Select` + `Textarea` + `EmojiPicker` |
| 树编辑对话框 | 编辑标题、描述、默认视图、默认布局 |
| 创建边对话框 | 源节点、目标节点、边类型、强度 |
| 撤销重做 | 基于快照的历史栈，支持 50 步 |
| 拖拽改父节点 | G6 拖拽结束若覆盖目标节点则触发移动 |
| 批量操作 | Shift+点击多选，批量删除/移动/关联认知节点 |
| 键盘快捷键 | F2 编辑、Delete 删除、Ctrl+N 添加子节点、方向键切换、Ctrl+Z/Y 撤销重做 |
| 删除确认 | 使用 `ConfirmDialog`，不再使用 `window.confirm` |

### 6.3 不再使用的实现

- `window.prompt` / `window.confirm`
- 手写 inline prompt
- 临时性的 alert 风格提示

---

## 7. 分阶段迁移计划

### Phase 1：Design System 1.0 基础建设（3-4 天）

**输入**：现有 UI 组件清单 + 设计令牌草稿。
**输出**：
- 补齐缺失组件（Form/Input/Select/Tabs/Toggle/CheckboxGroup/DropdownMenu/Tooltip/Timeline/ActivityItem）。
- 规范化现有组件（Button/Card/Dialog/Toast/Skeleton/EmptyState/Badge/Progress/StatCard）。
- 更新 `globals.css` 中的 Design Tokens 为 SSOT。
- 编写组件使用示例与规范文档。

**验收**：
- 所有新增组件 `npx tsc --noEmit` 通过。
- 至少一个页面（如知识树）开始接入新组件。

### Phase 2：跨壳学习活动流（2-3 天）

**输入**：Design System 1.0 + 事件协议。
**输出**：
- `learning_activities` 表 + ORM + 迁移。
- `LearningActivityEventHandler` 订阅关键事件并写入活动流。
- `GET /api/activities` API。
- 前端 `useLearningActivities` hook。

**验收**：
- 完成一次练习后，活动流出现 `practice_answer` 记录。
- 创建知识树节点后，活动流出现 `tree_node_created` 记录。

### Phase 3：秘书仪表盘首页改造（4-5 天）

**输入**：活动流 + Secretary API + Cockpit 数据。
**输出**：
- 新 `SecretaryDashboard` 组件替代现有 `/` 渲染。
- 融合 Cockpit 焦点/统计/推荐/时间线 + Secretary 提案/确认/批量操作。
- `/secretary` 路由 301 重定向到 `/`。
- 移动端/平板端适配。

**验收**：
- 登录后默认进入仪表盘，可见今日焦点、待处理、活动流。
- 可在仪表盘直接采纳秘书建议、确认计划项。
- `rebuild.sh` 通过。

### Phase 4：知识树壳按 Design System 迁移（3-4 天）

**输入**：Design System 1.0 + 活动流。
**输出**：
- 节点/树/边编辑对话框使用新组件。
- 撤销重做、快捷键、拖拽改父节点、批量操作。
- 节点详情面板接入活动流（展示该节点相关学习活动）。

**验收**：
- 无 `window.prompt` / `window.confirm`。
- 撤销重做覆盖主要操作。
- 活动流在节点详情中可见。

### Phase 5：其他壳按优先级迁移（后续迭代）

按以下顺序逐步迁移：
1. 练习壳（反馈面板 + 推荐下钻）。
2. 规划壳（确认池 + 时间线）。
3. 闪卡壳（复习流程 + 活动记录）。
4. 阅读壳（笔记/标注 + 材料关联）。
5. 对话壳（Context Pipeline + 提案入口）。

---

## 8. 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 设计系统方案 | 基于现有 Tailwind + 规范化 | 改动成本可控，避免引入新库带来的破坏性替换 |
| 首页入口 | 秘书仪表盘替代 Cockpit | 秘书编排器是跨壳大脑，天然适合做学习中枢 |
| 活动流存储 | 新增 `learning_activities` 表 | 事件是写时触发，活动流是读时聚合，分离职责更清晰 |
| 知识树编辑历史 | 快照式撤销重做 | 实现简单、覆盖主要操作；操作级撤销后续可升级 |
| 旧 Secretary 页 | 301 重定向到 `/` | 避免两个入口并存导致的数据不一致 |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 设计系统改造面大 | 回归点多 | 先补齐缺失组件，再逐个页面迁移；每页迁移后跑 rebuild.sh |
| 活动流数据量大 | 性能下降 | 按用户 + 时间分区索引；前端分页加载 |
| Secretary Dashboard 数据聚合复杂 | 首页加载慢 | 后端聚合为单个 `/api/secretary/dashboard`；关键数据缓存 |
| 旧 Cockpit 用户习惯 | 首页变化大 | 保留核心模块（今日焦点、统计、时间线），在其基础上增强 |

---

## 10. 验收标准（总）

- [ ] Design System 1.0 组件全部可用，类型检查通过。
- [ ] `/` 渲染 Secretary Dashboard，功能覆盖原 Cockpit + Secretary。
- [ ] `/secretary` 重定向到 `/`。
- [ ] 学习活动流可记录并展示练习、知识树、规划等操作。
- [ ] 知识树页无 `window.prompt` / `window.confirm`，支持撤销重做、快捷键、拖拽改父节点。
- [ ] `rebuild.sh` 全量通过。
- [ ] 文档更新：`docs/adr/0023-unified-design-system.md`、`docs/modules/design-system/overview.md`。

---

## 11. 相关文档

- `docs/adr/0022-knowledge-tree-shell.md`
- `docs/temp/task0024-knowledge-tree-shell-design.md`
- `docs/temp/task0024-knowledge-tree-shell-implementation-plan.md`
- `frontend/src/components/ui/*`
- `frontend/src/components/layout/AppShell.tsx`
- `frontend/src/components/dashboard/Cockpit.tsx`
- `frontend/src/app/secretary/page.tsx`
