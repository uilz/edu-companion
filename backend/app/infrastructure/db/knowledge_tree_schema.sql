-- 知识树壳 Schema
-- 四实体解耦：knowledge_trees / tree_nodes / tree_edges / tree_node_cognitive_links

CREATE TABLE IF NOT EXISTS knowledge_trees (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT '我的知识树',
    description TEXT NOT NULL DEFAULT '',
    tree_type VARCHAR(32) NOT NULL DEFAULT 'project',
    root_node_id VARCHAR(32),
    default_view_mode VARCHAR(32) NOT NULL DEFAULT 'tree',
    default_layout VARCHAR(32) NOT NULL DEFAULT 'layered',
    tags JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_knowledge_trees_user ON knowledge_trees(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_trees_user_status ON knowledge_trees(user_id, status);

CREATE TABLE IF NOT EXISTS tree_nodes (
    id VARCHAR(32) PRIMARY KEY,
    tree_id VARCHAR(32) NOT NULL REFERENCES knowledge_trees(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    label VARCHAR(255) NOT NULL,
    node_type VARCHAR(32) NOT NULL DEFAULT 'concept',
    parent_id VARCHAR(32) REFERENCES tree_nodes(id) ON DELETE CASCADE,
    children_order JSONB NOT NULL DEFAULT '[]',
    order_index INT NOT NULL DEFAULT 0,
    color VARCHAR(16) NOT NULL DEFAULT '',
    emoji VARCHAR(8) NOT NULL DEFAULT '',
    icon_url VARCHAR(512) NOT NULL DEFAULT '',
    position JSONB NOT NULL DEFAULT '{}',
    source_refs JSONB NOT NULL DEFAULT '[]',
    tags JSONB NOT NULL DEFAULT '[]',
    brief TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tree_nodes_tree ON tree_nodes(tree_id);
CREATE INDEX IF NOT EXISTS idx_tree_nodes_user ON tree_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_tree_nodes_parent ON tree_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_tree_nodes_tree_status ON tree_nodes(tree_id, status);

CREATE TABLE IF NOT EXISTS tree_edges (
    id VARCHAR(32) PRIMARY KEY,
    tree_id VARCHAR(32) NOT NULL REFERENCES knowledge_trees(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    source_node_id VARCHAR(32) NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    target_node_id VARCHAR(32) NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    edge_type VARCHAR(32) NOT NULL DEFAULT 'parent_child',
    strength FLOAT NOT NULL DEFAULT 1.0,
    is_user_confirmed BOOLEAN NOT NULL DEFAULT TRUE,
    is_inferred BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tree_id, source_node_id, target_node_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_tree_edges_tree ON tree_edges(tree_id);
CREATE INDEX IF NOT EXISTS idx_tree_edges_source ON tree_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_tree_edges_target ON tree_edges(target_node_id);

CREATE TABLE IF NOT EXISTS tree_node_cognitive_links (
    id VARCHAR(32) PRIMARY KEY,
    tree_id VARCHAR(32) NOT NULL REFERENCES knowledge_trees(id) ON DELETE CASCADE,
    tree_node_id VARCHAR(32) NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    cognitive_node_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    link_role VARCHAR(32) NOT NULL DEFAULT 'primary',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tree_id, tree_node_id, cognitive_node_id)
);

CREATE INDEX IF NOT EXISTS idx_tree_cognitive_links_tree ON tree_node_cognitive_links(tree_id);
CREATE INDEX IF NOT EXISTS idx_tree_cognitive_links_tree_node ON tree_node_cognitive_links(tree_node_id);
CREATE INDEX IF NOT EXISTS idx_tree_cognitive_links_cognitive ON tree_node_cognitive_links(cognitive_node_id);
CREATE INDEX IF NOT EXISTS idx_tree_cognitive_links_user ON tree_node_cognitive_links(user_id);
