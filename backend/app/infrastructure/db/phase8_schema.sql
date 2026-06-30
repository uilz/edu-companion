-- Phase 16: 认知节点补全迁移（幂等）
-- 为 knowledge_nodes 添加 Phase 8 缺失的列、表、索引
-- 由 database.py._migrate() 自动执行

-- =============================================
-- 1. knowledge_nodes 加列
-- =============================================
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS path_id VARCHAR(500);
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR(50) DEFAULT 'explicit';
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT false;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS subsystems JSONB DEFAULT '{}';
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS embedding JSONB;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS emoji TEXT DEFAULT '';
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS color TEXT DEFAULT '';
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS sort_order INT DEFAULT 0;

-- =============================================
-- 2. 索引增强 (Phase 16 新增)
-- =============================================

-- label 索引（find_node_by_label 热点查询）
CREATE INDEX IF NOT EXISTS idx_cn_label
    ON knowledge_nodes(user_id, label)
    WHERE label IS NOT NULL AND label != '' AND deleted_at IS NULL;

-- =============================================
-- 3. 知识图谱边表
-- =============================================
CREATE TABLE IF NOT EXISTS knowledge_edges (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id VARCHAR(255) NOT NULL,
    source_node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    target_node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    edge_type VARCHAR(50) NOT NULL DEFAULT 'related_to',
    strength FLOAT DEFAULT 0.5,
    confidence FLOAT,
    trust_score FLOAT DEFAULT 0.5,
    edge_status VARCHAR(30) DEFAULT 'suggested',
    created_by VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT now(),
    last_evaluated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_node_id, target_node_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_ke_source ON knowledge_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_ke_target ON knowledge_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_ke_status ON knowledge_edges(user_id, edge_status);

-- =============================================
-- 4. 会话-节点关联表
-- =============================================
CREATE TABLE IF NOT EXISTS conversation_node_links (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    conversation_id VARCHAR(255) NOT NULL,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    added_by VARCHAR(50) DEFAULT 'system',
    is_primary BOOLEAN DEFAULT false,
    added_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(conversation_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_cnl_conv ON conversation_node_links(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cnl_node ON conversation_node_links(node_id);

-- =============================================
-- 5. cognitive_events 复合索引 (Phase 16)
-- =============================================
CREATE INDEX IF NOT EXISTS idx_cog_events_lookup
    ON cognitive_events(user_id, event_type, node_id);

-- =============================================
-- 6. 补全 cognitive_schema.sql 中缺失的旧索引
--    （path_id 唯一索引 + 可见性索引）
-- =============================================
CREATE UNIQUE INDEX IF NOT EXISTS idx_cn_path_id
    ON knowledge_nodes(user_id, path_id)
    WHERE path_id IS NOT NULL AND path_id != '' AND deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cn_parent_visible
    ON knowledge_nodes(user_id, parent)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cn_level_filtered
    ON knowledge_nodes(user_id, level)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cn_visible
    ON knowledge_nodes(user_id, parent, is_visible)
    WHERE is_visible = true AND deleted_at IS NULL;
