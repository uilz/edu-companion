-- 智能题库系统 — 新增表
-- 遵循现有系统规范：TEXT PK、无外键约束、JSONB 灵活字段

-- 7.0.1 题库表
CREATE TABLE IF NOT EXISTS question_banks (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT DEFAULT '',
    import_source   VARCHAR(50) DEFAULT 'manual',
    ref_node_id     TEXT,
    ref_node_level  VARCHAR(20),
    auto_created    BOOLEAN DEFAULT false,
    question_count  INT DEFAULT 0,
    preferences     JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

-- 7.0.2 题目表
CREATE TABLE IF NOT EXISTS questions (
    id              TEXT PRIMARY KEY,
    bank_id         TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    question_type   VARCHAR(20) NOT NULL,
    stem            TEXT NOT NULL,
    options         JSONB DEFAULT '[]',
    answer          JSONB NOT NULL,
    analysis        TEXT DEFAULT '',
    difficulty      INT DEFAULT 3,
    cognitive_node_ids TEXT[] DEFAULT '{}',
    source          VARCHAR(20) DEFAULT 'manual',
    is_favorite     BOOLEAN DEFAULT false,
    is_slashed      BOOLEAN DEFAULT false,
    status          VARCHAR(20) DEFAULT 'active',
    source_line     INT,
    import_errors   JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_v7q_bank ON questions(bank_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_v7q_cognitive ON questions USING GIN(cognitive_node_ids);
CREATE INDEX IF NOT EXISTS idx_v7q_type ON questions(question_type);

-- 7.0.3 练习会话表
CREATE TABLE IF NOT EXISTS practice_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    bank_id         TEXT,
    session_type    VARCHAR(20) NOT NULL DEFAULT 'practice',
    mode            VARCHAR(20) NOT NULL DEFAULT 'adaptive',
    config          JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'created',
    total_count     INT NOT NULL,
    correct_count   INT DEFAULT 0,
    wrong_count     INT DEFAULT 0,
    score           DOUBLE PRECISION,
    cognitive_node_ids TEXT[] DEFAULT '{}',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    duration_seconds INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 7.0.4 会话题目关联表
CREATE TABLE IF NOT EXISTS session_questions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    user_answer     JSONB,
    is_correct      BOOLEAN,
    time_spent_seconds INT DEFAULT 0,
    hints_used      INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_v7sq_session ON session_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_v7sq_question ON session_questions(question_id);

-- 7.0.5 答题记录表
CREATE TABLE IF NOT EXISTS practice_attempts (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL,
    question_id         TEXT NOT NULL,
    user_id             TEXT NOT NULL,
    user_answer         JSONB,
    is_correct          BOOLEAN,
    time_spent_seconds  INT DEFAULT 0,
    is_wrong            BOOLEAN DEFAULT false,
    wrong_count         INT DEFAULT 0,
    consecutive_correct INT DEFAULT 0,
    mastered            BOOLEAN DEFAULT false,
    cognitive_node_ids  TEXT[] DEFAULT '{}',
    error_pattern       VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_v7pa_session ON practice_attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_pa_user_q ON practice_attempts(user_id, question_id);
CREATE INDEX IF NOT EXISTS idx_pa_wrong ON practice_attempts(user_id) WHERE is_wrong = true;

-- 7.0.6 收藏表
CREATE TABLE IF NOT EXISTS question_favorites (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qf_user_q ON question_favorites(user_id, question_id);

-- 7.0.7 斩题记录表
CREATE TABLE IF NOT EXISTS slashed_questions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    slashed_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sq_user_q ON slashed_questions(user_id, question_id);
