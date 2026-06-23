-- Events 表 — 通用事件记录 (v2)
-- 取代旧 cognitive_events 表, 独立于 cognitive 模块
-- 多个模块 (cognitive/secretary/practice/conversation) 共用
-- v2 新增: stream归属、因果链、跨域关联、AI摘要、重要性、向量嵌入

CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    -- 事件类型
    event_type      TEXT NOT NULL,

    -- 流归属 (v2 新增)
    stream_type     TEXT,                   -- conversation | practice | knowledge | secretary | system
    stream_id       TEXT,                   -- 流内实体ID (conversation_id / session_id / node_id)

    -- 来源 (保留兼容)
    source_type     TEXT NOT NULL,          -- conversation | practice | secretary | manual | system
    source_id       TEXT NOT NULL DEFAULT '',

    -- 因果链 (v2 新增)
    parent_event_id TEXT,                   -- 哪个事件触发了这个
    correlation_id  TEXT,                   -- 跨域关联 (同一用户操作链)

    -- 状态
    status          TEXT NOT NULL DEFAULT 'done',  -- pending | processing | done | failed
    status_msg      TEXT NOT NULL DEFAULT '',

    -- 数据
    payload         JSONB NOT NULL DEFAULT '{}',

    -- AI 记忆 (v2 新增)
    summary         TEXT,                   -- AI 生成的事件摘要 (用于长期记忆检索)
    importance      REAL DEFAULT 0.0,       -- 0~1 重要性评分 (用于记忆淘汰)
    embedding       vector(384),            -- 向量嵌入 (granite-embedding-97m, 384维)

    -- 时间
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_ats     TIMESTAMPTZ[] DEFAULT ARRAY[NOW()]
);

-- 查询索引
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status, created_at) WHERE status = 'pending';

-- v2 新增索引
CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream_type, stream_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_parent ON events(parent_event_id) WHERE parent_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_importance ON events(user_id, importance DESC) WHERE importance > 0.5;

-- pgvector HNSW 索引 (语义搜索)
DO $$ BEGIN
    CREATE INDEX IF NOT EXISTS idx_events_embedding
        ON events USING hnsw (embedding vector_cosine_ops)
        WITH (m=16, ef_construction=200);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector HNSW index not available for events';
END $$;