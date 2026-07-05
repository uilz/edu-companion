# Task #89 Project 模块多视图重构 + 拖拽全模块迁移 — 实现记录

> 时间: 2026-07-05
> 分支: main
> PR 拆分: PR #1（基础设施）→ PR #2（详情页拆分）→ PR #3（5 视图）→ PR #4（其他模块拖拽迁移）→ PR #5（文档 + 验收）

## 一、目标回顾

把 Project 模块详情页从 1225 行单体重构为可维护的 5 视图结构，并统一全项目拖拽实现到 @dnd-kit。

## 二、架构决策（详见 [ADR 0008](../adr/0008-project-multiview-architecture.md)）

| 决策 | 选择 | 理由 |
|------|------|------|
| 拖拽库 | @dnd-kit/core + sortable + utilities | 跨容器拖拽、键盘可访问、动画、触屏支持 |
| 文档编辑 | Markdown + `@[节点标题]` 引用 | 零新增存储、复用 description 字段 |
| 节点状态字段 | 复用 `project_nodes.status` | 看板列直接用 status，零 DB 迁移 |
| 视图偏好存储 | 扩展 `user_settings.view.{projectId}` | 复用 D16 JSONB 仓储、跨设备一致 |
| Timeline → Activity | 重写为多源事件流 | 不只是节点操作，含里程碑/引用/版本 |

## 三、5 视图职责

| 视图 | 用途 | 关键能力 |
|------|------|----------|
| 手稿（document） | 长文/读书笔记 | 树扁平展示、@引用跳转+高亮、反向引用 Badge |
| 大纲（outline） | 树形结构 | 折叠展开、子节点、@引用+反向引用 Badge |
| 看板（kanban） | 任务跟踪 | 4 列（草稿/进行中/已完成/已归档）、跨列拖拽改 status |
| 知识图谱（knowledge） | 节点关系 | 网格卡片、邻接可视化（保留原版） |
| 活动流（activity） | 项目活动 | 节点编辑/完成/里程碑/引用事件按时间倒序 |

## 四、PR 拆分与落地

### PR #1 — 基础设施（已完成）

- 后端: UserSettingsRepo 扩展 `NS_VIEW` / `get_view_pref` / `set_view_pref`
- 后端: settings_api.py 新增 `GET/PUT /api/settings/view/{project_id}`
- 后端: project_service 新增 `update_node_status` / `reorder_nodes`
- 后端: project/routes.py 新增 `PATCH /nodes/{id}/status` + `POST /nodes/reorder`
- 前端: package.json 装 @dnd-kit

### PR #2 — 详情页拆分（已完成）

- page.tsx: 1225 → 361 行
- types.tsx: 共享类型（Project / ProjectNode / Milestone / Version / NODE_STATUS_COLUMNS / FlatNode）
- hooks/useProjectData.ts: 项目数据 + 操作
- hooks/useViewPreference.ts: 视图偏好持久化
- components/NodeEditor.tsx / VersionHistory.tsx / NodeRow.tsx / NodeCard.tsx: 提取共享组件
- lib/dnd/{DndProvider, SortableItem, DroppableColumn}.tsx: 共享拖拽原语
- lib/parseNodeRefs.ts: @引用解析工具

### PR #3 — 5 视图（已完成）

- views/DocumentView.tsx: 手稿视图（@引用跳转+高亮+反向引用 Badge）
- views/OutlineView.tsx: 增强大纲（@引用+反向引用 Badge）
- views/KanbanView.tsx: 4 列看板（跨列拖拽改 status）
- views/KnowledgeView.tsx: 保留原版
- views/ActivityView.tsx: 重写 timeline 为多源事件流
- views/ViewSwitcher.tsx: 5-tab 切换器
- view/{document,kanban,activity}/page.tsx: 3 个 redirect page
- view/timeline/page.tsx: 改为 redirect → activity（保留 URL 兼容）
- view/outline/page.tsx: 改为 redirect → ?view=outline

### PR #4 — 全模块拖拽迁移（已完成）

- planning/daily/page.tsx: HTML5 DragEvent → @dnd-kit useDraggable/useDroppable
- resources/page.tsx + import/page.tsx: 文件上传 drop zone 抽到 lib/dnd/FileDropZone.tsx

### PR #5 — 文档 + 验收（本 PR）

- docs/temp/task-89-project-multiview.md: 本文件
- docs/adr/0008-project-multiview-architecture.md: 5 视图架构 ADR
- docs/modules/project-based-exploration/overview.md: 同步视图章节
- e2e/project-multiview.spec.ts: 6 case 自动化验证
- rebuild.sh + 浏览器手测

## 五、关键设计权衡

### 1. types.ts → types.tsx rename

NODE_TYPE_LABELS 包含 JSX 元素（lucide icons），TS 不允许 .ts 文件含 JSX。改为 .tsx，13 个 import 同步更新。

### 2. @dnd-kit 类型挑战

dnd-kit 导出 `DraggableSyntheticListeners`（不是 SyntheticListenerMap）和 `DraggableAttributes`，无 index signature 不能直接赋给 `Record<string, unknown>`。统一改用 dnd-kit 导出的精确类型。

### 3. DocumentView @引用"跳 vs 编辑"

- @引用点击 → 滚动到目标 BlockRow + ring 高亮 1.5s（不打开编辑器）
- 标题点击 → 打开 NodeEditor 编辑
- 两者职责分离，避免冲突

### 4. FileDropZone 设计

- dnd-kit 不能管 OS 文件拖入（只能管 component 间拖拽）
- FileDropZone 同时挂 useDroppable（视觉反馈）+ 原生 onDrop（拿 file）
- 视觉反馈用 dnd-kit 的 isOver 替代 useState

### 5. URL 同步策略

- view 切换：setView 立即更新 state + 同步 URL ?view= + 后台 PUT 偏好
- 首次加载：URL ?view= 优先于服务端偏好
- 旧 URL /view/timeline 保留 redirect → ?view=activity 兼容

## 六、风险与回退

| 风险 | 缓解 |
|------|------|
| @dnd-kit 与 Next.js 14 SSR | 所有用文件已 "use client"，DndContext 在 client boundary |
| 1225 行拆分回归 | typecheck/lint 通过，UI 验收分视图走 |
| 看板 status 乐观更新失败 | 失败时 refetch 回滚 + console.error |
| 视图偏好首次未设置 | 默认 document，可后续切换覆盖 |

## 七、验收

1. ✅ `cd frontend && npx tsc --noEmit` 任务相关错误清零（pre-existing 错误不在范围）
2. ⏳ `cd frontend && npx next lint` ESLint 检查
3. ⏳ `cd backend && pytest tests/ -k "project or settings_view"` 单测
4. ⏳ `bash rebuild.sh` 重启前后端
5. ⏳ 浏览器手测：5 视图切换 / 拖拽 / @引用跳转高亮 / 偏好持久
6. ⏳ `cd frontend && npx playwright test project-multiview` E2E

## 八、后续 TODO

- 思维导图 / 无限画布视图（用户未选）
- 跨项目节点引用 UI 优化
- Live collaboration / CRDT
- 富文本编辑（Tiptap/Lexical）
- 看板视图增加列内拖拽排序（同列内重排）
