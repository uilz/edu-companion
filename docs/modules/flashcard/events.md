# FlashCard 事件 schema

> FlashCard 模块产生和消费的事件定义。

**ADR**：[`docs/adr/0002-card-module.md`](../../adr/0002-card-module.md)

---

## 1. 事件清单

| 事件 | 触发时机 |
|------|---------|
| `FlashCardCreated` | 卡片创建（任何来源）|
| `FlashCardUpdated` | 卡片内容更新 |
| `FlashCardSuspended` | 用户暂停 |
| `FlashCardResumed` | 用户恢复 |
| `FlashCardReset` | 用户重置调度 |
| `FlashCardArchived` | 用户归档 |
| `FlashCardDeleted` | 用户删除 |
| `FlashCardReviewed` | 复习自评完成 |
| `FlashCardSessionStarted` | 复习会话开始 |
| `FlashCardSessionEnded` | 复习会话结束 |
| `FlashCardStatusChanged` | status 字段变化（later → processing → completed）|
| `FlashCardImportedToModule` | 跨模块导入完成 |

---

## 2. 事件 Schema

### 2.1 卡片生命周期

```python
class FlashCardCreated(DomainEvent):
    user_id: str
    card_id: str
    type: int  # 1-7
    # source: 本模块内部来源
    #   - manual         : 用户手动创建
    #   - system         : 系统生成（如批量补卡）
    # cross_module_source: 跨模块引用来源（与 source 互斥，二选一）
    #   - practice_error : 来自练习错题本
    #   - reading_note   : 来自阅读反思
    #   - conversation   : 来自对话
    #   - project        : 来自项目节点导出
    #   - language_room  : 来自语言房间词汇便签
    #   - interest_explorer : 来自兴趣探索
    source: Literal["manual", "system"] = "manual"
    cross_module_source: Literal[
        "practice_error", "reading_note", "conversation",
        "project", "language_room", "interest_explorer"
    ] | None = None
    linked_node_ids: list[str] = field(default_factory=list)
    source_ref: dict | None = None
    created_at: datetime

class FlashCardUpdated(DomainEvent):
    user_id: str
    card_id: str
    changed_fields: list[str]  # ["front_text", "back_text", "tags"]
    reset_scheduling: bool     # 是否重置了 FSRS 调度
    updated_at: datetime

class FlashCardSuspended(DomainEvent):
    user_id: str
    card_id: str
    suspended_at: datetime

class FlashCardResumed(DomainEvent):
    user_id: str
    card_id: str
    resumed_at: datetime

class FlashCardReset(DomainEvent):
    user_id: str
    card_id: str
    reset_at: datetime
    previous_review_count: int

class FlashCardArchived(DomainEvent):
    user_id: str
    card_id: str
    archived_at: datetime

class FlashCardDeleted(DomainEvent):
    user_id: str
    card_id: str
    deleted_at: datetime
```

### 2.2 复习事件

```python
class FlashCardReviewed(DomainEvent):
    """单次复习自评完成 - 核心事件"""
    user_id: str
    card_id: str
    session_id: str
    self_assessment: Literal["difficult", "good", "easy"]
    stability_before: float
    stability_after: float
    difficulty_before: float
    difficulty_after: float
    interval_before: int  # 天
    interval_after: int
    elapsed_days: int
    linked_node_ids: list[str]    # 关联知识点（用于 Belief 回写）
    node_link_roles: dict[str, str]  # {"node_id": "primary" / "secondary"}
    next_review_at: datetime
    reviewed_at: datetime

class FlashCardSessionStarted(DomainEvent):
    user_id: str
    session_id: str
    source_module: str  # manual / plan_item
    initial_card_count: int
    started_at: datetime

class FlashCardSessionEnded(DomainEvent):
    user_id: str
    session_id: str
    total_cards: int
    difficult_count: int
    good_count: int
    easy_count: int
    duration_seconds: int
    ended_at: datetime
```

### 2.3 状态与跨模块导入

