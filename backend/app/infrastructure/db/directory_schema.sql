-- DirectoryNode 统一目录表
-- 取代旧 conversation_user_meta 中的 partitions/domains/topics JSONB 字段

ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS directory_nodes JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS directory_root_id TEXT DEFAULT '';

-- 索引: 加速按用户和路径查询
CREATE INDEX IF NOT EXISTS idx_conv_meta_dn ON conversation_user_meta USING GIN (directory_nodes jsonb_path_ops);

-- 旧向后兼容字段 (partitions, domains, topics, conversations 等) 已从 conversation_schema 中移除
