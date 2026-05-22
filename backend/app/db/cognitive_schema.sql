-- CognitiveNode 数据表
-- 基于 AI 伴学系统中枢数据设计文档 v2.10

-- ════════════════════════════════════════════
-- 节点表：每行一个 CognitiveNode
-- 全部子系统存在 JSONB 字段中
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cognitive_nodes (
    id              TEXT NOT NULL,              -- "math.analysis.derivative.chain_rule"
    user_id         TEXT NOT NULL,              -- 多用户支持
    label           TEXT NOT NULL DEFAULT '',
    level           TEXT NOT NULL DEFAULT 'atom', -- partition|domain|topic|concept|atom
    parent          TEXT,                        -- 父节点 ID
    children        JSONB DEFAULT '[]'::jsonb,
    is_core         BOOLEAN DEFAULT FALSE,

    -- 认知状态（JSONB 子系统）
    activation      JSONB DEFAULT '{}',
    belief           JSONB DEFAULT '{}',
    prediction      JSONB DEFAULT '{}',
    cognitive_load  JSONB DEFAULT '{}',
    trend           JSONB DEFAULT '{}',
    scheduling      JSONB DEFAULT '{}',
    dialogue_contexts JSONB DEFAULT '[]',
    practice_events JSONB DEFAULT '[]',
    practice_summary JSONB DEFAULT '{}',
    error_clusters  JSONB DEFAULT '[]',
    metacognition   JSONB DEFAULT '{}',
    engagement      JSONB DEFAULT '{}',
    composition     JSONB DEFAULT '{}',
    deep_links      JSONB DEFAULT '[]',
    deep_processing JSONB DEFAULT '{}',
    goal_alignment  JSONB DEFAULT '{}',
    diagnostic      JSONB DEFAULT '{}',

    -- 图谱结构
    prerequisites   JSONB DEFAULT '[]',
    unlocks          JSONB DEFAULT '[]',
    associates      JSONB DEFAULT '[]',

    -- 参数引用
    param_refs      JSONB DEFAULT '{}',

    -- 元信息
    meta            JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (id)
);

-- 用户索引（user_id 不是 PK 一部分，但需要快速过滤）
CREATE INDEX IF NOT EXISTS idx_cog_nodes_user ON cognitive_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_cog_nodes_parent ON cognitive_nodes(parent);
CREATE INDEX IF NOT EXISTS idx_cog_nodes_level ON cognitive_nodes(level);
-- next_review: 浮点时间戳（Unix 秒，含小数），用 double precision
CREATE INDEX IF NOT EXISTS idx_cog_nodes_next_review
    ON cognitive_nodes (((scheduling ->> 'next_review'::text)::double precision))
    WHERE (scheduling ->> 'next_review'::text) IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cog_nodes_urgency
    ON cognitive_nodes(((scheduling->>'urgency')::float) DESC)
    WHERE scheduling->>'urgency' IS NOT NULL;

-- ════════════════════════════════════════════
-- 事件表
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cognitive_events (
    event_id    TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,           -- practice_response|diagnostic_result|...
    user_id     TEXT NOT NULL,
    node_id     TEXT,
    timestamp   TIMESTAMPTZ NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}',
    processed   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cog_events_user ON cognitive_events(user_id);
CREATE INDEX IF NOT EXISTS idx_cog_events_type ON cognitive_events(event_type);
CREATE INDEX IF NOT EXISTS idx_cog_events_node ON cognitive_events(node_id);
CREATE INDEX IF NOT EXISTS idx_cog_events_unprocessed
    ON cognitive_events(created_at)
    WHERE processed = FALSE;
