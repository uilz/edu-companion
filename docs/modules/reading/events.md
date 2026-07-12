# 阅读壳事件协议

> 阅读壳通过事件总线发布用户阅读行为，供秘书编排器、规划壳、认知状态中心等消费；同时消费来自规划壳和认知状态中心的事件。

---

## 发出的事件

### 会话生命周期

#### `ReadingSessionStarted`

阅读会话开始。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `session_id` | str | 会话 ID |
| `material_id` | str | 材料 ID |
| `mode` | `intensive` \| `skim` \| `review` | 阅读模式 |
| `started_at` | datetime | 开始时间 |

#### `ReadingSessionEnded`

阅读会话结束。关键事件，触发秘书与规划模块联动。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `session_id` | str | 会话 ID |
| `material_id` | str | 材料 ID |
| `duration_seconds` | float | 阅读时长（秒） |
| `annotations_count` | int | 标注数量 |
| `notes_count` | int | 创建的 FlashCard 反思型数量 |
| `cards_generated` | int | 生成的卡片数量 |
| `linked_node_ids` | list[str] | 关联的认知节点 ID 列表 |
| `ended_at` | datetime | 结束时间 |

#### `ReadingSessionResumed`

中断后恢复阅读会话。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `session_id` | str | 会话 ID |
| `last_chunk_id` | str | 最后浏览的 chunk ID |
| `resumed_at` | datetime | 恢复时间 |

#### `ReadingModeChanged`

阅读模式切换。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `session_id` | str | 会话 ID |
| `old_mode` | `intensive` \| `skim` \| `review` | 旧模式 |
| `new_mode` | `intensive` \| `skim` \| `review` | 新模式 |
| `changed_at` | datetime | 切换时间 |

---

### 标注

#### `ReadingAnnotationCreated`

创建标注（5 颜色多意图分类）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `annotation_id` | str | 标注 ID |
| `material_id` | str | 材料 ID |
| `chunk_id` | str | Chunk ID |
| `color` | `yellow` \| `blue` \| `green` \| `purple` \| `orange` | 颜色 |
| `intent` | `important_concept` \| `data_fact` \| `quotable` \| `doubt` \| `conflict` | 意图 |
| `linked_node_id` | str | 关联认知节点 ID（可选） |
| `created_at` | datetime | 创建时间 |

#### `ReadingAnnotationUpdated`

更新标注。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `annotation_id` | str | 标注 ID |
| `changed_fields` | list[str] | 变更字段列表 |
| `updated_at` | datetime | 更新时间 |

#### `ReadingAnnotationDeleted`

删除标注。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `annotation_id` | str | 标注 ID |
| `deleted_at` | datetime | 删除时间 |

#### `ReadingAnnotationProcessed`

标注被处理（提取为 FlashCard / 发起对话 / 转知识点）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `annotation_id` | str | 标注 ID |
| `target_module` | `flashcard` \| `conversation` \| `cognitive_node` \| `project` | 目标模块 |
| `target_ref_id` | str | 目标模块产生记录的 ID |
| `processed_at` | datetime | 处理时间 |

---

### 笔记与提醒

#### `ReadingNoteCreated`

阅读笔记创建（实际是创建 FlashCard 反思型）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `material_id` | str | 材料 ID |
| `card_id` | str | FlashCard ID |
| `source` | `reading_note` | 固定值 |
| `cross_module_source` | `reading` \| `None` | 跨模块引用来源 |
| `created_at` | datetime | 创建时间 |

#### `ReadingReviewReminderScheduled`

阅读回顾提醒已排入 Planning（复用 PlanItem）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `material_id` | str | 材料 ID |
| `reminder_days` | int | 提醒间隔天数（7/30/90） |
| `scheduled_for` | datetime | 计划提醒时间 |
| `plan_item_id` | str | PlanItem ID |

---

### 进度与对比

#### `MaterialProgressUpdated`

阅读材料进度更新。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `source_module` | str | 固定为 `reading` |
| `material_id` | str | 材料 ID |
| `session_id` | str | 会话 ID |
| `progress_pct` | float | 进度百分比 0.0-1.0 |
| `last_chunk_id` | str | 最后浏览 chunk ID |
| `last_offset` | int | 最后浏览 offset |
| `updated_at` | datetime | 更新时间 |

#### `ReadingMaterialCompleted`

阅读材料完成（progress_pct 达到阈值或用户手动标记完成）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `source_module` | str | 固定为 `reading` |
| `material_id` | str | 材料 ID |
| `session_id` | str | 会话 ID |
| `progress_pct` | float | 完成时进度百分比 |
| `duration_seconds` | int | 总阅读时长（秒） |
| `completed_at` | datetime | 完成时间 |

#### `ReadingComparisonCreated`

创建对比阅读分组。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | str | 用户 ID |
| `comparison_id` | str | 对比分组 ID |
| `material_id_left` | str | 左侧材料 ID |
| `material_id_right` | str | 右侧材料 ID |
| `sync_scroll` | bool | 是否同步滚动 |
| `created_at` | datetime | 创建时间 |

---

## 消费的事件

### `PlanItemCompleted`

当 `source_module='reading'` 的 PlanItem（回顾提醒）被完成时，规划壳通过 `completion_writer.py` 路由回阅读壳，阅读壳可据此更新材料复习状态或发布后续事件。

### `CognitiveStateChanged`

认知状态中心发布。阅读壳刷新已关联认知节点的掌握度展示（如高亮已掌握/薄弱知识点）。

---

## 事件发布位置

| 事件 | 发布位置 |
|------|---------|
| `ReadingSessionStarted` | `app/services/reading/sessions.py` |
| `ReadingSessionEnded` | `app/services/reading/sessions.py` |
| `ReadingSessionResumed` | `app/services/reading/sessions.py` |
| `ReadingModeChanged` | `app/services/reading/sessions.py` |
| `ReadingAnnotationCreated` | `app/services/reading/annotations.py` |
| `ReadingAnnotationUpdated` | `app/services/reading/annotations.py` |
| `ReadingAnnotationDeleted` | `app/services/reading/annotations.py` |
| `ReadingAnnotationProcessed` | `app/services/reading/annotations.py` |
| `ReadingNoteCreated` | `app/services/reading/notes.py` |
| `ReadingReviewReminderScheduled` | `app/services/reading/review_reminder.py` |
| `ReadingComparisonCreated` | `app/services/reading/compare.py` |
| `MaterialProgressUpdated` | `app/services/reading/sessions.py` |
| `ReadingMaterialCompleted` | `app/services/reading/sessions.py` |
