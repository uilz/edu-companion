-- 事件层次系统: event_relations 表
-- 多父多子 DAG, 支持三维聚合 (mixed/topic/type) × 六时间窗口 (5m/30m/1h/day/week/month)
-- 2026-06-22

CREATE TABLE IF NOT EXISTS event_relations (
    id              TEXT PRIMARY KEY,
    parent_id       TEXT NOT NULL,
    child_id        TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(parent_id, child_id)
);

DO $$ BEGIN
    CREATE INDEX IF NOT EXISTS idx_er_parent ON event_relations(parent_id);
EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'insufficient privilege to create index idx_er_parent on event_relations';
END $$;

DO $$ BEGIN
    CREATE INDEX IF NOT EXISTS idx_er_child ON event_relations(child_id);
EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'insufficient privilege to create index idx_er_child on event_relations';
END $$;