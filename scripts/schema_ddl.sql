-- 导出时间: 2026-07-01 16:36:55
-- 包含 33 张表, 91 个索引

CREATE INDEX IF NOT EXISTS idx_ach_user ON public.achievements USING btree (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ach_user_ach ON public.achievements USING btree (user_id, ach_id, level);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_vec ON public.material_chunks USING hnsw (embedding_vec public.vector_cosine_ops) WITH (m='16', ef_construction='200');

CREATE INDEX IF NOT EXISTS idx_chunks_material ON public.material_chunks USING btree (material_id);

CREATE INDEX IF NOT EXISTS idx_cl_node ON public.cognitive_links USING btree (node_id);

CREATE INDEX IF NOT EXISTS idx_cl_source ON public.cognitive_links USING btree (source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_cl_type ON public.cognitive_links USING btree (link_type);

CREATE INDEX IF NOT EXISTS idx_cn_label ON public.knowledge_nodes USING btree (user_id, label) WHERE ((label IS NOT NULL) AND (label <> ''::text) AND (deleted_at IS NULL));

CREATE INDEX IF NOT EXISTS idx_cn_level ON public.knowledge_nodes USING btree (user_id, level) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS idx_cn_level_filtered ON public.knowledge_nodes USING btree (user_id, level) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS idx_cn_parent ON public.knowledge_nodes USING btree (user_id, parent) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS idx_cn_parent_visible ON public.knowledge_nodes USING btree (user_id, parent) WHERE (deleted_at IS NULL);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cn_path_id ON public.knowledge_nodes USING btree (user_id, path_id) WHERE ((path_id IS NOT NULL) AND (path_id <> ''::text) AND (deleted_at IS NULL));

CREATE INDEX IF NOT EXISTS idx_cn_visible ON public.knowledge_nodes USING btree (user_id, parent, is_visible) WHERE ((is_visible = true) AND (deleted_at IS NULL));

CREATE INDEX IF NOT EXISTS idx_cnl_conv ON public.conversation_node_links USING btree (conversation_id);

CREATE INDEX IF NOT EXISTS idx_cnl_node ON public.conversation_node_links USING btree (node_id);

CREATE INDEX IF NOT EXISTS idx_cog_nodes_level ON public.knowledge_nodes USING btree (level);

CREATE INDEX IF NOT EXISTS idx_cog_nodes_level_user ON public.knowledge_nodes USING btree (user_id, level);

CREATE INDEX IF NOT EXISTS idx_cog_nodes_next_review ON public.knowledge_nodes USING btree ((((scheduling ->> 'next_review'::text))::double precision)) WHERE ((scheduling ->> 'next_review'::text) IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_cog_nodes_parent ON public.knowledge_nodes USING btree (parent);

CREATE INDEX IF NOT EXISTS idx_cog_nodes_urgency ON public.knowledge_nodes USING btree ((((scheduling ->> 'urgency'::text))::double precision) DESC) WHERE ((scheduling ->> 'urgency'::text) IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_cog_nodes_user ON public.knowledge_nodes USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_conv_knowledge_nodes ON public.conversations USING gin (knowledge_node_ids);

CREATE INDEX IF NOT EXISTS idx_conv_meta_dn ON public.conversation_user_meta USING gin (directory_nodes jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_conv_parent ON public.conversations USING btree (parent_conversation_id);

CREATE INDEX IF NOT EXISTS idx_conv_user ON public.conversations USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_cs_conv ON public.conversation_summaries USING btree (conversation_id, round_number DESC);

CREATE INDEX IF NOT EXISTS idx_eb_resolved ON public.error_book USING btree (user_id, is_resolved);

CREATE INDEX IF NOT EXISTS idx_eb_skill ON public.error_book USING btree (skill_id);

CREATE INDEX IF NOT EXISTS idx_eb_user ON public.error_book USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_er_child ON public.event_relations USING btree (child_id);

CREATE INDEX IF NOT EXISTS idx_er_parent ON public.event_relations USING btree (parent_id);

CREATE INDEX IF NOT EXISTS idx_errors_user ON public.error_book USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_events_correlation ON public.events USING btree (correlation_id) WHERE (correlation_id IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_events_embedding ON public.events USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='200');

CREATE INDEX IF NOT EXISTS idx_events_importance ON public.events USING btree (user_id, importance DESC) WHERE (importance > (0.5)::double precision);

CREATE INDEX IF NOT EXISTS idx_events_parent ON public.events USING btree (parent_event_id) WHERE (parent_event_id IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_events_source ON public.events USING btree (source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_events_status ON public.events USING btree (status, created_at) WHERE (status = 'pending'::text);

CREATE INDEX IF NOT EXISTS idx_events_stream ON public.events USING btree (stream_type, stream_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_type ON public.events USING btree (event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_user ON public.events USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_goals_node ON public.learning_goals USING btree (node_id);

CREATE INDEX IF NOT EXISTS idx_goals_status ON public.learning_goals USING btree (status);

CREATE INDEX IF NOT EXISTS idx_goals_user ON public.learning_goals USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_ke_source ON public.knowledge_edges USING btree (source_node_id);

CREATE INDEX IF NOT EXISTS idx_ke_status ON public.knowledge_edges USING btree (user_id, edge_status);

CREATE INDEX IF NOT EXISTS idx_ke_target ON public.knowledge_edges USING btree (target_node_id);

CREATE INDEX IF NOT EXISTS idx_login_events_created ON public.login_events USING btree (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_login_events_ip ON public.login_events USING btree (ip_address);

CREATE INDEX IF NOT EXISTS idx_login_events_user ON public.login_events USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_materials_user ON public.materials USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_msg_conversation ON public.messages USING btree (conv_id);

CREATE INDEX IF NOT EXISTS idx_msg_parent ON public.messages USING btree (parent_id);

CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON public.messages USING btree ("timestamp");

CREATE INDEX IF NOT EXISTS idx_msg_user ON public.messages USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_nav_conversation ON public.navigation_nodes USING btree (conversation_id);

CREATE INDEX IF NOT EXISTS idx_nav_knowledge_area ON public.navigation_nodes USING btree (knowledge_area_id);

CREATE INDEX IF NOT EXISTS idx_nav_node_type ON public.navigation_nodes USING btree (node_type);

CREATE INDEX IF NOT EXISTS idx_nav_parent ON public.navigation_nodes USING btree (parent_id);

CREATE INDEX IF NOT EXISTS idx_nav_user ON public.navigation_nodes USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_notes_created ON public.user_notes USING btree (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notes_node ON public.user_notes USING gin (node_ids);

CREATE INDEX IF NOT EXISTS idx_notes_type ON public.user_notes USING btree (type);

CREATE INDEX IF NOT EXISTS idx_notes_user ON public.user_notes USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_pa_session ON public.practice_attempts USING btree (session_id);

CREATE INDEX IF NOT EXISTS idx_pa_user_q ON public.practice_attempts USING btree (user_id, question_id);

CREATE INDEX IF NOT EXISTS idx_pa_wrong ON public.practice_attempts USING btree (user_id) WHERE (is_wrong = true);

CREATE INDEX IF NOT EXISTS idx_pmq_material ON public.practice_material_questions USING btree (material_id);

CREATE INDEX IF NOT EXISTS idx_pmq_question ON public.practice_material_questions USING btree (question_id);

CREATE INDEX IF NOT EXISTS idx_projects_node ON public.exploration_projects USING gin (node_ids);

CREATE INDEX IF NOT EXISTS idx_projects_status ON public.exploration_projects USING btree (status);

CREATE INDEX IF NOT EXISTS idx_projects_user ON public.exploration_projects USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_q_bank ON public.questions USING btree (bank_id) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS idx_q_type ON public.questions USING btree (question_type);

CREATE INDEX IF NOT EXISTS idx_questions_skill ON public.questions USING btree (skill_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_quf_user_q_type ON public.question_user_flags USING btree (user_id, question_id, flag_type);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON public.practice_sessions USING btree (started_at);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON public.practice_sessions USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_sq_question ON public.session_questions USING btree (question_id);

CREATE INDEX IF NOT EXISTS idx_sq_session ON public.session_questions USING btree (session_id);

CREATE INDEX IF NOT EXISTS idx_toc_material ON public.material_toc USING btree (material_id);

CREATE INDEX IF NOT EXISTS idx_toc_parent ON public.material_toc USING btree (parent_toc_id);

CREATE INDEX IF NOT EXISTS idx_users_username ON public.users USING btree (username);

CREATE UNIQUE INDEX IF NOT EXISTS idx_v7ach_user_ach ON public.achievements USING btree (user_id, ach_id, level);

CREATE INDEX IF NOT EXISTS idx_v7pa_session ON public.practice_attempts USING btree (session_id);

CREATE INDEX IF NOT EXISTS idx_v7q_bank ON public.questions USING btree (bank_id) WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS idx_v7q_cognitive ON public.questions USING gin (cognitive_node_ids);

CREATE INDEX IF NOT EXISTS idx_v7q_type ON public.questions USING btree (question_type);

CREATE INDEX IF NOT EXISTS idx_v7sq_question ON public.session_questions USING btree (question_id);

CREATE INDEX IF NOT EXISTS idx_v7sq_session ON public.session_questions USING btree (session_id);

CREATE TABLE IF NOT EXISTS public.achievements (
    id text NOT NULL,
    user_id text NOT NULL,
    ach_id text NOT NULL,
    level integer DEFAULT 1,
    name character varying(100),
    icon character varying(10),
    tier character varying(20),
    description text,
    unlocked_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.cognitive_links (
    id text NOT NULL,
    user_id text NOT NULL,
    source_type text NOT NULL,
    source_id text NOT NULL,
    node_id text NOT NULL,
    link_type text NOT NULL,
    weight double precision DEFAULT 1.0,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.conversation_node_links (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    conversation_id character varying(255) NOT NULL,
    node_id text NOT NULL,
    added_by character varying(50) DEFAULT 'system'::character varying,
    is_primary boolean DEFAULT false,
    added_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.conversation_summaries (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    conversation_id text NOT NULL,
    user_id text NOT NULL,
    round_number integer NOT NULL,
    summary text NOT NULL,
    involved_node_ids text[] DEFAULT '{}'::text[],
    token_count integer,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.conversation_user_meta (
    user_id text NOT NULL,
    role text DEFAULT 'student'::text,
    org_id text,
    active_partition_id text,
    created_at double precision DEFAULT 0,
    knowledge_graphs jsonb DEFAULT '{}'::jsonb,
    knowledge_states jsonb DEFAULT '{}'::jsonb,
    practice_sessions jsonb DEFAULT '{}'::jsonb,
    error_book jsonb DEFAULT '{}'::jsonb,
    event_log jsonb DEFAULT '[]'::jsonb,
    domains jsonb DEFAULT '{}'::jsonb,
    topics jsonb DEFAULT '{}'::jsonb,
    files jsonb DEFAULT '{}'::jsonb,
    background_jobs jsonb DEFAULT '{}'::jsonb,
    updated_at double precision DEFAULT 0,
    domains_backup jsonb,
    topics_backup jsonb,
    secretary_prefs jsonb DEFAULT '{}'::jsonb,
    policy_memory jsonb DEFAULT '{}'::jsonb,
    partitions jsonb DEFAULT '{}'::jsonb,
    conversations jsonb DEFAULT '{}'::jsonb,
    nodes jsonb DEFAULT '{}'::jsonb,
    link_nodes jsonb DEFAULT '{}'::jsonb,
    response_blocks jsonb DEFAULT '{}'::jsonb,
    directory_nodes jsonb DEFAULT '{}'::jsonb,
    directory_root_id text DEFAULT ''::text
);

CREATE TABLE IF NOT EXISTS public.conversations (
    id character varying(50) NOT NULL,
    user_id character varying(50) NOT NULL,
    message_ids jsonb DEFAULT '[]'::jsonb,
    knowledge_node_ids jsonb DEFAULT '[]'::jsonb,
    summary_short text DEFAULT ''::text,
    summary_dirty boolean DEFAULT false,
    parent_conversation_id character varying(50) DEFAULT ''::character varying,
    sub_branch_ids jsonb DEFAULT '[]'::jsonb,
    depth integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb,
    deleted_at timestamp with time zone
);

CREATE TABLE IF NOT EXISTS public.error_book (
    entry_id text NOT NULL,
    user_id text NOT NULL,
    question_id text NOT NULL,
    skill_id text NOT NULL,
    error_type text,
    misconception text,
    user_answer text DEFAULT ''::text,
    correct_answer text DEFAULT ''::text,
    question_text text DEFAULT ''::text,
    review_count integer DEFAULT 0,
    next_review timestamp without time zone DEFAULT now(),
    is_resolved boolean DEFAULT false,
    referenced_materials_json jsonb DEFAULT '[]'::jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS public.event_relations (
    id text NOT NULL,
    parent_id text NOT NULL,
    child_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.events (
    id text NOT NULL,
    user_id text NOT NULL,
    event_type text NOT NULL,
    source_type text NOT NULL,
    source_id text DEFAULT ''::text NOT NULL,
    status text DEFAULT 'done'::text NOT NULL,
    status_msg text DEFAULT ''::text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_ats timestamp with time zone[] DEFAULT ARRAY[now()],
    stream_type text,
    stream_id text,
    parent_event_id text,
    correlation_id text,
    summary text,
    importance real DEFAULT 0.0,
    embedding public.vector(384)
);

CREATE TABLE IF NOT EXISTS public.exploration_projects (
    id text NOT NULL,
    user_id text NOT NULL,
    title text NOT NULL,
    description text DEFAULT ''::text,
    goal text DEFAULT ''::text,
    node_ids jsonb DEFAULT '[]'::jsonb,
    prerequisites jsonb DEFAULT '[]'::jsonb,
    deliverables jsonb DEFAULT '[]'::jsonb,
    status text DEFAULT 'suggested'::text,
    difficulty double precision DEFAULT 0.5,
    estimated_hours double precision DEFAULT 2.0,
    source text DEFAULT 'system'::text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.ip_controls (
    id integer NOT NULL,
    ip character varying(45) NOT NULL,
    list_type character varying(10) NOT NULL,
    reason character varying(256) DEFAULT ''::character varying,
    is_temp boolean DEFAULT false,
    expires_at timestamp without time zone,
    created_by character varying(32) DEFAULT ''::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ip_controls_list_type_check CHECK (((list_type)::text = ANY ((ARRAY['blacklist'::character varying, 'whitelist'::character varying])::text[])))
);

CREATE TABLE IF NOT EXISTS public.knowledge_edges (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    user_id character varying(255) NOT NULL,
    source_node_id text NOT NULL,
    target_node_id text NOT NULL,
    edge_type character varying(50) DEFAULT 'related_to'::character varying NOT NULL,
    strength double precision DEFAULT 0.5,
    confidence double precision,
    trust_score double precision DEFAULT 0.5,
    edge_status character varying(30) DEFAULT 'suggested'::character varying,
    created_by character varying(50) DEFAULT 'system'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    last_evaluated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.knowledge_nodes (
    id text NOT NULL,
    user_id text NOT NULL,
    label text DEFAULT ''::text NOT NULL,
    level text DEFAULT 'atom'::text NOT NULL,
    parent text,
    children jsonb DEFAULT '[]'::jsonb,
    is_core boolean DEFAULT false,
    activation jsonb DEFAULT '{}'::jsonb,
    belief jsonb DEFAULT '{}'::jsonb,
    prediction jsonb DEFAULT '{}'::jsonb,
    cognitive_load jsonb DEFAULT '{}'::jsonb,
    trend jsonb DEFAULT '{}'::jsonb,
    scheduling jsonb DEFAULT '{}'::jsonb,
    dialogue_contexts jsonb DEFAULT '[]'::jsonb,
    practice_events jsonb DEFAULT '[]'::jsonb,
    practice_summary jsonb DEFAULT '{}'::jsonb,
    error_clusters jsonb DEFAULT '[]'::jsonb,
    metacognition jsonb DEFAULT '{}'::jsonb,
    engagement jsonb DEFAULT '{}'::jsonb,
    composition jsonb DEFAULT '{}'::jsonb,
    deep_links jsonb DEFAULT '[]'::jsonb,
    deep_processing jsonb DEFAULT '{}'::jsonb,
    goal_alignment jsonb DEFAULT '{}'::jsonb,
    diagnostic jsonb DEFAULT '{}'::jsonb,
    prerequisites jsonb DEFAULT '[]'::jsonb,
    unlocks jsonb DEFAULT '[]'::jsonb,
    associates jsonb DEFAULT '[]'::jsonb,
    param_refs jsonb DEFAULT '{}'::jsonb,
    meta jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    path_id text DEFAULT ''::text NOT NULL,
    node_type text DEFAULT 'explicit'::text NOT NULL,
    is_visible boolean DEFAULT false NOT NULL,
    subsystems jsonb DEFAULT '{}'::jsonb NOT NULL,
    embedding jsonb,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    emoji text DEFAULT ''::text,
    color text DEFAULT ''::text,
    sort_order integer DEFAULT 0,
    created_by character varying(50) DEFAULT 'system'::character varying,
    description text,
    metadata jsonb DEFAULT '{}'::jsonb,
    brief text DEFAULT ''::text,
    tags jsonb DEFAULT '[]'::jsonb,
    children_order jsonb DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS public.learning_goals (
    id text NOT NULL,
    user_id text NOT NULL,
    node_id text NOT NULL,
    node_label text DEFAULT ''::text,
    target_mastery double precision DEFAULT 0.8,
    target_date date,
    current_mastery double precision DEFAULT 0.0,
    priority integer DEFAULT 2,
    status text DEFAULT 'active'::text,
    notes text DEFAULT ''::text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.login_events (
    event_id text NOT NULL,
    user_id text NOT NULL,
    ip_address text DEFAULT ''::text,
    country text DEFAULT ''::text,
    region text DEFAULT ''::text,
    city text DEFAULT ''::text,
    user_agent text DEFAULT ''::text,
    device_type text DEFAULT ''::text,
    browser text DEFAULT ''::text,
    os text DEFAULT ''::text,
    is_current boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS public.material_chunks (
    chunk_id text NOT NULL,
    user_id text NOT NULL,
    material_id text NOT NULL,
    text text DEFAULT ''::text,
    chunk_type text DEFAULT 'text'::text,
    source_file text DEFAULT ''::text,
    chunk_index integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    indexed_at timestamp without time zone,
    indexing_status text DEFAULT 'pending'::text,
    embedding double precision[],
    heading_path text DEFAULT ''::text,
    embedding_vec public.vector(384)
);

CREATE TABLE IF NOT EXISTS public.material_toc (
    toc_id text NOT NULL,
    material_id text NOT NULL,
    parent_toc_id text,
    level integer DEFAULT 1 NOT NULL,
    heading text DEFAULT ''::text NOT NULL,
    chunk_start integer DEFAULT 0,
    chunk_end integer DEFAULT 0,
    page_start integer,
    created_at timestamp with time zone DEFAULT now(),
    heading_line_index integer DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.materials (
    material_id text NOT NULL,
    user_id text NOT NULL,
    file_name text NOT NULL,
    file_type text DEFAULT ''::text,
    file_size integer DEFAULT 0,
    storage_path text DEFAULT ''::text,
    purpose text DEFAULT 'session'::text,
    status text DEFAULT 'uploading'::text,
    chunk_count integer DEFAULT 0,
    skills_covered_json jsonb DEFAULT '[]'::jsonb,
    expires_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    indexed_at timestamp without time zone,
    summary text DEFAULT ''::text,
    tags_json jsonb DEFAULT '[]'::jsonb,
    is_folder boolean DEFAULT false,
    is_deleted boolean DEFAULT false,
    deleted_at timestamp without time zone,
    parent_id text DEFAULT ''::text,
    level text DEFAULT 'partition'::text
);

CREATE TABLE IF NOT EXISTS public.messages (
    id text NOT NULL,
    user_id text NOT NULL,
    conv_id text NOT NULL,
    role text NOT NULL,
    content text DEFAULT ''::text,
    content_blocks jsonb DEFAULT '[]'::jsonb,
    text_summary text DEFAULT ''::text,
    knowledge_node_ids jsonb DEFAULT '[]'::jsonb,
    parent_id text,
    children_ids jsonb DEFAULT '[]'::jsonb,
    has_sub_branches boolean DEFAULT false,
    sub_branch_ids jsonb DEFAULT '[]'::jsonb,
    sub_branch_summaries jsonb DEFAULT '[]'::jsonb,
    "timestamp" timestamp with time zone DEFAULT now(),
    token_count integer DEFAULT 0,
    version integer DEFAULT 1,
    is_deleted boolean DEFAULT false,
    agent_label text DEFAULT ''::text,
    metadata jsonb DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS public.navigation_nodes (
    id character varying(50) NOT NULL,
    user_id character varying(50) NOT NULL,
    parent_id character varying(50),
    node_type character varying(10) DEFAULT 'dir'::character varying NOT NULL,
    kind character varying(20) DEFAULT 'general'::character varying NOT NULL,
    name character varying(200) DEFAULT '新节点'::character varying NOT NULL,
    user_name character varying(200),
    ai_name character varying(200) DEFAULT ''::character varying,
    children_order jsonb DEFAULT '[]'::jsonb,
    conversation_id character varying(50),
    knowledge_area_id character varying(50),
    path jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb,
    deleted_at timestamp with time zone
);

CREATE TABLE IF NOT EXISTS public.plan_snapshots (
    id integer NOT NULL,
    user_id text NOT NULL,
    plan_json jsonb DEFAULT '{}'::jsonb,
    changes_json jsonb DEFAULT '{}'::jsonb,
    reason text DEFAULT ''::text,
    created_at timestamp without time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.practice_attempts (
    id text NOT NULL,
    session_id text NOT NULL,
    question_id text NOT NULL,
    user_id text NOT NULL,
    user_answer jsonb,
    is_correct boolean,
    time_spent_seconds integer DEFAULT 0,
    is_wrong boolean DEFAULT false,
    wrong_count integer DEFAULT 0,
    consecutive_correct integer DEFAULT 0,
    mastered boolean DEFAULT false,
    cognitive_node_ids text[] DEFAULT '{}'::text[],
    error_pattern character varying(50),
    created_at timestamp with time zone DEFAULT now(),
    error_analysis jsonb DEFAULT '{}'::jsonb,
    confidence_before integer
);

CREATE TABLE IF NOT EXISTS public.practice_material_questions (
    id integer NOT NULL,
    material_id text NOT NULL,
    question_id text NOT NULL,
    chunk_index integer,
    user_id text NOT NULL,
    session_id text,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.practice_sessions (
    id text NOT NULL,
    user_id text NOT NULL,
    bank_id text,
    session_type character varying(20) DEFAULT 'practice'::character varying NOT NULL,
    mode character varying(20) DEFAULT 'adaptive'::character varying NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    status character varying(20) DEFAULT 'created'::character varying NOT NULL,
    total_count integer NOT NULL,
    correct_count integer DEFAULT 0,
    wrong_count integer DEFAULT 0,
    score double precision,
    cognitive_node_ids text[] DEFAULT '{}'::text[],
    started_at timestamp with time zone DEFAULT now(),
    finished_at timestamp with time zone,
    duration_seconds integer,
    created_at timestamp with time zone DEFAULT now(),
    conversation_id character varying(64) DEFAULT NULL::character varying
);

CREATE TABLE IF NOT EXISTS public.question_banks (
    id text NOT NULL,
    user_id text NOT NULL,
    name character varying(255) NOT NULL,
    description text DEFAULT ''::text,
    import_source character varying(50) DEFAULT 'manual'::character varying,
    ref_node_id text,
    ref_node_level character varying(20),
    auto_created boolean DEFAULT false,
    question_count integer DEFAULT 0,
    preferences jsonb DEFAULT '{}'::jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);

CREATE TABLE IF NOT EXISTS public.question_user_flags (
    id text NOT NULL,
    user_id text NOT NULL,
    question_id text NOT NULL,
    flag_type text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.questions (
    id text NOT NULL,
    bank_id text NOT NULL,
    user_id text NOT NULL,
    question_type character varying(20) NOT NULL,
    stem text NOT NULL,
    options jsonb DEFAULT '[]'::jsonb,
    answer jsonb NOT NULL,
    explanation text DEFAULT ''::text,
    difficulty integer DEFAULT 3,
    cognitive_node_ids text[] DEFAULT '{}'::text[],
    source character varying(20) DEFAULT 'manual'::character varying,
    is_favorite boolean DEFAULT false,
    is_slashed boolean DEFAULT false,
    status character varying(20) DEFAULT 'active'::character varying,
    source_line integer,
    import_errors jsonb DEFAULT '[]'::jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone,
    skill_id text DEFAULT ''::text NOT NULL
);

CREATE TABLE IF NOT EXISTS public.secretary_proposals (
    id text NOT NULL,
    user_id text NOT NULL,
    session_id text,
    emoji text DEFAULT '💡'::text,
    title text NOT NULL,
    description text DEFAULT ''::text,
    action_type text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb,
    priority integer DEFAULT 3,
    generated_by text DEFAULT ''::text,
    overrideable boolean DEFAULT true,
    status text DEFAULT 'pending'::text,
    metadata jsonb DEFAULT '{}'::jsonb,
    snoozed_until timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    expires_at timestamp without time zone,
    updated_at timestamp without time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.session_questions (
    id text NOT NULL,
    session_id text NOT NULL,
    question_id text NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    user_answer jsonb,
    is_correct boolean,
    time_spent_seconds integer DEFAULT 0,
    hints_used integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.system_config (
    key character varying(64) NOT NULL,
    value text DEFAULT ''::text NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS public.user_notes (
    id text NOT NULL,
    user_id text NOT NULL,
    content text NOT NULL,
    type text DEFAULT 'note'::text NOT NULL,
    source_text text DEFAULT ''::text,
    node_ids jsonb DEFAULT '[]'::jsonb,
    message_id text,
    conversation_id text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.user_settings (
    user_id text NOT NULL,
    settings_jsonb jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.users (
    id text NOT NULL,
    username text NOT NULL,
    email text DEFAULT ''::text,
    password_hash text NOT NULL,
    display_name text DEFAULT ''::text,
    role text DEFAULT 'user'::text,
    is_active boolean DEFAULT true,
    last_login timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    avatar_url character varying(512) DEFAULT ''::character varying,
    last_active_at timestamp without time zone,
    token_version integer DEFAULT 0
);

-- ── FlashCard 模块表 (docs/modules/flashcard/data-model.md) ──
CREATE TABLE IF NOT EXISTS public.flashcards (
    id text NOT NULL,
    user_id text NOT NULL,
    type smallint NOT NULL,
    source character varying(30) NOT NULL,
    front_text text NOT NULL,
    back_text text,
    back_context text,
    language character varying(20),
    source_ref jsonb DEFAULT '{}'::jsonb,
    status character varying(20) DEFAULT 'pending'::text,
    suspended_at timestamp without time zone,
    is_resolved boolean DEFAULT false,
    stability double precision,
    difficulty double precision,
    forgetting_rate double precision,
    last_review_at timestamp without time zone,
    next_review_at timestamp without time zone,
    review_count integer DEFAULT 0,
    lapse_count integer DEFAULT 0,
    target_retention double precision DEFAULT 0.85,
    linked_node_ids jsonb DEFAULT '[]'::jsonb,
    node_link_roles jsonb DEFAULT '{}'::jsonb,
    tags jsonb DEFAULT '[]'::jsonb,
    error_book_entry_id text,
    response_history jsonb DEFAULT '[]'::jsonb,
    field_versions jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT NOW(),
    deleted_at timestamp without time zone
);

CREATE TABLE IF NOT EXISTS public.review_sessions (
    id text NOT NULL,
    user_id text NOT NULL,
    started_at timestamp without time zone NOT NULL,
    ended_at timestamp without time zone,
    card_count integer DEFAULT 0,
    difficult_count integer DEFAULT 0,
    good_count integer DEFAULT 0,
    easy_count integer DEFAULT 0,
    duration_seconds integer,
    source_module character varying(30)
);

CREATE TABLE IF NOT EXISTS public.review_history (
    id text NOT NULL,
    card_id text NOT NULL,
    session_id text,
    user_id text NOT NULL,
    self_assessment character varying(10) NOT NULL,
    stability_before double precision,
    stability_after double precision,
    difficulty_before double precision,
    difficulty_after double precision,
    interval_before integer,
    interval_after integer,
    elapsed_days integer,
    reviewed_at timestamp without time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.flashcard_tags (
    id text NOT NULL,
    user_id text NOT NULL,
    name character varying(128) NOT NULL,
    parent_id text,
    level smallint DEFAULT 0 NOT NULL,
    color character varying(7),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fc_user_status ON public.flashcards USING btree (user_id, status);
CREATE INDEX IF NOT EXISTS idx_fc_next_review ON public.flashcards USING btree (user_id, next_review_at) WHERE (status::text = 'pending'::text);
CREATE INDEX IF NOT EXISTS idx_fc_source ON public.flashcards USING btree (user_id, source);
CREATE INDEX IF NOT EXISTS idx_fc_type ON public.flashcards USING btree (user_id, type);
CREATE INDEX IF NOT EXISTS idx_fc_user_created ON public.flashcards USING btree (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fc_tags ON public.flashcards USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_fc_linked_nodes ON public.flashcards USING gin (linked_node_ids);
CREATE INDEX IF NOT EXISTS idx_fc_error_book ON public.flashcards USING btree (error_book_entry_id) WHERE (error_book_entry_id IS NOT NULL);
CREATE INDEX IF NOT EXISTS idx_rsessions_user ON public.review_sessions USING btree (user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rhistory_card ON public.review_history USING btree (card_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_rhistory_session ON public.review_history USING btree (session_id);
CREATE INDEX IF NOT EXISTS idx_rhistory_user ON public.review_history USING btree (user_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_fctags_user_parent ON public.flashcard_tags USING btree (user_id, parent_id);
