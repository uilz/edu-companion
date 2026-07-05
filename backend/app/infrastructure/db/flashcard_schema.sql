-- FlashCard 模块统一建表
-- 本文件由 flashcard_service._ensure_tables() 幂等执行
-- 依据: docs/modules/flashcard/data-model.md

-- ── 1. 卡片主表 flashcards ──
CREATE TABLE IF NOT EXISTS flashcards (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    type            SMALLINT NOT NULL,                          -- 1-7
    source          VARCHAR(30) NOT NULL,                       -- manual/practice_error/reading_note/conversation/project/language_room/interest_explorer
    front_text      TEXT NOT NULL,
    back_text       TEXT,
    back_context    TEXT,
    language        VARCHAR(20),

    -- 来源追溯
    source_ref      JSONB DEFAULT '{}'::jsonb,

    -- 状态
    status          VARCHAR(20) DEFAULT 'pending',              -- pending / later / processing / completed / suspended / archived
    suspended_at    TIMESTAMP,
    is_resolved     BOOLEAN DEFAULT FALSE,

    -- FSRS 调度参数（每张卡独立）
    stability           DOUBLE PRECISION,                       -- FSRS 稳定性
    difficulty          DOUBLE PRECISION,                       -- FSRS 难度
    forgetting_rate     DOUBLE PRECISION,                       -- 遗忘速率
    last_review_at      TIMESTAMP,
    next_review_at      TIMESTAMP,
    review_count        INT DEFAULT 0,
    lapse_count         INT DEFAULT 0,                          -- 失败次数（"困难"次数）
    target_retention    DOUBLE PRECISION DEFAULT 0.85,          -- 用户设定的目标保留率

    -- 关联
    linked_node_ids     JSONB DEFAULT '[]'::jsonb,
    node_link_roles     JSONB DEFAULT '{}'::jsonb,
    tags                JSONB DEFAULT '[]'::jsonb,
    error_book_entry_id TEXT,

    -- 反思型附加
    response_history    JSONB DEFAULT '[]'::jsonb,

    -- 字段级粒度版本控制（参考 0001 Project 文档）
    field_versions      JSONB DEFAULT '{}'::jsonb,              -- {"front_text": 3, "tags": 2, ...}

    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMP                                 -- 软删除时间
);

CREATE INDEX IF NOT EXISTS idx_fc_user_status ON flashcards(user_id, status);
CREATE INDEX IF NOT EXISTS idx_fc_next_review ON flashcards(user_id, next_review_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_fc_source ON flashcards(user_id, source);
CREATE INDEX IF NOT EXISTS idx_fc_type ON flashcards(user_id, type);
CREATE INDEX IF NOT EXISTS idx_fc_user_created ON flashcards(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fc_tags ON flashcards USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_fc_linked_nodes ON flashcards USING gin (linked_node_ids);
CREATE INDEX IF NOT EXISTS idx_fc_error_book ON flashcards(error_book_entry_id) WHERE error_book_entry_id IS NOT NULL;


-- ── 2. 复习会话表 review_sessions ──
CREATE TABLE IF NOT EXISTS review_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    ended_at        TIMESTAMP,
    card_count      INT DEFAULT 0,
    difficult_count INT DEFAULT 0,
    good_count      INT DEFAULT 0,
    easy_count      INT DEFAULT 0,
    duration_seconds INT,
    source_module   VARCHAR(30)                                -- manual / plan_item
);

CREATE INDEX IF NOT EXISTS idx_rsessions_user ON review_sessions(user_id, started_at DESC);


-- ── 3. 复习历史表 review_history ──
CREATE TABLE IF NOT EXISTS review_history (
    id                  TEXT PRIMARY KEY,
    card_id             TEXT NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    session_id          TEXT REFERENCES review_sessions(id) ON DELETE SET NULL,
    user_id             TEXT NOT NULL,
    self_assessment     VARCHAR(10) NOT NULL,                  -- difficult / good / easy
    stability_before    DOUBLE PRECISION,
    stability_after     DOUBLE PRECISION,
    difficulty_before   DOUBLE PRECISION,
    difficulty_after    DOUBLE PRECISION,
    interval_before     INT,                                    -- 复习间隔（天）
    interval_after      INT,
    elapsed_days        INT,
    reviewed_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rhistory_card ON review_history(card_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_rhistory_session ON review_history(session_id);
CREATE INDEX IF NOT EXISTS idx_rhistory_user ON review_history(user_id, reviewed_at DESC);


-- ── 4. 标签表 flashcard_tags ──
CREATE TABLE IF NOT EXISTS flashcard_tags (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    name        VARCHAR(128) NOT NULL,
    parent_id   TEXT REFERENCES flashcard_tags(id) ON DELETE CASCADE,
    level       SMALLINT NOT NULL DEFAULT 0,                   -- 0/1/2 三层
    color       VARCHAR(7),                                    -- UI 配色（可选）
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fctags_user_parent ON flashcard_tags(user_id, parent_id);
