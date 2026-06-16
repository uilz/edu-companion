-- 练习系统统一建表 (v2 重构版)
-- 取代: question_bank.sql + database.py 内联建表 + 各文件内联 _ensure_tables()
-- 注意: 本文件由 _ensure_tables() 幂等执行，所有表用 IF NOT EXISTS

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

-- 7.0.2 题目表 (v2: 砍 skill_id → cognitive_links, 砍 correct_answer → options[].is_correct, 砍 cognitive_node_ids → cognitive_links)
CREATE TABLE IF NOT EXISTS questions (
    id              TEXT PRIMARY KEY,
    bank_id         TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    question_type   VARCHAR(20) NOT NULL,       -- single/multiple/judge/fill/free_form/calculation
    stem            TEXT NOT NULL,
    options         JSONB DEFAULT '[]',          -- [{letter, text, is_correct, distractor_type}, ...]
    answer          JSONB NOT NULL,              -- 冗余缓存: options[] 中 is_correct=true 的 letter
    explanation     TEXT DEFAULT '',             -- 解析
    hints           JSONB DEFAULT '[]',          -- 渐进提示
    difficulty      INT DEFAULT 3,               -- 1~5
    source          VARCHAR(20) DEFAULT 'manual', -- llm/manual/imported/material
    is_favorite     BOOLEAN DEFAULT false,       -- 待迁移至 question_user_flags
    is_slashed      BOOLEAN DEFAULT false,       -- 待迁移至 question_user_flags
    status          VARCHAR(20) DEFAULT 'active',
    source_line     INT,
    import_errors   JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',          -- bloom_level, subject, hints, tags, skill_id(历史), etc.
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

-- 迁移: 为已存在的表补充新列（开发阶段幂等执行）
ALTER TABLE practice_attempts ADD COLUMN IF NOT EXISTS error_analysis JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_q_bank ON questions(bank_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_q_type ON questions(question_type);

-- 7.0.3 练习会话表 (v2: 砍 question_ids_json → session_questions, 保留 correct/wrong/score 为统计缓存)
CREATE TABLE IF NOT EXISTS practice_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    bank_id         TEXT,
    session_type    VARCHAR(20) NOT NULL DEFAULT 'practice',  -- practice/exam
    mode            VARCHAR(20) NOT NULL DEFAULT 'adaptive',  -- adaptive/review/challenge/exam
    config          JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'created',   -- created/started/paused/completed/cancelled
    total_count     INT NOT NULL,
    correct_count   INT DEFAULT 0,
    wrong_count     INT DEFAULT 0,
    score           DOUBLE PRECISION,
    cognitive_node_ids TEXT[] DEFAULT '{}',       -- 待迁移至 cognitive_links
    conversation_id TEXT DEFAULT '',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    duration_seconds INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 7.0.4 会话题目关联表 (v2: 无状态化, 仅保留排序和元数据, 答题状态从 practice_attempts 聚合)
CREATE TABLE IF NOT EXISTS session_questions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    question_type   VARCHAR(20) DEFAULT '',
    bloom_level     VARCHAR(20) DEFAULT '',
    difficulty      INT DEFAULT 3,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sq_session ON session_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_sq_question ON session_questions(question_id);

-- 7.0.5 答题记录表 (唯一主表, 取代 attempts 表)
CREATE TABLE IF NOT EXISTS practice_attempts (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL,
    question_id         TEXT NOT NULL,
    user_id             TEXT NOT NULL,
    user_answer         JSONB,
    is_correct          BOOLEAN,
    time_spent_seconds  INT DEFAULT 0,
    is_wrong            BOOLEAN DEFAULT false,
    wrong_count         INT DEFAULT 0,           -- 该题累计错误次数
    consecutive_correct INT DEFAULT 0,           -- 该题连续正确次数 (用于判断"已掌握")
    mastered            BOOLEAN DEFAULT false,
    cognitive_node_ids  TEXT[] DEFAULT '{}',       -- 待迁移至 cognitive_links
    error_pattern       VARCHAR(50),              -- 错因分类: 概念混淆/计算失误/审题不清/...
    error_analysis      JSONB DEFAULT '{}',        -- 错因分析详细数据 (LLM 输出)
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pa_session ON practice_attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_pa_user_q ON practice_attempts(user_id, question_id);
CREATE INDEX IF NOT EXISTS idx_pa_wrong ON practice_attempts(user_id) WHERE is_wrong = true;

-- 7.0.6 用户题目标记表 (取代 question_favorites + slashed_questions)
CREATE TABLE IF NOT EXISTS question_user_flags (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    flag_type       TEXT NOT NULL,               -- 'favorite' | 'slashed'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_quf_user_q_type ON question_user_flags(user_id, question_id, flag_type);

-- 7.0.7 错题本缓存表 (从 practice_attempts 聚合写入, 只读缓存)
CREATE TABLE IF NOT EXISTS error_book (
    entry_id        TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    skill_id        TEXT DEFAULT '',             -- 待迁移至 cognitive_links
    error_type      TEXT DEFAULT '',
    misconception   TEXT DEFAULT '',
    user_answer     TEXT DEFAULT '',
    question_text   TEXT DEFAULT '',
    review_count    INT DEFAULT 0,
    next_review     TIMESTAMPTZ DEFAULT NOW(),
    mastery_after_review DOUBLE PRECISION DEFAULT 0,
    is_resolved     BOOLEAN DEFAULT false,
    consecutive_correct INT DEFAULT 0,
    referenced_materials JSONB DEFAULT '[]',
    attribution     JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eb_user ON error_book(user_id);
CREATE INDEX IF NOT EXISTS idx_eb_skill ON error_book(skill_id);
CREATE INDEX IF NOT EXISTS idx_eb_resolved ON error_book(user_id, is_resolved);

-- 7.0.8 统一关联表 (取代 cognitive_node_ids 数组 + knowledge_edges + conversation_node_links + material_chunks.skill_ids_json)
CREATE TABLE IF NOT EXISTS cognitive_links (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    source_type TEXT NOT NULL,                   -- 'question' | 'conversation' | 'material_chunk' | 'cognitive_edge'
    source_id   TEXT NOT NULL,
    node_id     TEXT NOT NULL,                   -- CognitiveNode.id
    link_type   TEXT NOT NULL,                   -- 'belongs_to' | 'prerequisite' | 'associate' | 'unlocks'
    weight      DOUBLE PRECISION DEFAULT 1.0,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cl_source ON cognitive_links(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_cl_node ON cognitive_links(node_id);
CREATE INDEX IF NOT EXISTS idx_cl_type ON cognitive_links(link_type);

-- 7.0.9 用户设置表 (取代 user_llm_configs + conversation_user_meta.secretary_prefs + policy_memory)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id         TEXT NOT NULL PRIMARY KEY,
    settings_jsonb  JSONB NOT NULL DEFAULT '{}',
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 7.0.10 消息表 (取代 conversation_user_meta.nodes/messages/response_blocks JSONB)
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    directory_id    TEXT NOT NULL,
    role            TEXT NOT NULL,               -- user | assistant | system
    content         TEXT DEFAULT '',
    content_blocks  JSONB DEFAULT '[]',          -- [TextBlock, PracticeBlock, MindMapBlock, ...]
    text_summary    TEXT DEFAULT '',
    parent_id       TEXT,
    children_ids    TEXT[] DEFAULT '{}',
    timestamp       DOUBLE PRECISION DEFAULT 0,
    token_count     INTEGER DEFAULT 0,
    version         INTEGER DEFAULT 1,
    is_deleted      BOOLEAN DEFAULT FALSE,
    agent_label     TEXT DEFAULT '',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_msg_dir ON messages(directory_id);
CREATE INDEX IF NOT EXISTS idx_msg_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_msg_parent ON messages(parent_id);
