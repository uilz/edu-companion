-- ============================================================
-- Phase 1: 数据模型重构 (v6.md)
-- 适配现有 TEXT ID 约定，无外键约束（与现有 schema 一致）
-- ============================================================

-- ── 1.1 cognitive_nodes 索引（补全）──
-- parent 字段已存在（TEXT 类型），加索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cn_parent
  ON cognitive_nodes(user_id, parent) WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cn_level
  ON cognitive_nodes(user_id, level) WHERE deleted_at IS NULL;


-- ── 1.2 conversations 表（映射旧表的顶层对话）──
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    source_partition_id TEXT,
    source_branch_id TEXT,
    is_temporary BOOLEAN DEFAULT false,
    message_count INT DEFAULT 0,
    last_activity_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_temp ON conversations(is_temporary, last_activity_at) WHERE is_temporary = true;


-- ── 1.2 messages 表（原生 VECTOR(1536) 类型，需 pgvector 扩展）──
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    content_blocks JSONB DEFAULT '[]',
    embedding vector(1536),
    cognitive_node_ids TEXT[] DEFAULT '{}',
    cognitive_annotations JSONB DEFAULT '[]',
    summary TEXT,
    token_count INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, created_at);
-- 数据非空后执行: CREATE INDEX idx_msg_embedding ON messages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- ── 1.3 conversation_summaries 表 ──
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    round_number INT NOT NULL,
    summary TEXT NOT NULL,
    involved_node_ids TEXT[] DEFAULT '{}',
    token_count INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(conversation_id, round_number)
);
CREATE INDEX IF NOT EXISTS idx_cs_conv ON conversation_summaries(conversation_id, round_number DESC);


-- ── 1.3 cognitive_events 补全索引（表已存在）──
CREATE INDEX IF NOT EXISTS idx_ce_type ON cognitive_events(user_id, event_type, created_at DESC);


-- ── 数据迁移：conversation_partitions → conversations ──
INSERT INTO conversations (id, user_id, title, source_partition_id, created_at)
SELECT
    gen_random_uuid()::text,
    COALESCE(cp.user_id, 'unknown'),
    COALESCE(cp.name, '未命名分区'),
    cp.id,
    to_timestamp(COALESCE(cp.created_at, extract(epoch from now())))
FROM conversation_partitions cp
WHERE NOT EXISTS (SELECT 1 FROM conversations c WHERE c.source_partition_id = cp.id)
ON CONFLICT DO NOTHING;

-- 统计 conversations 的消息数
UPDATE conversations c
SET message_count = (
    SELECT COUNT(*) FROM conversation_nodes cn
    WHERE cn.partition_id = c.source_partition_id AND cn.is_deleted IS DISTINCT FROM true
),
last_activity_at = COALESCE((
    SELECT to_timestamp(MAX(cn.timestamp)) FROM conversation_nodes cn
    WHERE cn.partition_id = c.source_partition_id
), c.last_activity_at)
WHERE c.source_partition_id IS NOT NULL;
