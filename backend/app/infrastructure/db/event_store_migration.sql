-- EventSystem v2 迁移: events 表扩展
-- 新增字段: stream_type, stream_id, parent_event_id, correlation_id, summary, importance, embedding
-- 2026-06-22

-- 1. 扩展 pgvector (如未安装则跳过)
DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector not available, skipping vector extension';
END $$;

-- 2. 新增列 (stream 归属)
ALTER TABLE events ADD COLUMN IF NOT EXISTS stream_type TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS stream_id TEXT;

-- 3. 新增列 (因果链 + 跨域关联)
ALTER TABLE events ADD COLUMN IF NOT EXISTS parent_event_id TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS correlation_id TEXT;

-- 4. 新增列 (AI 摘要 + 重要性)
ALTER TABLE events ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS importance REAL DEFAULT 0.0;

-- 5. 新增列 (向量嵌入 — 384维, 与 granite-embedding-97m 一致)
DO $$ BEGIN
    ALTER TABLE events ADD COLUMN embedding vector(384);
EXCEPTION WHEN duplicate_column THEN
    RAISE NOTICE 'column embedding already exists';
WHEN OTHERS THEN
    RAISE NOTICE 'pgvector not available, skipping embedding column';
END $$;

-- 6. 填充已有数据的 stream_type / stream_id (默认与 source 一致)
UPDATE events SET stream_type = source_type WHERE stream_type IS NULL;
UPDATE events SET stream_id = source_id WHERE stream_id IS NULL;

-- 7. 新索引
CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream_type, stream_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_parent ON events(parent_event_id) WHERE parent_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_importance ON events(user_id, importance DESC) WHERE importance > 0.5;

-- 8. pgvector HNSW 索引 (语义搜索)
DO $$ BEGIN
    CREATE INDEX IF NOT EXISTS idx_events_embedding
        ON events USING hnsw (embedding vector_cosine_ops)
        WITH (m=16, ef_construction=200);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector HNSW index not available';
END $$;