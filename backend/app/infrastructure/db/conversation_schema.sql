-- 对话系统 PostgreSQL 持久化 (v5.0)
-- 统一 UserData JSONB 存储，仅保留 conversation_user_meta 表

-- 用户元数据表（存储完整 UserData 所有字段）
CREATE TABLE IF NOT EXISTS conversation_user_meta (
    user_id TEXT PRIMARY KEY,
    role TEXT DEFAULT 'student',
    org_id TEXT,
    active_partition_id TEXT,
    knowledge_graphs JSONB DEFAULT '{}',
    created_at DOUBLE PRECISION DEFAULT 0,
    updated_at DOUBLE PRECISION DEFAULT 0
);

-- 统一 JSONB 字段（存储完整 UserData 结构）
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS partitions JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS conversations JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS nodes JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS link_nodes JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS response_blocks JSONB DEFAULT '{}';

-- 旧向后兼容字段 (event_log, domains, topics, files, background_jobs) 已移除
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS secretary_prefs JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS policy_memory JSONB DEFAULT '{}';
