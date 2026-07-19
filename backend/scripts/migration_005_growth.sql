-- Migration 005: Growth tables for GrowthEngine
-- Per Contract: /vision/contracts/growth.html
BEGIN;

CREATE TABLE IF NOT EXISTS milestones (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    user_id         uuid NOT NULL,
    type            text NOT NULL DEFAULT '',        -- concept_first | breakthrough | completion | habit
    title           text DEFAULT '',
    description     text DEFAULT '',
    concept_id      text DEFAULT '',                  -- related concept
    day_number      int DEFAULT 0,
    evidence_event  text DEFAULT '',                  -- the event ID that triggered this
    detected_at     timestamptz DEFAULT now(),
    created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evolution_snapshots (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    day_number      int NOT NULL DEFAULT 0,
    session_count   int DEFAULT 0,
    concept_count   int DEFAULT 0,                    -- total concepts engaged
    connection_count int DEFAULT 0,                   -- cross-concept connections
    top_concepts    text DEFAULT '',                  -- JSON: [{concept_id, depth}]
    milestone_ids   text DEFAULT '',                  -- JSON: [milestone_ids]
    created_at      timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_milestones_workspace ON milestones(workspace_id, detected_at);
CREATE INDEX IF NOT EXISTS idx_milestones_user ON milestones(user_id, day_number);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_snapshot_per_day
    ON evolution_snapshots(workspace_id, day_number);

COMMIT;
