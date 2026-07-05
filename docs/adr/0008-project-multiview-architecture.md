# ADR 0008: Project 模块 — 多视图架构 + @dnd-kit 全量迁移

## Status

Accepted (Task #89, 2026-07-05)

## Context

`/project/[id]` 详情页有 1225 行单体组件，仅 3 个视图（大纲/时间线/知识图谱），无文档/手稿/看板形态。长期主题性研究的工作台只支持树形大纲，与"阅读/写作/任务跟踪"等多场景脱节。

拖拽全项目用自实现 HTML5 DragEvent：项目大纲 1 处、planning/daily 1 处、resources 1 处、import 1 处，无库。

用户偏好只有主题/风格/学习/通知，缺"按项目记忆视图"。

## 决策

### 决策 1 — 拖拽库选 @dnd-kit

| 候选 | 评估 | 选择 |
|------|------|------|
| @dnd-kit/core + sortable | 跨容器拖拽、键盘可访问、动画、触屏支持、活跃维护 | ✅ |
| react-dnd | API 复杂、需要 HTML5Backend，触屏支持差 | ❌ |
| 自实现 HTML5 | 跨容器/触屏/键盘都需手写 | ❌ |

**结果**：引入 `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities`，统一替换 4 处自实现拖拽（项目大纲 / planning/daily / resources / import）。

### 决策 2 — 文档编辑用 Markdown + @引用语法

不用 Tiptap/Lexical 等富文本编辑器（成本高），复用 description 字段 + `parseNodeRefs` 工具解析 `@[节点标题]`：

- 零新增存储（description 字段已存在）
- 解析为可点击 link，点击跳转+高亮
- 找不到目标节点时回退为普通文本（不报错）

### 决策 3 — 节点状态复用 `project_nodes.status` 字段

`status` 字段已在 schema 中存在（pending/active/completed/archived），直接用，避免 DB 迁移：

- 看板 4 列 = 4 个 status
- 跨列拖拽 = PATCH `/nodes/{id}/status` API
- ALTER TABLE ... IF NOT EXISTS 兼容旧表

### 决策 4 — 视图偏好扩展 `user_settings.view.{projectId}`

复用 D16 已有的 `user_settings` JSONB 表，新增 `NS_VIEW = "view"` 命名空间：

```python
settings["view"][project_id] = "document" | "outline" | "kanban" | "knowledge" | "activity"
```

- 跨设备一致
- 白名单校验：`PROJECT_VIEW_NAMES = ("document", "outline", "kanban", "knowledge", "activity")`
- URL ?view= 优先于服务端偏好（首次加载）
- 切换时立即更新 state + 同步 URL + 后台 PUT（失败静默）

### 决策 5 — Timeline 重写为 Activity

Timeline 只展示节点操作时间线，过于单薄。重写为多源事件流（节点编辑/完成/里程碑/引用，按时间倒序）：

- 拉取 `GET /api/projects/{id}/milestones`（已有）
- 节点 `updated_at` 排序
- `linked_node_ids` 非空的节点 = 引用事件
- 时间线 UI 改为"左侧时间戳 + 右侧事件卡"模式

### 决策 6 — 5 视图职责分离

| 视图 | 用途 | 拖拽 | 节点编辑 |
|------|------|------|----------|
| document | 长文/读书笔记 | dnd-kit 整体重排 | 标题点击 |
| outline | 树形结构 | dnd-kit 根节点重排 | 子节点/折叠 |
| kanban | 任务跟踪 | dnd-kit 跨列拖拽 | 卡片点击 |
| knowledge | 节点关系 | 无（保留原版） | 卡片点击 |
| activity | 事件流 | 无 | 节点链接可点击编辑 |

### 决策 7 — 抽 FileDropZone 共享组件

OS 文件拖入 dnd-kit 不能直接管（只能管 component 间），所以 FileDropZone 同时挂 useDroppable（视觉反馈）+ 原生 onDrop（拿 file）：

- 替代 resources / import 中两份手写 drop zone
- 视觉反馈由 useDroppable 的 isOver 替代 useState

### 决策 8 — types.ts → types.tsx rename

NODE_TYPE_LABELS 包含 JSX 元素，TS 不允许 .ts 含 JSX。13 个 import 同步更新。

## 后果

### 正面

- 详情页 1225 → 361 行，组件化清晰
- 5 视图覆盖研究/写作/任务跟踪多场景
- @dnd-kit 提供统一跨容器/触屏/键盘支持
- 用户偏好跨设备一致
- @引用跳转+高亮+反向 Badge 提升节点互链可发现性

### 负面

- @dnd-kit 类型与 React 事件类型不完全兼容（DraggableAttributes 无 index signature），需要 explicit cast 或 import 精确类型
- 文档视图 @引用点击 vs 标题编辑点击需 UX 区分（已通过职责分离解决）
- FileDropZone 保留原生 onDrop，无法完全消除 HTML5 DragEvent（OS 文件拖入限制）

## 实施

PR 拆分 5 阶段：PR #1（基础设施）→ PR #2（详情页拆分）→ PR #3（5 视图）→ PR #4（全模块拖拽迁移）→ PR #5（文档 + 验收）。

每阶段独立可测、可回退。

## 替代方案

### 方案 A：保持单页 + 内嵌 5 视图切换

✅ 优点：单文件、改动小
❌ 缺点：仍然 1500+ 行、不可维护

### 方案 B：用 react-dnd

✅ 优点：老牌
❌ 缺点：触屏支持差、API 复杂、社区迁移至 @dnd-kit

### 方案 C：视图不记忆偏好

✅ 优点：实现简单
❌ 缺点：用户体验差，每次进项目都是默认视图

最终选择：方案 A 否决、方案 B 否决、方案 C 否决。
