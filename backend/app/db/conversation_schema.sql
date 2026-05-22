-- 对话系统 PostgreSQL 持久化 (v3.0)
-- 替换 JSON 文件存储，支持查询和索引

-- 分区表
CREATE TABLE IF NOT EXISTS conversation_partitions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    direction TEXT DEFAULT 'subject',
    emoji TEXT DEFAULT '💬',
    color TEXT DEFAULT '#0066FF',
    root_id TEXT NOT NULL,
    active_branch_id TEXT DEFAULT '',
    context_summary TEXT DEFAULT '',
    summary_branches JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    created_at DOUBLE PRECISION DEFAULT 0,
    updated_at DOUBLE PRECISION DEFAULT 0,
    last_active_at DOUBLE PRECISION DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0
);

-- 分支表
CREATE TABLE IF NOT EXISTS conversation_branches (
    id TEXT PRIMARY KEY,
    partition_id TEXT NOT NULL REFERENCES conversation_partitions(id) ON DELETE CASCADE,
    topic_id TEXT DEFAULT '',
    name TEXT DEFAULT '',
    fork_point_id TEXT,
    path TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    is_archived BOOLEAN DEFAULT false,
    summary TEXT,
    summary_dirty BOOLEAN DEFAULT false,
    practice_sessions TEXT[] DEFAULT '{}',
    practice_summary TEXT DEFAULT '',
    created_at DOUBLE PRECISION DEFAULT 0,
    last_message_at DOUBLE PRECISION DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_branches_partition ON conversation_branches(partition_id);

-- 消息节点表
CREATE TABLE IF NOT EXISTS conversation_nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT NOT NULL,
    children_ids TEXT[] DEFAULT '{}',
    partition_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    content_blocks JSONB DEFAULT '[]',
    text_summary TEXT DEFAULT '',
    summary TEXT,
    role TEXT NOT NULL,
    timestamp DOUBLE PRECISION DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT false,
    is_archived BOOLEAN DEFAULT false,
    has_modified_version BOOLEAN DEFAULT false,
    links_to TEXT[] DEFAULT '{}',
    linked_from TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_nodes_branch ON conversation_nodes(branch_id);
CREATE INDEX IF NOT EXISTS idx_nodes_partition ON conversation_nodes(partition_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON conversation_nodes(parent_id);

-- 响应块表
CREATE TABLE IF NOT EXISTS conversation_response_blocks (
    id TEXT PRIMARY KEY,
    message_id TEXT DEFAULT '',
    partition_id TEXT DEFAULT '',
    branch_id TEXT DEFAULT '',
    type TEXT NOT NULL,
    status TEXT DEFAULT 'ready',
    content JSONB DEFAULT '{}',
    "order" INTEGER DEFAULT 0,
    sources TEXT[] DEFAULT '{}',
    created_at DOUBLE PRECISION DEFAULT 0,
    updated_at DOUBLE PRECISION DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_blocks_message ON conversation_response_blocks(message_id);

-- 链接节点表
CREATE TABLE IF NOT EXISTS conversation_link_nodes (
    id TEXT PRIMARY KEY,
    target_message_id TEXT NOT NULL,
    target_partition_id TEXT NOT NULL,
    target_branch_id TEXT NOT NULL,
    source_partition_id TEXT NOT NULL,
    source_branch_id TEXT NOT NULL,
    preview_summary TEXT,
    timestamp DOUBLE PRECISION DEFAULT 0
);

-- 用户元数据表 (v4.2 — Phase 6.5 全字段)
CREATE TABLE IF NOT EXISTS conversation_user_meta (
    user_id TEXT PRIMARY KEY,
    role TEXT DEFAULT 'student',
    org_id TEXT,
    active_partition_id TEXT,
    knowledge_graphs JSONB DEFAULT '{}',
    created_at DOUBLE PRECISION DEFAULT 0
);

-- Phase 6.5: 追加全字段列（幂等）
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS knowledge_states JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS practice_sessions JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS error_book JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS event_log JSONB DEFAULT '[]';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS domains JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS topics JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS files JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS background_jobs JSONB DEFAULT '{}';
