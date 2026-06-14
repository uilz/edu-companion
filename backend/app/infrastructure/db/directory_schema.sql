-- DirectoryNode 统一目录表
-- 取代旧 conversation_user_meta 中的 partitions/domains/topics JSONB 字段

ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS directory_nodes JSONB DEFAULT '{}';
ALTER TABLE conversation_user_meta ADD COLUMN IF NOT EXISTS directory_root_id TEXT DEFAULT '';

-- 索引: 加速按用户和路径查询
CREATE INDEX IF NOT EXISTS idx_conv_meta_dn ON conversation_user_meta USING GIN (directory_nodes jsonb_path_ops);

-- 旧字段标记为废弃 (保留为兼容过渡, 可后续删除)
-- partitions, domains, topics, conversations 字段不再使用
