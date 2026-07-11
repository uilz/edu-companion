-- Planning 模块统一建表（ADR 0006）
-- 本文件由 app.services.planning._ensure_tables() 幂等执行
-- 包含 6 张表：plan_items / plan_view_layouts / plan_goals / plan_periodic_reviews / plan_drafts / plan_deviations

-- 1. 计划项
CREATE TABLE IF NOT EXISTS plan_items (
    id                       TEXT PRIMARY KEY,
    user_id                  TEXT NOT NULL,
    source_module            VARCHAR(30) NOT NULL,           -- flashcard/practice/project/reading/language_room/manual
    target_type              VARCHAR(30) NOT NULL,           -- flashcard_set/practice_set/project_node/material/scenario/manual
    target_ref_id            TEXT NOT NULL,
    title                    TEXT NOT NULL,
    description              TEXT DEFAULT '',
    estimated_minutes        INT DEFAULT 0,
    actual_minutes           INT,
    linked_node_ids          JSONB DEFAULT '[]'::jsonb,
    priority                 SMALLINT DEFAULT 0,
    is_mood_rule_affected    BOOLEAN DEFAULT FALSE,
    status                   VARCHAR(20) DEFAULT 'pending',  -- pending/scheduled/in_progress/completed/skipped/extended
    scheduled_for            TIMESTAMPTZ,
    started_at               TIMESTAMPTZ,
    completed_at             TIMESTAMPTZ,
    skipped_at               TIMESTAMPTZ,
    plan_date                DATE,
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_items_user_date
    ON plan_items(user_id, plan_date);
CREATE INDEX IF NOT EXISTS idx_plan_items_status
    ON plan_items(user_id, status);
CREATE INDEX IF NOT EXISTS idx_plan_items_source
    ON plan_items(user_id, source_module);
CREATE INDEX IF NOT EXISTS idx_plan_items_user_scheduled
    ON plan_items(user_id, scheduled_for);

ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_plan_items_metadata_request_id
    ON plan_items((metadata->>'request_id'));


-- 2. 计划项确认请求（pending confirmation）
CREATE TABLE IF NOT EXISTS plan_item_confirmations (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    request_id      TEXT NOT NULL,
    suggestion_id   TEXT,
    source_module   VARCHAR(30) NOT NULL DEFAULT 'secretary',
    target_type     VARCHAR(30) NOT NULL,
    target_ref_id   TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    priority        SMALLINT DEFAULT 0,
    estimated_minutes INT DEFAULT 10,
    linked_node_ids JSONB DEFAULT '[]'::jsonb,
    proposed_scheduled_for TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'pending',
    expires_at      TIMESTAMPTZ,
    accepted_at     TIMESTAMPTZ,
    dismissed_at    TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_item_confirmations_user_status
    ON plan_item_confirmations(user_id, status);
CREATE INDEX IF NOT EXISTS idx_plan_item_confirmations_request_id
    ON plan_item_confirmations(user_id, request_id);
CREATE INDEX IF NOT EXISTS idx_plan_item_confirmations_suggestion_id
    ON plan_item_confirmations(user_id, suggestion_id);


-- 3. 自定义视图方案
CREATE TABLE IF NOT EXISTS plan_view_layouts (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    view_type    VARCHAR(20) NOT NULL,                     -- day / week / knowledge / custom
    filters      JSONB NOT NULL DEFAULT '{}'::jsonb,
    layout       JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_default   BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_view_layouts_user
    ON plan_view_layouts(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_view_layouts_user_default
    ON plan_view_layouts(user_id) WHERE is_default = TRUE;


-- 4. 目标
CREATE TABLE IF NOT EXISTS plan_goals (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    target_module   VARCHAR(30) NOT NULL,                  -- project/flashcard/practice/reading/language_room
    target_metric   VARCHAR(30) NOT NULL,                  -- node_count/card_count/practice_count/duration_minutes
    target_value    INT NOT NULL,
    current_value   INT DEFAULT 0,                         -- 由模块数据自动更新
    deadline        DATE,
    status          VARCHAR(20) DEFAULT 'active',          -- active / completed / abandoned
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_goals_user_status
    ON plan_goals(user_id, status);
CREATE INDEX IF NOT EXISTS idx_plan_goals_deadline_active
    ON plan_goals(user_id, deadline) WHERE status = 'active';


-- 5. 周期回顾
CREATE TABLE IF NOT EXISTS plan_periodic_reviews (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    period_type     VARCHAR(20) NOT NULL,                  -- weekly / monthly
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    summary_data    JSONB NOT NULL DEFAULT '{}'::jsonb,
    user_note       TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_reviews_user_period
    ON plan_periodic_reviews(user_id, period_start DESC);


-- 6. 计划草稿
CREATE TABLE IF NOT EXISTS plan_drafts (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    plan_date    DATE NOT NULL,
    draft_data   JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_saved     BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_drafts_user_date
    ON plan_drafts(user_id, plan_date);


-- 7. 偏差记录
CREATE TABLE IF NOT EXISTS plan_deviations (
    id                 TEXT PRIMARY KEY,
    plan_item_id       TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    user_id            TEXT NOT NULL,
    deviation_type     VARCHAR(20) NOT NULL,                -- timeout / skip / early_complete / extra_insert
    planned_minutes    INT,
    actual_minutes     INT,
    deviation_minutes  INT,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_deviations_item
    ON plan_deviations(plan_item_id);
CREATE INDEX IF NOT EXISTS idx_plan_deviations_user_time
    ON plan_deviations(user_id, created_at DESC);
