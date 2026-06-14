-- Events 表 — 通用事件记录
-- 取代旧 cognitive_events 表, 独立于 cognitive 模块
-- 多个模块 (cognitive/secretary/practice) 共用

CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    event_type      TEXT NOT NULL,          -- "cognitive_update" | 未来扩展
    source_type     TEXT NOT NULL,          -- "conversation" | "practice" | "secretary" | "manual" | "system"
    source_id       TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'done',  -- pending | processing | done | failed
    status_msg      TEXT NOT NULL DEFAULT '',
    payload         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_ats     TIMESTAMPTZ[] DEFAULT ARRAY[NOW()]  -- status 变更追加
);

CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status, created_at) WHERE status = 'pending';
