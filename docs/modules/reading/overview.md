# 阅读壳（Reading Shell）

> 用户与「学习材料」之间的交互界面：把 PDF、文章、视频等原始材料组织成可阅读、可标注、可笔记、可复习的认知加工入口。

---

## 定位

阅读壳是「认知操作系统 + 场景壳层」架构中的场景壳层之一，负责：

1. 在 `file-management` 之上提供阅读体验增强层（章节展示、阅读模式、标注、笔记、对比、回顾）。
2. 把用户的阅读行为（标注、笔记、进度、模式切换）转化为学习事实事件，供认知诊断、秘书提案、规划安排消费。
3. 与认知节点、闪卡、对话、规划、项目等壳层通过事件协议联动，但不直接维护它们的内部状态。

### 与 file-management 的关系

| 层级 | 职责 | 现有归属 |
|------|------|---------|
| 存储/解析层 | 文件上传、格式解析、分块、向量化、TOC、RAG 索引 | `file-management` |
| **阅读体验层** | 章节展示、阅读模式、标注、笔记、对比、回顾 | **阅读壳（本模块）** |
| 知识层 | 知识点状态、掌握度、关联 | `CognitiveNode` |
| 材料层 | FlashCard / Question / ErrorBookEntry / ExplainCard | 已有 + FlashCard 模块 |

### 不做的事

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 直接更新认知投影 | 破坏 SSOT | 认知状态中心 |
| 维护闪卡复习调度 | 属于闪卡壳 | 闪卡壳 |
| 维护计划项生命周期 | 属于规划壳 | 规划壳 |
| 生成跨模块计划 | 属于秘书编排器 | 秘书编排器 |
| 直接维护错题本 | 属于练习壳 | 练习壳 |

---

## 核心实体

| 实体 | 说明 | 对应表 |
|------|------|--------|
| Reading Material | 原始学习材料（复用 `file-management` 的 `Material`） | `materials` |
| Material Chunk | 材料分块/章节（复用 `file-management` 的 `MaterialChunk`） | `material_chunks` |
| Reading Session | 一次阅读会话 | `reading_sessions` |
| Reading Annotation | 5 色多意图高亮标注 | `reading_annotations` |
| Reading Note | 阅读笔记（复用 FlashCard 反思型） | `flashcards`（`source='reading_note'`） |
| Review Reminder | 阅读回顾提醒（复用 PlanItem） | `plan_items`（`source_module='reading'`） |
| Reading Comparison | 对比阅读分组 | `reading_comparisons` |
| Reading Prefs | 用户阅读偏好 | `reading_prefs` |

---

## 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 阅读会话 | 开始、继续、结束会话；中断恢复；模式切换 | 已实现 |
| 5 色多意图标注 | yellow/blue/green/purple/orange 对应重要概念/数据事实/可引用/疑问/冲突 | 已实现 |
| 标注处理 | 将标注提取为 FlashCard / 发起对话 / 转认知节点 | 已实现 |
| 阅读笔记 | 创建 FlashCard 反思型，自动获得 FSRS 调度 | 已实现 |
| 节点关联 | 标注/笔记关联到认知节点 | 已实现 |
| 进度追踪 | 阅读位置、完成百分比、访问章节 | 已实现 |
| 对比阅读 | 两篇材料并排对比、同步滚动 | 已实现 |
| 回顾提醒 | 基于材料创建复习计划项（复用规划壳） | 已实现 |
| 阅读偏好 | 默认模式、高亮设置、复习间隔等 | 已实现 |
| 颜色后续动作映射 | 前后端共享 5 色 → 意图 → 后续动作元数据 | 已实现 |

---

## API 概览

统一前缀：`/api/reading`

