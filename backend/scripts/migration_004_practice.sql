-- Migration 004: Practice tables for PracticeRuntime
-- Uses 'practice_' prefix to avoid conflict with existing questions table
-- Per Contract: /vision/contracts/practice.html
BEGIN;

CREATE TABLE IF NOT EXISTS practices (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    state           text NOT NULL DEFAULT 'created',
    title           text DEFAULT '',
    total_questions int DEFAULT 0,
    correct_count   int DEFAULT 0,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS practice_questions (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    practice_id     uuid NOT NULL REFERENCES practices(id),
    seq             int NOT NULL DEFAULT 1,
    text            text DEFAULT '',
    concept_ids     text DEFAULT '',
    context_source  text DEFAULT '',
    correct_answer  text DEFAULT '',
    created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS practice_attempts (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_id     uuid NOT NULL REFERENCES practice_questions(id),
    user_id         uuid NOT NULL,
    answer          text DEFAULT '',
    is_correct      boolean DEFAULT false,
    confidence      int DEFAULT 0,
    response_time_s float DEFAULT 0.0,
    reviewed        boolean DEFAULT false,
    review_comment  text DEFAULT '',
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_practices_workspace ON practices(workspace_id, state);
CREATE INDEX IF NOT EXISTS idx_pquestions_practice ON practice_questions(practice_id, seq);
CREATE INDEX IF NOT EXISTS idx_pattempts_question ON practice_attempts(question_id);
CREATE INDEX IF NOT EXISTS idx_pattempts_user ON practice_attempts(user_id, created_at);

COMMIT;
