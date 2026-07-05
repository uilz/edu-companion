# Project 数据模型

> Project 模块的数据结构（节点、版本、关联、模板）。

**ADR**：[`docs/adr/0001-project-based-exploration.md`](../../adr/0001-project-based-exploration.md)

---

## 1. 项目表 `projects`

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    template_id UUID,                          -- 来自哪个模板（NULL = 用户自由创建）
    template_version INT,                      -- 模板版本号
    status VARCHAR(20) DEFAULT 'active',       -- active / archived / completed
    tags JSONB DEFAULT '[]',                   -- 标签
    node_count INT DEFAULT 0,
    completed_node_count INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(user_id, status);
```

---

## 2. 节点表 `project_nodes`（统一表，type 区分）

```sql
CREATE TABLE project_nodes (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES project_nodes(id) ON DELETE CASCADE,
    type SMALLINT NOT NULL,                    -- 1-7 (大纲/文本/数据表/对比/代码/附件/聚合)
    title TEXT NOT NULL,
    description TEXT,
    order_in_parent INT DEFAULT 0,
    tags JSONB DEFAULT '[]',

    -- 类型特定内容
    content JSONB,                             -- 文本节点：富文本
    rows JSONB,                                -- 数据表节点
    columns JSONB,                             -- 对比节点（每列独立富文本）
    language VARCHAR(20),                      -- 代码节点
    code TEXT,                                 -- 代码节点
    explanation TEXT,                          -- 代码节点
    material_id VARCHAR(64),                   -- 附件节点
    chunk_id_range JSONB,                      -- 附件节点
    fragments JSONB,                           -- 聚合节点

    -- 关联
    linked_node_ids JSONB DEFAULT '[]',        -- 关联的 CognitiveNode
    linked_material_ids JSONB DEFAULT '[]',    -- 关联的 Material
    linked_card_ids JSONB DEFAULT '[]',        -- 关联的 FlashCard
    cross_project_refs JSONB DEFAULT '[]',     -- 跨项目节点引用

    -- 元数据
    version INT NOT NULL DEFAULT 1,
    is_archived BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_nodes_project ON project_nodes(project_id);
CREATE INDEX idx_nodes_parent ON project_nodes(parent_id);
CREATE INDEX idx_nodes_type ON project_nodes(user_id, type);
CREATE INDEX idx_nodes_archived ON project_nodes(user_id, is_archived);
CREATE INDEX idx_nodes_completed ON project_nodes(project_id, completed_at);
```

---

## 3. 节点版本历史表 `node_versions`

```sql
CREATE TABLE node_versions (
    id UUID PRIMARY KEY,
    node_id UUID NOT NULL REFERENCES project_nodes(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    field_changes JSONB NOT NULL,              -- {"title": {"old": ..., "new": ...}, ...}
    changed_fields JSONB NOT NULL,             -- ["title", "content"] - 字段级粒度
    diff_summary TEXT,                         -- 人类可读的变更摘要
    is_rollback BOOLEAN DEFAULT FALSE,
    rolled_back_from_version INT,              -- 如果是回滚，记录从哪个版本回滚
    change_source VARCHAR(20) NOT NULL,        -- user_edit / api / rollback / system
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE(node_id, version_number)
);

CREATE INDEX idx_versions_node ON node_versions(node_id, version_number DESC);
```

**字段级粒度**：

- `title` / `description` / `content` / `tags` 等字段**各自独立**维护版本
- 一次修改只对**被修改的字段**入栈新版本
- 未修改字段的版本号不变

---

## 4. 关联关系表 `node_links`

```sql
CREATE TABLE node_links (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    source_node_id UUID NOT NULL REFERENCES project_nodes(id) ON DELETE CASCADE,
    link_type VARCHAR(30) NOT NULL,            -- linked_node / linked_material / linked_card / cross_project
    target_ref_id VARCHAR(64) NOT NULL,        -- CognitiveNode.id / Material.id / FlashCard.id / 其他项目节点 id
    target_ref_type VARCHAR(20) NOT NULL,      -- cognitive_node / material / flashcard / project_node
    weight FLOAT DEFAULT 1.0,                  -- 主 1.0 / 次 0.3
    role VARCHAR(20) DEFAULT 'primary',        -- primary / secondary
    label TEXT,                                -- 用户自定义标签
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_links_source ON node_links(source_node_id);
CREATE INDEX idx_links_target ON node_links(target_ref_type, target_ref_id);
CREATE INDEX idx_links_user_type ON node_links(user_id, link_type);
```

---

## 5. 项目里程碑快照表 `project_milestones`

```sql
CREATE TABLE project_milestones (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_name TEXT NOT NULL,
    snapshot_data JSONB NOT NULL,               -- {"node_count": ..., "completed_count": ..., "link_count": ...}
    is_user_marked BOOLEAN DEFAULT TRUE,        -- 用户手动标记 vs 系统自动检测
    marked_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_milestones_project ON project_milestones(project_id, marked_at DESC);
```

---

## 6. 引用关系表 `node_references`（@节点 引用）

```sql
CREATE TABLE node_references (
    id UUID PRIMARY KEY,
    source_node_id UUID NOT NULL REFERENCES project_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES project_nodes(id) ON DELETE CASCADE,
    target_project_id UUID,                    -- 跨项目时记录
    reference_type VARCHAR(20) NOT NULL,       -- inline（内容内引用）/ link（链接复制）/ embed（嵌入）
    is_broken BOOLEAN DEFAULT FALSE,           -- 目标节点被删除/归档时为 true
    broken_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refs_source ON node_references(source_node_id);
CREATE INDEX idx_refs_target ON node_references(target_node_id);
```

---

## 7. 项目模板表 `project_templates`

```sql
CREATE TABLE project_templates (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category VARCHAR(50),                       -- 编程语言 / 数学 / 研究 / 阅读
    structure JSONB NOT NULL,                  -- 节点树形结构（包含占位符）
    placeholder_schema JSONB,                  -- 占位符定义（用户需填充）
    is_system BOOLEAN DEFAULT FALSE,           -- 系统预置 vs 用户自建
    created_by_user_id VARCHAR(64),            -- NULL 表示系统预置
    version INT NOT NULL DEFAULT 1,
    parent_template_id UUID,                   -- 衍生自哪个模板
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_templates_category ON project_templates(category, is_system);
```

---

## 8. 字段说明

### 8.1 节点类型 `type`

| 值 | 类型 | 关键字段 |
|---|------|---------|
| 1 | 大纲节点 | `parent_id` / `child_node_ids` 隐式 |
| 2 | 文本节点 | `content` (JSONB 富文本) |
| 3 | 数据表节点 | `rows` / `columns` (JSONB) |
| 4 | 对比节点 | `columns` (每列独立 JSONB) |
| 5 | 代码节点 | `language` / `code` / `explanation` |
| 6 | 附件节点 | `material_id` / `chunk_id_range` |
| 7 | 聚合节点 | `fragments` (引用源节点 + offset) |

### 8.2 节点状态 `status`

- `active` — 活跃节点
- `archived` — 归档节点（不显示主视图）
- `completed` — 已完成节点（与 `completed_at` 配对）

### 8.3 关联角色 `role`

- `primary` — 主关联（weight 1.0）
- `secondary` — 次关联（weight 0.3）

### 8.4 版本变更来源 `change_source`

- `user_edit` — 用户手动编辑
- `api` — 程序化 API 调用
- `rollback` — 用户回滚
- `system` — 系统自动（如自动归档）

---

## 9. 数据归属总览

| 归属模块 | 存储内容 |
|---------|---------|
| **本模块** | 项目元数据、节点内容、版本快照、关联、引用、里程碑、模板 |
| `CognitiveNode` | 知识点状态、Belief、Scheduling |
| `Material` | 阅读材料文件 |
| `FlashCard` | 复习卡内容 |
| `ErrorBookEntry` | 错题记录 |
| `ExplainCard` | 对话标注 |
| 全局事件流 | 项目级事件（创建/完成/里程碑）|
