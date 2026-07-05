-- Project（项目式探索构建）建表
-- 本文件由 _ensure_tables() 幂等执行，所有表用 IF NOT EXISTS
-- 对应文档: docs/modules/project-based-exploration/data-model.md
--
-- 注意：target_node_id 不带 FK 引用（应用层在 service.mark_broken_references
-- 后再删除节点），保证引用记录不被 CASCADE 误删，可显示"已失效"。

-- 1. 项目主表
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    template_id UUID,
    template_version INT,
    status VARCHAR(20) DEFAULT 'active',
    tags JSONB DEFAULT '[]'::jsonb,
    node_count INT DEFAULT 0,
    completed_node_count INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(user_id, status);
CREATE INDEX IF NOT EXISTS idx_projects_template ON projects(template_id) WHERE template_id IS NOT NULL;

-- 2. 节点表（统一表，type 区分 1-7）
CREATE TABLE IF NOT EXISTS project_nodes (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES project_nodes(id) ON DELETE CASCADE,
    type SMALLINT NOT NULL CHECK (type BETWEEN 1 AND 7),
    title TEXT NOT NULL,
    description TEXT,
    order_in_parent INT DEFAULT 0,
    tags JSONB DEFAULT '[]'::jsonb,

    -- 类型特定内容
    content JSONB,
    rows JSONB,
    columns JSONB,
    language VARCHAR(20),
    code TEXT,
    explanation TEXT,
    material_id VARCHAR(64),
    chunk_id_range JSONB,
    fragments JSONB,

    -- 关联
    linked_node_ids JSONB DEFAULT '[]'::jsonb,
    linked_material_ids JSONB DEFAULT '[]'::jsonb,
    linked_card_ids JSONB DEFAULT '[]'::jsonb,
    cross_project_refs JSONB DEFAULT '[]'::jsonb,

    -- 元数据
    version INT NOT NULL DEFAULT 1,
    is_archived BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'pending',
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 迁移: 兼容旧表 (无 status 列)
ALTER TABLE project_nodes ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE project_nodes ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_nodes_project ON project_nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON project_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON project_nodes(user_id, type);
CREATE INDEX IF NOT EXISTS idx_nodes_archived ON project_nodes(user_id, is_archived);
CREATE INDEX IF NOT EXISTS idx_nodes_completed ON project_nodes(project_id, completed_at);

-- 3. 节点版本历史（横切能力 — 字段级粒度）
CREATE TABLE IF NOT EXISTS node_versions (
    id UUID PRIMARY KEY,
    node_id UUID NOT NULL REFERENCES project_nodes(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    field_changes JSONB NOT NULL,
    changed_fields JSONB NOT NULL,
    diff_summary TEXT,
    is_rollback BOOLEAN DEFAULT FALSE,
    rolled_back_from_version INT,
    change_source VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(node_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_versions_node ON node_versions(node_id, version_number DESC);

-- 4. 关联关系（链接到 CognitiveNode / Material / FlashCard / 其他项目节点）
CREATE TABLE IF NOT EXISTS node_links (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    source_node_id UUID NOT NULL REFERENCES project_nodes(id) ON DELETE CASCADE,
    link_type VARCHAR(30) NOT NULL,
    target_ref_id VARCHAR(64) NOT NULL,
    target_ref_type VARCHAR(20) NOT NULL,
    weight FLOAT DEFAULT 1.0,
    role VARCHAR(20) DEFAULT 'primary',
    label TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_links_source ON node_links(source_node_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON node_links(target_ref_type, target_ref_id);
CREATE INDEX IF NOT EXISTS idx_links_user_type ON node_links(user_id, link_type);

-- 5. @节点 引用（含跨项目引用 + 循环检测）
-- target_node_id 不带 FK（应用层在删除节点前 mark_broken_references）
CREATE TABLE IF NOT EXISTS node_references (
    id UUID PRIMARY KEY,
    source_node_id UUID NOT NULL REFERENCES project_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL,
    target_project_id UUID,
    reference_type VARCHAR(20) NOT NULL,
    is_broken BOOLEAN DEFAULT FALSE,
    broken_reason TEXT,
    creates_cycle BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refs_source ON node_references(source_node_id);
CREATE INDEX IF NOT EXISTS idx_refs_target ON node_references(target_node_id);
CREATE INDEX IF NOT EXISTS idx_refs_broken ON node_references(is_broken) WHERE is_broken = TRUE;

-- 6. 项目里程碑快照
CREATE TABLE IF NOT EXISTS project_milestones (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_name TEXT NOT NULL,
    snapshot_data JSONB NOT NULL,
    is_user_marked BOOLEAN DEFAULT TRUE,
    marked_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_milestones_project ON project_milestones(project_id, marked_at DESC);

-- 7. 项目模板
CREATE TABLE IF NOT EXISTS project_templates (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category VARCHAR(50),
    structure JSONB NOT NULL,
    placeholder_schema JSONB,
    is_system BOOLEAN DEFAULT FALSE,
    created_by_user_id VARCHAR(64),
    version INT NOT NULL DEFAULT 1,
    parent_template_id UUID,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_templates_category ON project_templates(category, is_system);
CREATE INDEX IF NOT EXISTS idx_templates_user ON project_templates(created_by_user_id) WHERE created_by_user_id IS NOT NULL;

-- ─────────────────────────────────────────────
-- PlanItemCompleted → ProjectNodeCompleted 幂等记录
-- (避免与 Planning 形成事件循环)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS project_plan_completed_log (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    plan_item_id VARCHAR(64) NOT NULL,
    project_node_id UUID,
    processed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(plan_item_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_completed_log_user ON project_plan_completed_log(user_id);
