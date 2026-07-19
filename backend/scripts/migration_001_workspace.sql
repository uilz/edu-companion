-- Migration 001: Core Tables for WorkspaceRuntime
-- Aligns existing workspaces/sessions tables with AppleGo Domain Freeze v1.1
-- Run: psql -U companion -d edu_companion -f migration_001_workspace.sql

BEGIN;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- DROP legacy tables if they exist (from earlier prototypes)
-- ============================================================
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS workspaces CASCADE;

-- ============================================================
-- workspaces — per Domain Freeze §2.1
-- ============================================================
CREATE TABLE workspaces (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     uuid NOT NULL,
    name        text NOT NULL,
    icon        text DEFAULT 'book',
    color       text DEFAULT '#5a8f6b',
    state       text NOT NULL DEFAULT 'created',
    active_session_id uuid,
    day_count   int DEFAULT 0,
    created_at  timestamptz DEFAULT now(),
    updated_at  timestamptz DEFAULT now()
);

-- ============================================================
-- sessions — per Domain Freeze §2.2
-- State machine: created → active ⇄ paused → ended
-- ============================================================
CREATE TABLE sessions (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    project_id      uuid,
    state           text NOT NULL DEFAULT 'created',
    title           text,
    mission_source  text,
    mission_text    text,
    mission_state   text DEFAULT 'active',
    last_refresh    timestamptz DEFAULT now(),
    created_at      timestamptz DEFAULT now(),
    ended_at        timestamptz
);

-- ============================================================
-- session_artifacts — per Domain Freeze §2.2
-- Snapshot of what tools/resources are open during a session
-- ============================================================
CREATE TABLE session_artifacts (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      uuid NOT NULL REFERENCES sessions(id),
    artifact_type   text NOT NULL,
    artifact_id     uuid NOT NULL,
    position        jsonb
);

-- ============================================================
-- projects — per Domain Freeze §2.1
-- ============================================================
CREATE TABLE projects (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    name            text NOT NULL,
    state           text DEFAULT 'active',
    created_at      timestamptz DEFAULT now()
);

-- ============================================================
-- learning_events — per Domain Freeze §6 (event bus store)
-- ============================================================
CREATE TABLE learning_events (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      text NOT NULL,
    aggregate_id    uuid NOT NULL,
    payload         jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz DEFAULT now()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_sessions_workspace ON sessions(workspace_id, state);
CREATE INDEX idx_sessions_state ON sessions(state);
CREATE INDEX idx_learning_events_type ON learning_events(event_type, created_at);
CREATE INDEX idx_session_artifacts_session ON session_artifacts(session_id);

-- Guarantees Invariant I3: only one active session per workspace
CREATE UNIQUE INDEX idx_one_active_session
    ON sessions(workspace_id) WHERE state = 'active';

COMMIT;
