# FlashCard 数据模型

> FlashCard 模块的数据结构。

**ADR**：[`docs/adr/0002-card-module.md`](../../adr/0002-card-module.md)

---

## 1. 卡片主表 `flashcards`

```sql
CREATE TABLE flashcards (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    type SMALLINT NOT NULL,                    -- 1-7 (基础问答/填空/对比/流程/应用场景/错题溯源/反思)
    source VARCHAR(30) NOT NULL,               -- manual/practice_error/reading_note/conversation/project/language_room/interest_explorer
    front_text TEXT NOT NULL,
    back_text TEXT,
    back_context TEXT,                         -- 反面附加（如关键论述、原文引用）
    language VARCHAR(20),                      -- 用于 STT/TTS 标注

    -- 来源追溯
    source_ref JSONB,                          -- {"module": "...", "id": "...", "offset": ..., "length": ...}

    -- 状态
    status VARCHAR(20) DEFAULT 'pending',      -- pending / later / processing / completed / suspended / archived
    suspended_at TIMESTAMP,
    is_resolved BOOLEAN DEFAULT FALSE,         -- 错题溯源类型：是否已掌握

    -- FSRS 调度参数（每张卡独立）
    stability FLOAT,                           -- FSRS 稳定性
    difficulty FLOAT,                          -- FSRS 难度
    last_review_at TIMESTAMP,
    next_review_at TIMESTAMP,
    review_count INT DEFAULT 0,
    lapse_count INT DEFAULT 0,                 -- 失败次数（"困难"次数）
    target_retention FLOAT DEFAULT 0.85,       -- 用户设定的目标保留率

    -- 关联
    linked_node_ids JSONB DEFAULT '[]',        -- 关联的 CognitiveNode（多对多）
    node_link_roles JSONB DEFAULT '{}',        -- {"node_id_1": "primary", "node_id_2": "secondary"}
    tags JSONB DEFAULT '[]',                   -- 多标签
    error_book_entry_id UUID,                  -- 错题溯源类型：关联的 ErrorBookEntry

    -- 反思型附加
    response_history JSONB DEFAULT '[]',        -- 反思型：用户多次回答历史

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_flashcards_user_status ON flashcards(user_id, status);
CREATE INDEX idx_flashcards_next_review ON flashcards(user_id, next_review_at) WHERE status = 'pending';
CREATE INDEX idx_flashcards_source ON flashcards(user_id, source);
CREATE INDEX idx_flashcards_type ON flashcards(user_id, type);
```

**`source_ref` 字段 schema**（JSONB）：

```json
{
  "module": "reading",
  "id": "material-uuid",
  "sub_id": "chunk-id-range",
  "offset": 100,
  "length": 200,
  "url": "...",
  "title": "..."
}
```

---

## 2. 复习会话表 `review_sessions`

```sql
CREATE TABLE review_sessions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    card_count INT DEFAULT 0,
    difficult_count INT DEFAULT 0,
    good_count INT DEFAULT 0,
    easy_count INT DEFAULT 0,
    duration_seconds INT,
    source_module VARCHAR(30)                  -- 哪个入口发起的复习（manual/plan_item）
);

CREATE INDEX idx_sessions_user ON review_sessions(user_id, started_at DESC);
```

---

## 3. 复习历史表 `review_history`

```sql
CREATE TABLE review_history (
    id UUID PRIMARY KEY,
    card_id UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    session_id UUID REFERENCES review_sessions(id) ON DELETE SET NULL,
    user_id VARCHAR(64) NOT NULL,
    self_assessment VARCHAR(10) NOT NULL,      -- difficult / good / easy
    stability_before FLOAT,
    stability_after FLOAT,
    difficulty_before FLOAT,
    difficulty_after FLOAT,
    interval_before INT,                       -- 复习间隔（天）
    interval_after INT,
    elapsed_days INT,
    reviewed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_history_card ON review_history(card_id, reviewed_at DESC);
CREATE INDEX idx_history_session ON review_history(session_id);
```

---

## 4. 标签表 `flashcard_tags`

```sql
CREATE TABLE flashcard_tags (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    parent_id UUID REFERENCES flashcard_tags(id) ON DELETE CASCADE,
    level SMALLINT NOT NULL DEFAULT 0,         -- 0/1/2 三层
    color VARCHAR(7),                          -- UI 配色（可选）
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tags_user_parent ON flashcard_tags(user_id, parent_id);
```

---

## 5. 字段说明

### 5.1 `type` 卡片类型

| 值 | 类型 | 关键字段 |
|---|------|---------|
| 1 | 基础问答 | `front_text` / `back_text` |
| 2 | 填空 | `front_text`（带 `__` 占位） / `back_text` |
| 3 | 对比 | `back_context`（各维度）|
| 4 | 流程 | `back_text`（有序步骤）|
| 5 | 应用场景 | `front_text` / `back_text`（含推理）|
| 6 | 错题溯源 | `error_book_entry_id` |
| 7 | 反思 | `response_history`（用户回答历史）|

### 5.2 `source` 来源

7 种来源（详见 `overview.md` §3.2）

### 5.3 `status` 状态

| 值 | 含义 |
|---|------|
| `pending` | 待复习（FSRS 调度）|
| `later` | 稍后处理（来自兴趣探索等）|
| `processing` | 处理中（已触发跨模块导入）|
| `completed` | 已完成（用户标记或长期掌握）|
| `suspended` | 暂停（用户主动暂停）|
| `archived` | 归档（用户主动归档）|

### 5.4 `node_link_roles` 关联角色

- `primary` — 主知识点（weight 1.0）
- `secondary` — 次知识点（weight 0.3）

---

## 6. 数据归属

| 归属模块 | 存储内容 |
|---------|---------|
| **本模块** | 卡片内容、FSRS 参数、复习历史、标签 |
| `CognitiveNode` | 知识点状态、Belief、Scheduling |
| `ErrorBookEntry` | 错题记录（`error_book_entry_id` 关联）|
| `Material` | 阅读材料（`source_ref` 关联）|
| `Question` | 练习题（`source_ref` 关联）|
| 全局事件流 | 复习会话事件、卡片状态变更 |
