# Reading 事件 schema

> Reading 模块产生和消费的事件定义。

**ADR**：[`docs/adr/0003-reading-module.md`](../../adr/0003-reading-module.md)

---

## 1. 事件清单

| 事件 | 触发时机 |
|------|---------|
| `ReadingSessionStarted` | 用户开始阅读会话 |
| `ReadingSessionEnded` | 用户结束阅读会话 |
| `ReadingSessionResumed` | 中断后恢复会话 |
| `ReadingAnnotationCreated` | 创建标注 |
| `ReadingAnnotationUpdated` | 修改标注 |
| `ReadingAnnotationDeleted` | 删除标注 |
| `ReadingAnnotationProcessed` | 标注被处理（提取/转卡片/转对话）|
| `ReadingNoteCreated` | 创建笔记（实际是创建 FlashCard 反思型）|
| `ReadingReviewReminderScheduled` | 触发 0006 Planning 回顾提醒 |

---

## 2. 事件 Schema

### 2.1 阅读会话

```python
class ReadingSessionStarted(DomainEvent):
    user_id: str
    session_id: str
    material_id: str
    mode: Literal["intensive", "skim", "review"]
    started_at: datetime

class ReadingSessionEnded(DomainEvent):
    user_id: str
    session_id: str
    material_id: str
    duration_seconds: float
    annotations_count: int
    notes_count: int  # 创建的 FlashCard 反思型数量（cross_module_source='reading'）
    cards_generated: int
    linked_node_ids: list[str]  # 本次会话关联/创建的 CognitiveNode（统一命名，原 nodes_linked）
    ended_at: datetime

class ReadingSessionResumed(DomainEvent):
    user_id: str
    session_id: str
    resumed_at: datetime
    last_chunk_id: str
```

### 2.2 标注事件

```python
class ReadingAnnotationCreated(DomainEvent):
    user_id: str
    annotation_id: str
    material_id: str
    chunk_id: str
    color: Literal["yellow", "blue", "green", "purple", "orange"]
    intent: Literal["important_concept", "data_fact", "quotable", "doubt", "conflict"]
    linked_node_id: str | None
    created_at: datetime

class ReadingAnnotationUpdated(DomainEvent):
    user_id: str
    annotation_id: str
    changed_fields: list[str]
    updated_at: datetime

class ReadingAnnotationDeleted(DomainEvent):
    user_id: str
    annotation_id: str
    deleted_at: datetime

class ReadingAnnotationProcessed(DomainEvent):
    """标注被处理（提取为 FlashCard、发起对话、转知识点）"""
    user_id: str
    annotation_id: str
    # target_module 必须为 CrossModuleTarget 枚举的合法值（来自 shared.events.CrossModuleTarget）
    #   - flashcard      : 提取为 FlashCard
    #   - conversation   : 发起对话
    #   - cognitive_node : 转为知识点
    target_module: CrossModuleTarget = CrossModuleTarget.FLASHCARD
    target_ref_id: str
    processed_at: datetime
```

### 2.3 笔记与提醒

```python
class ReadingNoteCreated(DomainEvent):
    """实际是创建 FlashCard 反思型"""
    user_id: str
    material_id: str
    card_id: str              # FlashCard.id
    # source: 本模块内部来源（笔记的内部归类）
    #   - reading_note : 阅读笔记反思型
    # cross_module_source: 跨模块引用来源（与 source 互斥，二选一）
    #   - reading      : 来自阅读模块（当前唯一合法跨模块来源）
    source: Literal["reading_note"] = "reading_note"
    cross_module_source: Literal["reading"] | None = "reading"
    created_at: datetime

class ReadingReviewReminderScheduled(DomainEvent):
    """触发 0006 Planning 回顾提醒"""
    user_id: str
    material_id: str
    reminder_days: int        # 7 / 30 / 90
    scheduled_for: datetime
    plan_item_id: str         # 0006 PlanItem.id
```

---

## 3. 事件消费者

### 3.1 本模块消费

- `ReadingSessionStarted` → 写入 `reading_sessions` 表
- `FlashCardCreated`（`source='reading_note'`）→ 更新 `reading_sessions.notes_count`

### 3.2 其他模块消费

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `ReadingAnnotationCreated` | 秘书系统 | 记录阅读活动 |
| `ReadingSessionEnded` | 规划模块 | 计算下次回顾提醒 |
| `ReadingSessionEnded` | 知识图谱 | 更新关联节点的最近访问时间 |
| `ReadingNoteCreated` | 知识图谱 | 关联 `linked_node_ids` 记录 |
| `ReadingAnnotationProcessed`（target=flashcard）| FlashCard | 显示标注来源 |
| `ReadingAnnotationProcessed`（target=cognitive_node）| 知识图谱 | 显示标注引用 |
| `ReadingReviewReminderScheduled` | 0006 Planning | 创建 `PlanItem`（`source_module='reading'`）|

### 3.3 不更新的状态

**关键设计原则**：

- `ReadingSessionEnded` **不**触发 `CognitiveNode.Belief` 更新
- 标注创建/笔记创建**不**触发 `Belief` 更新
- Belief 的合法来源仅：练习答题、FlashCard 复习、对话深度参与、错题标记
- **阅读是被动接收，不构成"主动学习行为"**

---

## 4. 事件粒度

### 4.1 标注处理粒度

- `ReadingAnnotationProcessed` 每次**单个目标**发一次事件
- 同一标注同时提取到 FlashCard 和知识点，发**两次**事件

### 4.2 笔记创建粒度

- 每创建一个反思型 FlashCard 发**一次** `ReadingNoteCreated`
- `source='reading_note'` 标识
- `card_id` 字段关联 `flashcards.id`

### 4.3 回顾提醒粒度

- 用户设置"阅读后 N 天回顾"时，发**一次** `ReadingReviewReminderScheduled`
- 0006 接收后创建 `PlanItem`（`source_module='reading'`，`target_type='reading'`）

---

## 5. 与 0006 Planning 的事件协调

```
ReadingSessionEnded
    └─→ 规划模块消费
        └─→ 创建 PlanItemScheduled(source_module='reading')
            └─→ N 天后触发 PlanItemActivated
                └─→ 用户看到"回顾阅读"提醒
```

**不**新建独立提醒系统，**完全**复用 0006 Planning 的事件链。