```python
class FlashCardStatusChanged(DomainEvent):
    user_id: str
    card_id: str
    old_status: str
    new_status: str
    changed_at: datetime

class FlashCardImportedToModule(DomainEvent):
    """卡片内容导出到其他模块（与 Project 对称）"""
    user_id: str
    card_id: str
    # target_module 必须为 CrossModuleTarget 枚举的合法值（来自 shared.events.CrossModuleTarget）
    #   - reading        : 导出为阅读笔记
    #   - project        : 导出为项目节点
    #   - cognitive_node : 导出为知识点
    #   - language_room  : 导出为语言房间话题
    target_module: CrossModuleTarget = CrossModuleTarget.READING
    target_ref_id: str
    imported_at: datetime
```

---

## 3. 事件消费者

### 3.1 本模块消费

- `FlashCardCreated` → 写入 `flashcards` 表
- `FlashCardReviewed` → 写入 `review_history` + 更新 `flashcards` FSRS 参数
- `AnswerSubmitted`（错题）→ 创建 `FlashCard`（`source='system'`, `cross_module_source='practice_error'`）
- `ErrorBookEntryReviewed`（已解决）→ 标记 `flashcards.is_resolved = true`
- `ErrorBookEntryResolved` → 标记 `flashcards.status = 'completed'`

### 3.2 知识图谱消费（Belief 回写）

```python
# 知识图谱消费 FlashCardReviewed
async def on_flashcard_reviewed(event: FlashCardReviewed):
    """Belief 小权重贡献 (0.1)"""
    for node_id in event.linked_node_ids:
        role = event.node_link_roles.get(node_id, "secondary")
        weight = 1.0 if role == "primary" else 0.3
        contribution = 0.1 * weight

        if event.self_assessment == "easy":
            await update_belief(node_id, alpha_delta=contribution)
        elif event.self_assessment == "difficult":
            await update_belief(node_id, beta_delta=contribution)
        # "good" 不更新
```

### 3.3 其他模块消费

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `FlashCardCreated` | 秘书系统 | 记录"创建复习卡"行为 |
| `FlashCardReviewed` | 秘书系统 | 触发 `fatigue_manager` 检查（连续复习疲劳）|
| `FlashCardSessionEnded` | 规划模块 | 更新"复习任务"完成状态 |
| `FlashCardSessionEnded` | MoodStress | 可选：触发情绪分析（用户标记"焦虑"时）|
| `FlashCardSessionEnded` | 全局事件流 | 时间线展示 |

### 3.4 错题本双向同步

```python
# 错题卡复习 → ErrorBookEntry.is_resolved
async def on_flashcard_reviewed(event: FlashCardReviewed):
    if event.self_assessment in ["good", "easy"]:
        card = await get_flashcard(event.card_id)
        if card.source == "practice_error" and card.error_book_entry_id:
            await update_error_book_entry(
                card.error_book_entry_id,
                is_resolved=(event.self_assessment == "easy")
            )
```

---

## 4. 事件粒度

### 4.1 单卡 vs 会话

| 粒度 | 事件 |
|------|------|
| **单卡** | `FlashCardCreated` / `FlashCardUpdated` / `FlashCardReviewed` / `FlashCardSuspended` / ... |
| **会话** | `FlashCardSessionStarted` / `FlashCardSessionEnded` |

### 4.2 Belief 回写粒度

- 每张卡复习时，对**每个关联的 `CognitiveNode`** 触发 Belief 更新
- 多知识点时按 `node_link_roles` 计算权重
- 单次更新贡献 0.1（避免复习行为过度影响 Belief）
- **仅**自评"困难"或"简单"时更新；"良好"不更新

### 4.3 错题本同步粒度

- 自评"困难" → 不更新 `ErrorBookEntry`
- 自评"良好" → 标记 `review_count++`，但 `is_resolved` 保持
- 自评"简单" → 标记 `is_resolved = true`

---

## 5. 不更新 Belief 的事件

| 事件 | 是否更新 Belief |
|------|--------------|
| `FlashCardCreated` | ❌（创建行为）|
| `FlashCardUpdated` | ❌（修改行为）|
| `FlashCardSuspended` | ❌ |
| `FlashCardReviewed` | ✅（自评困难/简单时小权重更新）|
| `FlashCardSessionEnded` | ❌（事件聚合）|
| `FlashCardStatusChanged` | ❌（状态变更）|

**关键原则**：只有**用户主动的复习行为**（`FlashCardReviewed`）才更新 Belief；其他卡片生命周期事件**不**更新。
