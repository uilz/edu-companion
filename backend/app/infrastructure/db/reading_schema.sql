-- Reading 模块统一建表
-- 本文件由 app.services.reading._ensure_tables() 幂等执行
-- 依据: docs/modules/reading/data-model.md + ADR 0003
--
-- 设计原则：
--   - 标注 (5 色多意图) 独立表 reading_annotations — 不能合并到 FlashCard（语义独立）
--   - 笔记 = 复用 FlashCard 反思型 (card_type=7, cross_module_source=reading_note) — 不建 reading_notes 表
--   - 回顾提醒 = 复用 PlanItem (source_module='reading') — 不建独立提醒表
--   - 4 张独立表：reading_annotations / reading_sessions / reading_comparisons / reading_prefs


-- ── 1. 标注表 reading_annotations ──
CREATE TABLE IF NOT EXISTS reading_annotations (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    material_id     TEXT NOT NULL,
    chunk_id        TEXT,                                    -- 关联 MaterialChunk
    start_offset    INT,                                     -- chunk 内起始 offset
    end_offset      INT,                                     -- chunk 内结束 offset
    color           VARCHAR(10) NOT NULL,                    -- yellow/blue/green/purple/orange
    intent          VARCHAR(20) NOT NULL,                    -- important_concept/data_fact/quotable/doubt/conflict
    text            TEXT,                                    -- 标注原文
    note            TEXT,                                    -- 用户附加文字备注
    linked_node_id  TEXT,                                    -- 关联 CognitiveNode (可选)
    is_processed    BOOLEAN DEFAULT FALSE,                   -- 是否已被提取/转卡片/转对话
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ra_user_material
    ON reading_annotations(user_id, material_id);
CREATE INDEX IF NOT EXISTS idx_ra_chunk
    ON reading_annotations(material_id, chunk_id);
CREATE INDEX IF NOT EXISTS idx_ra_color
    ON reading_annotations(user_id, color);
CREATE INDEX IF NOT EXISTS idx_ra_node
    ON reading_annotations(linked_node_id) WHERE linked_node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ra_processed
    ON reading_annotations(user_id, is_processed);


-- ── 2. 阅读会话表 reading_sessions ──
CREATE TABLE IF NOT EXISTS reading_sessions (
    id                   TEXT PRIMARY KEY,
    user_id              TEXT NOT NULL,
    material_id          TEXT NOT NULL,
    mode                 VARCHAR(20) DEFAULT 'intensive',    -- intensive / skim / review
    started_at           TIMESTAMP NOT NULL,
    ended_at             TIMESTAMP,
    duration_seconds     INT,
    chapters_visited     JSONB DEFAULT '[]'::jsonb,          -- 访问的章节列表
    annotations_created  INT DEFAULT 0,
    notes_created        INT DEFAULT 0,                      -- 实际是创建的 FlashCard 反思型数量
    cards_generated      INT DEFAULT 0,
    linked_node_ids      JSONB DEFAULT '[]'::jsonb,          -- 关联/创建的 CognitiveNode (与事件层/FlashCard/Project/LanguageRoom 命名统一)
    state_snapshot       JSONB,                              -- 中断恢复用 (最后浏览位置)
    last_active_at       TIMESTAMP
);

-- 历史字段重命名迁移 (Task #58): nodes_linked 统一为 linked_node_ids
-- 旧列已存在时改名为新列. 新装/已迁移的库报错被 _ensure_tables 静默吞掉 (幂等)
ALTER TABLE reading_sessions RENAME COLUMN nodes_linked TO linked_node_ids;

CREATE INDEX IF NOT EXISTS idx_rs_user_material
    ON reading_sessions(user_id, material_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rs_user_active
    ON reading_sessions(user_id, last_active_at DESC) WHERE ended_at IS NULL;


-- ── 3. 对比阅读表 reading_comparisons ──
CREATE TABLE IF NOT EXISTS reading_comparisons (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL,
    material_id_left    TEXT NOT NULL,
    material_id_right   TEXT NOT NULL,
    sync_scroll         BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rc_user_created
    ON reading_comparisons(user_id, created_at DESC);


-- ── 4. 阅读偏好表 reading_prefs ──
CREATE TABLE IF NOT EXISTS reading_prefs (
    user_id               TEXT PRIMARY KEY,
    default_mode          VARCHAR(20) DEFAULT 'intensive',
    highlight_mastered    BOOLEAN DEFAULT TRUE,            -- 是否高亮已掌握知识点
    highlight_weak        BOOLEAN DEFAULT TRUE,            -- 是否高亮薄弱知识点
    auto_open_sidebar     BOOLEAN DEFAULT TRUE,
    sync_scroll_default   BOOLEAN DEFAULT FALSE,
    review_reminder_days  JSONB DEFAULT '[7, 30, 90]'::jsonb,
    created_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP NOT NULL DEFAULT NOW()
);
