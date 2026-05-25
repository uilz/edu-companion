"""
Phase 8 数据库迁移脚本

逐条执行（幂等）：
    psql -h localhost -p 5433 -U companion -d edu_companion -f migrate_phase8.sql
"""

-- =============================================
-- 1. cognitive_nodes 加列
-- =============================================
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS path_id VARCHAR(500);
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR(50) DEFAULT 'explicit';
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT false;
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS subsystems JSONB DEFAULT '{}';
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS embedding JSONB;
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- 索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_cn_path_id
    ON cognitive_nodes(user_id, path_id)
    WHERE path_id IS NOT NULL AND deleted_at IS NULL;

-- vector index removed — uses Python cosine similarity instead

CREATE INDEX IF NOT EXISTS idx_cn_parent
    ON cognitive_nodes(user_id, parent)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cn_level
    ON cognitive_nodes(user_id, level)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cn_visible
    ON cognitive_nodes(user_id, parent, is_visible)
    WHERE is_visible = true AND deleted_at IS NULL;

-- =============================================
-- 2. 知识图谱边表
-- =============================================
CREATE TABLE IF NOT EXISTS knowledge_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    source_node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
    target_node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
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
-- 3. 会话-节点关联表
-- =============================================
CREATE TABLE IF NOT EXISTS conversation_node_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) NOT NULL,
    node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
    added_by VARCHAR(50) DEFAULT 'system',
    is_primary BOOLEAN DEFAULT false,
    added_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(conversation_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_cnl_conv ON conversation_node_links(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cnl_node ON conversation_node_links(node_id);
