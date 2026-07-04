-- 秘书系统统一建表
-- 本文件由 app.infrastructure.db.secretary_schema._ensure_tables() 幂等执行，所有表用 IF NOT EXISTS
--
-- 核心表：
--   secretary_proposals  — 提案主表 (含 status/priority/metadata/decision_log)
--   mood_stress_prefs    — 心情压力偏好 (D16 决策保留为独立表)
--   emotion_records      — 情绪/压力/能量记录 (manual + auto)
--   mood_stress_intervention_logs — 干预工具日志
--   mood_stress_rules    — 用户自定义规则
--   behavior_signals     — 行为信号 (7 种类型)

-- 7.1.1 secretary_proposals 提案主表
CREATE TABLE IF NOT EXISTS secretary_proposals (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    session_id      TEXT,
    emoji           TEXT DEFAULT '💡',
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    action_type     TEXT NOT NULL,
    payload         JSONB DEFAULT '{}'::jsonb,
    priority        INTEGER DEFAULT 3,
    generated_by    TEXT DEFAULT '',
    overrideable    BOOLEAN DEFAULT TRUE,
    status          TEXT DEFAULT 'pending',
    metadata        JSONB DEFAULT '{}'::jsonb,
    snoozed_until   TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_secretary_proposals_user_status
    ON secretary_proposals (user_id, status);
CREATE INDEX IF NOT EXISTS idx_secretary_proposals_user_created
    ON secretary_proposals (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_secretary_proposals_priority
    ON secretary_proposals (user_id, priority DESC, created_at DESC) WHERE status = 'pending';

-- 7.1.2 mood_stress_prefs 心情压力偏好
CREATE TABLE IF NOT EXISTS mood_stress_prefs (
    user_id         TEXT PRIMARY KEY,
    reminder_enabled            BOOLEAN DEFAULT FALSE,
    reminder_frequency          VARCHAR(50),
    reminder_time               VARCHAR(50),
    data_retention_days         INT DEFAULT 90,
    auto_collect_task_switch    BOOLEAN DEFAULT TRUE,
    auto_collect_stay_duration  BOOLEAN DEFAULT TRUE,
    auto_collect_error_rate     BOOLEAN DEFAULT TRUE,
    auto_collect_undo           BOOLEAN DEFAULT TRUE,
    auto_collect_session_anomaly BOOLEAN DEFAULT TRUE,
    auto_collect_flashcard_failure BOOLEAN DEFAULT TRUE,
    auto_collect_voice_features BOOLEAN DEFAULT FALSE,
    output_to_planning          BOOLEAN DEFAULT TRUE,
    output_to_conversation      BOOLEAN DEFAULT TRUE,
    output_to_language_room     BOOLEAN DEFAULT TRUE,
    knowledge_breathing_excluded_node_ids JSONB DEFAULT '[]'::jsonb,
    environment_theme           VARCHAR(50) DEFAULT 'default',
    environment_sound           VARCHAR(50) DEFAULT 'none',
    planning_rules              JSONB DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- 7.1.3 emotion_records 情绪记录
CREATE TABLE IF NOT EXISTS emotion_records (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    source          VARCHAR(10) NOT NULL,  -- manual/auto
    emotion_tags    JSONB DEFAULT '[]'::jsonb,
    pressure_score  INT,
    energy_score    INT,
    text_note       TEXT,
    related_event_ids JSONB DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emotion_records_user_created
    ON emotion_records (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emotion_records_user_source
    ON emotion_records (user_id, source, created_at DESC);

-- 7.1.4 mood_stress_intervention_logs 干预日志
CREATE TABLE IF NOT EXISTS mood_stress_intervention_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    intervention_type VARCHAR(50) NOT NULL,
    duration_seconds INT,
    trigger_event   TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mood_stress_intervention_user_created
    ON mood_stress_intervention_logs (user_id, created_at DESC);

-- 7.1.5 mood_stress_rules 规则
CREATE TABLE IF NOT EXISTS mood_stress_rules (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    rule_name       VARCHAR(64) NOT NULL,
    trigger_metric  VARCHAR(50) NOT NULL,
    trigger_operator VARCHAR(10) NOT NULL,
    trigger_value   JSONB,
    action          VARCHAR(50) NOT NULL,
    is_enabled      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mood_stress_rules_user
    ON mood_stress_rules (user_id, is_enabled);

-- 7.1.6 behavior_signals 行为信号
CREATE TABLE IF NOT EXISTS behavior_signals (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    signal_type     VARCHAR(50) NOT NULL,
    signal_data     JSONB DEFAULT '{}'::jsonb,
    severity        INT DEFAULT 1,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_behavior_signals_user_unread
    ON behavior_signals (user_id, is_read, created_at DESC);
