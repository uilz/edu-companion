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
    total_tokens INTEGER DEFAULT 0,
    is_temp BOOLEAN NOT NULL DEFAULT false
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

-- ── v5 对话层级扩展：Conversation 支持挂载到任意层级 ──
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS parent_id TEXT DEFAULT '';
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS parent_type TEXT DEFAULT 'topic';
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'normal';
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS domain_id TEXT DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_branches_parent ON conversation_branches(parent_id);
CREATE INDEX IF NOT EXISTS idx_branches_type ON conversation_branches(type);

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
    created_at DOUBLE PRECISION DEFAULT 0,
    updated_at DOUBLE PRECISION DEFAULT 0
);

-- Phase 6.5: 追加全字段列（幂等）
-- DEPRECATED (Phase A2): practice_sessions now lives in separate practice_sessions table.
-- ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS practice_sessions JSONB DEFAULT '{}';
-- DEPRECATED (Phase A2): error_book now lives in separate error_book table.
-- ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS error_book JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS event_log JSONB DEFAULT '[]';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS domains JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS topics JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS files JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS background_jobs JSONB DEFAULT '{}';

-- Phase A3: 秘书系统存储统一 — secretary_prefs + policy_memory 从 JSON 文件迁移到 JSONB
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS secretary_prefs JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS policy_memory JSONB DEFAULT '{}';
