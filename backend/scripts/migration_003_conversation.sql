-- Migration 003: Conversation tables for ConversationRuntime
-- Uses 'conv_' prefix to avoid conflict with existing conversations table
-- Per Contract: /vision/contracts/conversation.html
BEGIN;

CREATE TABLE IF NOT EXISTS conv_conversations (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      uuid NOT NULL REFERENCES sessions(id),
    state           text NOT NULL DEFAULT 'created',
    title           text DEFAULT '',
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS context_snapshots (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id uuid REFERENCES conv_conversations(id),
    reading_page    int DEFAULT 0,
    reading_scroll  float DEFAULT 0.0,
    memory_tier     text DEFAULT '',
    knowledge_concepts text DEFAULT '',
    captured_at     timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS turns (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id uuid NOT NULL REFERENCES conv_conversations(id),
    seq             int NOT NULL DEFAULT 1,
    user_message    text DEFAULT '',
    ai_response     text DEFAULT '',
    context_snapshot_id uuid REFERENCES context_snapshots(id),
    orchestration   text DEFAULT '',
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conv_convs_session ON conv_conversations(session_id, state);
CREATE INDEX IF NOT EXISTS idx_turns_conv ON turns(conversation_id, seq);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_conv
    ON conv_conversations(session_id) WHERE state = 'active';

COMMIT;
