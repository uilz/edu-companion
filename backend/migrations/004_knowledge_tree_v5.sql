-- ============================================================
-- Round 4 Migration: Knowledge Tree v5
-- 重构 cognitive_nodes → knowledge_nodes，新增 navigation_nodes、
-- conversations、messages 表，支持知识树导航与对话系统。
-- 执行方式: psql -h localhost -U companion -d edu_companion -f 004_knowledge_tree_v5.sql
-- ============================================================

BEGIN;

-- ── 0. 清理旧表 & 外键约束 ──

-- 删除引用 cognitive_nodes 的外键约束
ALTER TABLE IF EXISTS knowledge_edges        DROP CONSTRAINT IF EXISTS knowledge_edges_source_node_id_fkey;
ALTER TABLE IF EXISTS knowledge_edges        DROP CONSTRAINT IF EXISTS knowledge_edges_target_node_id_fkey;
ALTER TABLE IF EXISTS conversation_node_links DROP CONSTRAINT IF EXISTS conversation_node_links_node_id_fkey;

-- 删除旧的 conversations 和 messages 表（schema 与 v5 不一致，数据量极少）
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS messages CASCADE;

-- ── 1. cognitive_nodes 扩展 & 重命名为 knowledge_nodes ──

ALTER TABLE IF EXISTS cognitive_nodes
    ADD COLUMN IF NOT EXISTS tags           JSONB       DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS created_by     VARCHAR(50) DEFAULT 'user',
    ADD COLUMN IF NOT EXISTS brief          TEXT        DEFAULT '',
    ADD COLUMN IF NOT EXISTS emoji          VARCHAR(10) DEFAULT '',
    ADD COLUMN IF NOT EXISTS color          VARCHAR(20) DEFAULT '',
    ADD COLUMN IF NOT EXISTS sort_order     INT         DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_visible     BOOLEAN     DEFAULT true,
    ADD COLUMN IF NOT EXISTS node_type      VARCHAR(50) DEFAULT 'explicit',
    ADD COLUMN IF NOT EXISTS path_id        VARCHAR(500) DEFAULT '',
    ADD COLUMN IF NOT EXISTS is_active      BOOLEAN     DEFAULT true,
    ADD COLUMN IF NOT EXISTS children_order JSONB       DEFAULT '[]'::jsonb;

ALTER TABLE IF EXISTS cognitive_nodes RENAME TO knowledge_nodes;

-- 重建外键约束，指向 knowledge_nodes
ALTER TABLE IF EXISTS knowledge_edges
    ADD CONSTRAINT knowledge_edges_source_node_id_fkey
    FOREIGN KEY (source_node_id) REFERENCES knowledge_nodes(id);

ALTER TABLE IF EXISTS knowledge_edges
    ADD CONSTRAINT knowledge_edges_target_node_id_fkey
    FOREIGN KEY (target_node_id) REFERENCES knowledge_nodes(id);

ALTER TABLE IF EXISTS conversation_node_links
    ADD CONSTRAINT conversation_node_links_node_id_fkey
    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id);

-- ── 2. navigation_nodes 表 ──

CREATE TABLE IF NOT EXISTS navigation_nodes (
    id                VARCHAR(50) PRIMARY KEY,
    user_id           VARCHAR(50) NOT NULL,
    parent_id         VARCHAR(50),
    node_type         VARCHAR(10) NOT NULL DEFAULT 'dir',
    kind              VARCHAR(20) NOT NULL DEFAULT 'general',
    name              VARCHAR(200) NOT NULL DEFAULT '新节点',
    user_name         VARCHAR(200),
    ai_name           VARCHAR(200) DEFAULT '',
    children_order    JSONB       DEFAULT '[]'::jsonb,
    conversation_id   VARCHAR(50),
    knowledge_area_id VARCHAR(50),
    path              JSONB       DEFAULT '[]'::jsonb,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    metadata          JSONB       DEFAULT '{}'::jsonb,
    deleted_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_nav_user            ON navigation_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_nav_parent          ON navigation_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nav_node_type       ON navigation_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nav_conversation    ON navigation_nodes(conversation_id);
CREATE INDEX IF NOT EXISTS idx_nav_knowledge_area  ON navigation_nodes(knowledge_area_id);

-- ── 3. conversations 表 ──

CREATE TABLE IF NOT EXISTS conversations (
    id                      VARCHAR(50) PRIMARY KEY,
    user_id                 VARCHAR(50) NOT NULL,
    message_ids             JSONB       DEFAULT '[]'::jsonb,
    knowledge_node_ids      JSONB       DEFAULT '[]'::jsonb,
    summary_short           TEXT        DEFAULT '',
    summary_dirty           BOOLEAN     DEFAULT false,
    parent_conversation_id  VARCHAR(50) DEFAULT '',
    sub_branch_ids          JSONB       DEFAULT '[]'::jsonb,
    depth                   INT         DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    metadata                JSONB       DEFAULT '{}'::jsonb,
    deleted_at              TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_conv_user            ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_knowledge_nodes ON conversations USING GIN (knowledge_node_ids);
CREATE INDEX IF NOT EXISTS idx_conv_parent          ON conversations(parent_conversation_id);

-- ── 4. messages 表 ──

CREATE TABLE IF NOT EXISTS messages (
    id                  VARCHAR(50) PRIMARY KEY,
    user_id             VARCHAR(50) NOT NULL,
    conversation_id     VARCHAR(50) NOT NULL,
    role                VARCHAR(20) NOT NULL DEFAULT 'user',
    content             TEXT        DEFAULT '',
    content_blocks      JSONB       DEFAULT '[]'::jsonb,
    text_summary        TEXT        DEFAULT '',
    knowledge_node_ids  JSONB       DEFAULT '[]'::jsonb,
    parent_id           VARCHAR(50),
    children_ids        JSONB       DEFAULT '[]'::jsonb,
    has_sub_branches    BOOLEAN     DEFAULT false,
    sub_branch_ids      JSONB       DEFAULT '[]'::jsonb,
    sub_branch_summaries JSONB      DEFAULT '[]'::jsonb,
    version             INT         DEFAULT 1,
    is_deleted          BOOLEAN     DEFAULT false,
    timestamp           TIMESTAMPTZ DEFAULT NOW(),
    token_count         INT         DEFAULT 0,
    agent_label         VARCHAR(50) DEFAULT '',
    metadata            JSONB       DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_msg_user            ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_msg_conversation    ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_knowledge_nodes ON messages USING GIN (knowledge_node_ids);
CREATE INDEX IF NOT EXISTS idx_msg_parent          ON messages(parent_id);
CREATE INDEX IF NOT EXISTS idx_msg_timestamp       ON messages(timestamp);

COMMIT;