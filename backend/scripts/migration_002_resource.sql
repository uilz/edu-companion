-- Migration 002: Resource tables for ReadingRuntime
-- Per Contract: /vision/contracts/resource.html
-- Run: psql -U companion -d edu_companion -f migration_002_resource.sql

BEGIN;

-- resources — per Contract §6
-- Wrapper around materials with lifecycle state
CREATE TABLE IF NOT EXISTS resources (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    material_id     uuid NOT NULL,                  -- FK to materials table
    title           text NOT NULL DEFAULT '',
    state           text NOT NULL DEFAULT 'closed', -- closed | open | completed
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- reading_states — per Contract I1, I2
-- One per resource per learner. Persistent across sessions.
CREATE TABLE IF NOT EXISTS reading_states (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_id     uuid NOT NULL REFERENCES resources(id),
    user_id         uuid NOT NULL,
    position_page   int DEFAULT 0,
    position_scroll float DEFAULT 0.0,
    last_read_at    timestamptz DEFAULT now(),
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_resources_workspace ON resources(workspace_id, state);
CREATE INDEX IF NOT EXISTS idx_reading_states_resource_user ON reading_states(resource_id, user_id);

-- I1: One ReadingState per resource per learner
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_reading_state
    ON reading_states(resource_id, user_id);

COMMIT;
