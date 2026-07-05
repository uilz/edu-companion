# Reading 数据模型

> Reading 模块的数据结构（标注、会话）。

**ADR**：[`docs/adr/0003-reading-module.md`](../../adr/0003-reading-module.md)

---

## 1. 阅读标注表 `reading_annotations`

```sql
CREATE TABLE reading_annotations (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    material_id VARCHAR(64) NOT NULL,         -- 关联 Material
    chunk_id VARCHAR(64),                     -- 关联 MaterialChunk
    start_offset INT,                         -- 在 chunk 内的起始 offset
    end_offset INT,                           -- 在 chunk 内的结束 offset
    color VARCHAR(10) NOT NULL,                -- yellow/blue/green/purple/orange
    intent VARCHAR(20) NOT NULL,               -- important_concept/data_fact/quotable/doubt/conflict
    text TEXT,                                 -- 标注原文
    note TEXT,                                 -- 用户附加文字备注
    linked_node_id UUID,                       -- 关联的 CognitiveNode（可选）
    is_processed BOOLEAN DEFAULT FALSE,        -- 是否已被提取/转卡片/转对话
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_annotations_user_material ON reading_annotations(user_id, material_id);
CREATE INDEX idx_annotations_chunk ON reading_annotations(material_id, chunk_id);
CREATE INDEX idx_annotations_color ON reading_annotations(user_id, color);
CREATE INDEX idx_annotations_node ON reading_annotations(linked_node_id) WHERE linked_node_id IS NOT NULL;
```

---

## 2. 阅读会话表 `reading_sessions`

```sql
CREATE TABLE reading_sessions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    material_id VARCHAR(64) NOT NULL,
    mode VARCHAR(20) DEFAULT 'intensive',     -- intensive / skim / review
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    duration_seconds INT,
    chapters_visited JSONB DEFAULT '[]',      -- 访问的章节列表
    annotations_created INT DEFAULT 0,
    notes_created INT DEFAULT 0,              -- 实际是创建的 FlashCard 反思型数量
    cards_generated INT DEFAULT 0,
    linked_node_ids JSONB DEFAULT '[]',       -- 关联/创建的 CognitiveNode (与事件层/FlashCard/Project/LanguageRoom 命名统一, Task #58)
    state_snapshot JSONB,                     -- 中断恢复用（最后浏览位置）
    last_active_at TIMESTAMP
);

CREATE INDEX idx_sessions_user_material ON reading_sessions(user_id, material_id, started_at DESC);
```

---

## 3. 跨项目对比阅读表 `reading_comparisons`

```sql
CREATE TABLE reading_comparisons (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    material_id_left VARCHAR(64) NOT NULL,
    material_id_right VARCHAR(64) NOT NULL,
    sync_scroll BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 4. 阅读模式偏好表 `reading_prefs`

```sql
CREATE TABLE reading_prefs (
    user_id VARCHAR(64) PRIMARY KEY,
    default_mode VARCHAR(20) DEFAULT 'intensive',
    highlight_mastered BOOLEAN DEFAULT TRUE,   -- 是否高亮已掌握知识点
    highlight_weak BOOLEAN DEFAULT TRUE,      -- 是否高亮薄弱知识点
    auto_open_sidebar BOOLEAN DEFAULT TRUE,
    sync_scroll_default BOOLEAN DEFAULT FALSE,
    review_reminder_days JSONB DEFAULT '[7, 30, 90]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 5. 字段说明

### 5.1 标注颜色 `color`

| 值 | 含义 |
|---|------|
| `yellow` | 重要概念 |
| `blue` | 数据/事实 |
| `green` | 可引用段落 |
| `purple` | 疑问/反驳 |
| `orange` | 与其他内容冲突 |

### 5.2 标注意图 `intent`

| 值 | 含义 |
|---|------|
| `important_concept` | 重要概念（建议关联知识点或创建卡片）|
| `data_fact` | 数据/事实（建议提取为数据卡片）|
| `quotable` | 可引用段落（保留为原文引用）|
| `doubt` | 疑问/反驳（建议发起对话）|
| `conflict` | 与其他内容冲突（建议对比分析）|

### 5.3 阅读模式 `mode`

- `intensive` — 精读模式
- `skim` — 略读模式
- `review` — 回顾模式

---

## 6. 数据归属

| 归属模块 | 存储内容 |
|---------|---------|
| **本模块** | 标注、会话、对比、阅读偏好 |
| `Material` / `MaterialChunk` | 材料内容、段落（**已存在，不重建**）|
| `FlashCard` | 笔记（反思型，`source='reading_note'`）|
| `ExplainCard` | 上下文对话标注（**已存在，调用**）|
| `CognitiveNode` | 关联的知识点（**已存在，调用**）|
| 全局事件流 | `ReadingSessionEnded` 事件 |
| 0006 Planning | 回顾提醒（**复用，不重建**）|
