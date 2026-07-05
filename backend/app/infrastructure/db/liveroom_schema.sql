-- LanguageRoom 模块统一建表
-- 本文件由 app.services.liveroom._ensure_tables() 幂等执行
-- 依据: docs/modules/language-room/data-model.md + ADR 0004
--
-- 设计原则：
--   - 数据归属 = 参与者各自存 (决策 1)
--   - 房间可见性 = 邀请制 (无 is_public 字段) (决策 2)
--   - 场景与项目平行 (决策 9)
--   - 录音可选 (决策 10)
--   - 转写数据各自分开 (决策 11)
--   - 词汇便签复用 FlashCard 数据卡 (data-model §9)
--   - 错误标记复用 ErrorBookEntry (不新建)
--   - 文字辅助复用 ExplainCard (不新建)
--   - 10 张独立表


-- ── 1. 房间主表 language_rooms ──
CREATE TABLE IF NOT EXISTS language_rooms (
    id                      TEXT PRIMARY KEY,
    owner_id                TEXT NOT NULL,                    -- 房主 user_id
    name                    TEXT NOT NULL,
    scenario_id             TEXT,                              -- 关联 room_scenarios
    room_type               VARCHAR(20) NOT NULL,             -- 1v1 / small / medium / large
    max_participants        INT DEFAULT 2,
    is_recording_enabled    BOOLEAN DEFAULT FALSE,
    is_transcript_enabled   BOOLEAN DEFAULT TRUE,
    ai_intrusion_level      VARCHAR(10) DEFAULT 'low',        -- low / medium / high
    status                  VARCHAR(20) DEFAULT 'active',     -- active / ended
    started_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at                TIMESTAMP,
    settings                JSONB DEFAULT '{}'::jsonb,        -- 房间级设置
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lr_owner
    ON language_rooms(owner_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_lr_status
    ON language_rooms(status);
CREATE INDEX IF NOT EXISTS idx_lr_scenario
    ON language_rooms(scenario_id) WHERE scenario_id IS NOT NULL;


-- ── 2. 参与者表 room_participants ──
CREATE TABLE IF NOT EXISTS room_participants (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 真人或 AI 角色 ID
    participant_type        VARCHAR(20) NOT NULL,             -- human / ai_companion / ai_assistant
    ai_role_id              TEXT,                              -- 关联 ai_personas (如果是 AI)
    role_label              VARCHAR(50),                       -- 场景中角色名 ("咖啡师")
    language                VARCHAR(20),                       -- 参与语种
    joined_at               TIMESTAMP NOT NULL DEFAULT NOW(),
    left_at                 TIMESTAMP,
    speaking_time_seconds   INT DEFAULT 0,
    is_muted                BOOLEAN DEFAULT FALSE,
    is_owner                BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_room
    ON room_participants(room_id);
CREATE INDEX IF NOT EXISTS idx_rp_user
    ON room_participants(user_id, joined_at DESC);
CREATE INDEX IF NOT EXISTS idx_rp_active
    ON room_participants(room_id) WHERE left_at IS NULL;


-- ── 3. 会话表 room_sessions ──
-- 每个参与者各一份 (决策 1)
CREATE TABLE IF NOT EXISTS room_sessions (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 该会话归属用户
    participant_id          TEXT NOT NULL,                    -- 关联 room_participants
    started_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at                TIMESTAMP,
    duration_seconds        INT,
    transcript_count        INT DEFAULT 0,                    -- 该用户转写段数
    errors_marked           INT DEFAULT 0,                    -- 该用户标记错误数
    cards_generated         INT DEFAULT 0,                    -- 该用户生成卡片数
    ai_help_requests        INT DEFAULT 0,                    -- 该用户召唤 AI 辅助者次数
    vocabulary_captured     INT DEFAULT 0,                    -- 该用户词汇便签数
    messages_posted         INT DEFAULT 0,                    -- 该用户文字辅助区数
    linked_node_ids         JSONB DEFAULT '[]'::jsonb,         -- 关联知识点
    session_metadata        JSONB DEFAULT '{}'::jsonb,         -- 扩展元数据
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rs_room
    ON room_sessions(room_id);
CREATE INDEX IF NOT EXISTS idx_rs_user
    ON room_sessions(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rs_user_active
    ON room_sessions(user_id) WHERE ended_at IS NULL;


-- ── 4. 转写片段表 room_transcripts ──
-- 按参与者各自存储 (决策 1 + 决策 11)
CREATE TABLE IF NOT EXISTS room_transcripts (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    participant_id          TEXT NOT NULL REFERENCES room_participants(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 转写归属用户
    segment_index           INT NOT NULL,
    text                    TEXT NOT NULL,
    language                VARCHAR(20),
    started_at              TIMESTAMP NOT NULL,
    ended_at                TIMESTAMP NOT NULL,
    confidence              DOUBLE PRECISION,
    speaker_id              TEXT,                              -- 实际说话者
    speaker_name            VARCHAR(100),
    is_user_marked          BOOLEAN DEFAULT FALSE,            -- 用户是否手动标记
    user_note               TEXT,
    is_error                BOOLEAN DEFAULT FALSE,            -- 标记为错误
    error_entry_id          TEXT,                              -- 关联 ErrorBookEntry.id
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rt_room
    ON room_transcripts(room_id, started_at);
CREATE INDEX IF NOT EXISTS idx_rt_user
    ON room_transcripts(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rt_error
    ON room_transcripts(user_id) WHERE is_error = TRUE;
CREATE INDEX IF NOT EXISTS idx_rt_participant
    ON room_transcripts(participant_id, segment_index);


-- ── 5. 场景表 room_scenarios ──
CREATE TABLE IF NOT EXISTS room_scenarios (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT,                              -- NULL = 系统预置
    name                    TEXT NOT NULL,
    description             TEXT,
    category                VARCHAR(50),                       -- 日常 / 学术 / 商务
    roles                   JSONB DEFAULT '[]'::jsonb,         -- 角色列表
    target_goals            JSONB DEFAULT '[]'::jsonb,         -- 目标任务列表
    prompt_text             TEXT,                              -- 浮动提示词
    linked_node_ids         JSONB DEFAULT '[]'::jsonb,         -- 关联 CognitiveNode
    cross_disciplinary      BOOLEAN DEFAULT FALSE,             -- 是否允许跨学科
    is_system               BOOLEAN DEFAULT FALSE,             -- 系统预置 / 用户自建
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rsc_user
    ON room_scenarios(user_id);
CREATE INDEX IF NOT EXISTS idx_rsc_category
    ON room_scenarios(category);
CREATE INDEX IF NOT EXISTS idx_rsc_system
    ON room_scenarios(is_system);


-- ── 6. AI 角色表 ai_personas ──
CREATE TABLE IF NOT EXISTS ai_personas (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT,                              -- NULL = 系统预置
    name                    TEXT NOT NULL,
    gender_voice            VARCHAR(20),
    personality             TEXT,                              -- 性格描述
    target_language         VARCHAR(20),
    proficiency             VARCHAR(20),                       -- beginner/intermediate/advanced/native
    speech_rate             VARCHAR(20),                       -- slow/normal/fast
    accent                  VARCHAR(50),
    behavior                VARCHAR(20),                       -- talkative/concise
    correction_tendency     VARCHAR(20) DEFAULT 'none',        -- none/occasional/proactive
    is_topic_lead           BOOLEAN DEFAULT FALSE,             -- 是否主动引导话题
    is_system               BOOLEAN DEFAULT FALSE,
    background              TEXT,                              -- 角色背景
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ap_user
    ON ai_personas(user_id);
CREATE INDEX IF NOT EXISTS idx_ap_system
    ON ai_personas(is_system);
CREATE INDEX IF NOT EXISTS idx_ap_lang
    ON ai_personas(target_language);


-- ── 7. AI 同伴配置表 ai_companion_configs ──
-- 房间级 AI 同伴行为配置
CREATE TABLE IF NOT EXISTS ai_companion_configs (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    participant_id          TEXT NOT NULL REFERENCES room_participants(id) ON DELETE CASCADE,
    persona_id              TEXT NOT NULL REFERENCES ai_personas(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 该配置所属用户
    correction_tendency     VARCHAR(20) DEFAULT 'none',        -- 用户选择
    is_topic_lead           BOOLEAN DEFAULT FALSE,
    response_style          VARCHAR(20) DEFAULT 'balanced',    -- formal/balanced/casual
    max_response_length     INT DEFAULT 200,
    activated_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    deactivated_at          TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_acc_room
    ON ai_companion_configs(room_id);
CREATE INDEX IF NOT EXISTS idx_acc_user
    ON ai_companion_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_acc_participant
    ON ai_companion_configs(participant_id);


-- ── 8. AI 辅助者侵入度配置表 ai_helper_invasiveness ──
-- 用户级侵入度配置 (决策: 房主无法为他人的 AI 行为做设置)
CREATE TABLE IF NOT EXISTS ai_helper_invasiveness (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    invasiveness_level      VARCHAR(10) DEFAULT 'low',         -- low/medium/high
    helper_types            JSONB DEFAULT '["grammar","vocabulary","sentence_pattern"]'::jsonb,
    correction_tendency     VARCHAR(20) DEFAULT 'none',        -- 用户主动选择 (决策 6)
    response_style          VARCHAR(20) DEFAULT 'concise',
    show_to_room            BOOLEAN DEFAULT FALSE,             -- 始终仅个人侧边区可见
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ahi_user_room
    ON ai_helper_invasiveness(user_id, room_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ahi_user_room
    ON ai_helper_invasiveness(user_id, room_id);


-- ── 9. 录音文件表 room_recordings ──
-- 可选存储 (决策 10)
CREATE TABLE IF NOT EXISTS room_recordings (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 录音归属用户
    storage_path            TEXT NOT NULL,                    -- 文件路径
    file_size_bytes         BIGINT,
    duration_seconds        INT,
    started_at              TIMESTAMP NOT NULL,
    ended_at                TIMESTAMP NOT NULL,
    format                  VARCHAR(10) DEFAULT 'opus',       -- 音频格式
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rr_room
    ON room_recordings(room_id);
CREATE INDEX IF NOT EXISTS idx_rr_user
    ON room_recordings(user_id, started_at DESC);


-- ── 10. 词汇便签表 vocabulary_captures ──
-- 复用 FlashCard 数据卡 (cross_module_source='language_room') 软链接
CREATE TABLE IF NOT EXISTS vocabulary_captures (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL,                    -- 词汇归属用户
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    transcript_id           TEXT REFERENCES room_transcripts(id) ON DELETE SET NULL,
    card_id                 TEXT,                              -- 关联 FlashCard.id (类型=data)
    word                    TEXT NOT NULL,
    translation             TEXT,
    context_sentence        TEXT,
    language                VARCHAR(20),
    captured_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vc_user
    ON vocabulary_captures(user_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_vc_room
    ON vocabulary_captures(room_id);
CREATE INDEX IF NOT EXISTS idx_vc_card
    ON vocabulary_captures(card_id) WHERE card_id IS NOT NULL;


-- ── 11. 房间邀请表 room_invitations ──
-- 邀请制 (决策 2 - 不设公开房间)
CREATE TABLE IF NOT EXISTS room_invitations (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    inviter_id              TEXT NOT NULL,
    invitee_id              TEXT,                              -- NULL = 邀请链接
    invitation_token        TEXT NOT NULL,
    is_used                 BOOLEAN DEFAULT FALSE,
    expires_at              TIMESTAMP,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ri_room
    ON room_invitations(room_id);
CREATE INDEX IF NOT EXISTS idx_ri_token
    ON room_invitations(invitation_token);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ri_token
    ON room_invitations(invitation_token);