| 方法 | 路由 | 功能 |
|------|------|------|
| POST | `/sessions` | 开始阅读会话 |
| GET | `/sessions/active` | 查询某材料的未结束会话 |
| GET | `/sessions/{id}` | 查询会话 |
| GET | `/sessions` | 列出阅读会话 |
| POST | `/sessions/{id}/end` | 结束会话 |
| POST | `/sessions/{id}/mode` | 切换阅读模式 |
| POST | `/sessions/{id}/activity` | 增量更新会话活动 |
| POST | `/annotations` | 创建标注 |
| GET | `/annotations/{id}` | 查询标注 |
| GET | `/materials/{id}/annotations` | 列出某材料标注（支持按颜色分组） |
| PATCH | `/annotations/{id}` | 更新标注 |
| DELETE | `/annotations/{id}` | 删除标注 |
| POST | `/annotations/{id}/process` | 标记标注已处理 |
| POST | `/notes` | 创建阅读笔记（FlashCard 反思型） |
| GET | `/notes` | 列出阅读笔记 |
| POST | `/review-reminder` | 创建回顾提醒（PlanItem） |
| GET | `/review-reminder` | 查询待处理回顾提醒 |
| DELETE | `/review-reminder/{plan_item_id}` | 取消回顾提醒 |
| GET | `/prefs` | 获取阅读偏好 |
| PATCH | `/prefs` | 更新阅读偏好 |
| POST | `/compare` | 创建对比阅读分组 |
| GET | `/compare` | 获取对比阅读分屏数据 |
| GET | `/compare/list` | 查询对比阅读分组列表 |
| GET | `/meta/colors` | 获取 5 色标注 → 后续动作映射 |

---

## 事件协议

详见 [events.md](./events.md)。

### 发出的事件

- `ReadingSessionStarted`
- `ReadingSessionEnded`
- `ReadingSessionResumed`
- `ReadingModeChanged`
- `ReadingAnnotationCreated`
- `ReadingAnnotationUpdated`
- `ReadingAnnotationDeleted`
- `ReadingAnnotationProcessed`
- `ReadingNoteCreated`
- `ReadingReviewReminderScheduled`
- `ReadingComparisonCreated`
- `MaterialProgressUpdated`
- `ReadingMaterialCompleted`

### 消费的事件

- `PlanItemCompleted`：阅读回顾提醒被完成时，由规划壳路由回阅读壳更新状态。
- `CognitiveStateChanged`：刷新已关联认知节点的掌握度展示。

---

## 前端组件

| 组件/文件 | 职责 |
|----------|------|
| `frontend/src/app/reading/page.tsx` | 阅读材料入口 |
| `frontend/src/app/reading/materials/[id]/page.tsx` | 单材料阅读器 |
| `frontend/src/app/reading/notes/page.tsx` | 阅读笔记列表 |
| `frontend/src/app/reading/compare/page.tsx` | 对比阅读 |
| `frontend/src/lib/api/reading-api.ts` | `/api/reading` API 客户端与类型 |

---

## 后端结构

| 路径 | 职责 |
|------|------|
| `backend/app/api/reading/routes.py` | REST API 路由（仅做 HTTP 转换、参数校验、错误映射） |
| `backend/app/api/reading/schemas.py` | Pydantic 请求/响应模型 |
| `backend/app/services/reading/sessions.py` | 阅读会话业务逻辑与事件发布 |
| `backend/app/services/reading/annotations.py` | 标注 CRUD 与事件发布 |
| `backend/app/services/reading/notes.py` | 阅读笔记（FlashCard 反思型）创建与事件发布 |
| `backend/app/services/reading/review_reminder.py` | 回顾提醒（PlanItem）调度与事件发布 |
| `backend/app/services/reading/compare.py` | 对比阅读分组与事件发布 |
| `backend/app/services/reading/prefs.py` | 阅读偏好 CRUD |
| `backend/app/services/reading/node_ref.py` | 标注/笔记与认知节点关联 |
| `backend/app/infrastructure/db/reading_schema.sql` | 阅读模块表结构 |

---

## 相关文档

- [events.md](./events.md)
- [ADR 0003: Reading 模块](../adr/0003-reading-module.md)
- [临时设计稿](/docs/temp/task0023-reading-shell-design.md)
- [file-management 模块](../file-management/overview.md)
- [flashcard 模块](../flashcard/overview.md)
- [planning 模块](../planning/overview.md)
