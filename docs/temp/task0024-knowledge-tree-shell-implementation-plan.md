# Task 0024: 知识树壳实施计划 v1.0

> 版本：v1.0
> 状态：实施中
> 决策：严格按设计文档重构，新建 `knowledge_trees / tree_nodes / tree_edges / tree_node_cognitive_links` 四张表，与认知数据系统完全解耦。

---

## 1. 目标与范围

### 1.1 目标
将知识树壳从「直接操作 cognitive nodes」改造为「用户创作结构 + 认知数据视图」双轨架构，满足设计文档 [task0024-knowledge-tree-shell-design.md](task0024-knowledge-tree-shell-design.md) 的全部要求。

### 1.2 范围
- 数据库：新建 4 张表，1 个迁移文件。
- 后端：新建/重构 `knowledge_tree` 服务层、API 路由、事件发布。
- 前端：重构 `/knowledge-tree` 页面与组件，接入新 API。
- 事件：补齐 `TreeNode*` / `TreeEdge*` / `TreeNodeLinkedToCognitiveNode` 等事件发布。
- 测试：单元测试 + 集成测试 + 端到端验证。
- 文档：更新 ADR、模块文档、API 文档。

### 1.3 不在本次范围
- 认知状态计算逻辑改造（认知 OS 内核）。
- 秘书编排器对知识树事件的消费（后续迭代）。
- 复杂的图布局算法自研（优先使用 @antv/g6）。

---

## 2. 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 用户树节点与认知节点 | **完全分离** | 设计文档决策 1，满足用户独立创作知识结构的需求 |
| 可视化编码 | **颜色=掌握度，大小=紧迫度，光晕=不确定性** | 设计文档决策 2 |
| 图引擎 | **@antv/g6** | 设计文档决策 3，树图/网图双模式，性能成熟 |
| 边表 | **tree_edges 独立** | 设计文档决策 4 |
| 数据迁移 | **从零开始 + 提供导入脚本** | 当前开发阶段不兼容旧数据，旧 cognitive 树结构可后续手动迁移 |

---

## 3. 数据库 Schema

### 3.1 knowledge_trees
```sql
CREATE TABLE knowledge_trees (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT '我的知识树',
    description TEXT NOT NULL DEFAULT '',
    tree_type VARCHAR(32) NOT NULL DEFAULT 'project', -- project | domain | map
    root_node_id VARCHAR(32),
    default_view_mode VARCHAR(32) NOT NULL DEFAULT 'tree', -- tree | graph | split
    default_layout VARCHAR(32) NOT NULL DEFAULT 'layered', -- layered | force | radial | manual
    tags JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'active', -- active | archived | deleted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INT NOT NULL DEFAULT 0
);
CREATE INDEX idx_knowledge_trees_user ON knowledge_trees(user_id);
CREATE INDEX idx_knowledge_trees_user_status ON knowledge_trees(user_id, status);
```

### 3.2 tree_nodes
```sql
CREATE TABLE tree_nodes (
    id VARCHAR(32) PRIMARY KEY,
    tree_id VARCHAR(32) NOT NULL REFERENCES knowledge_trees(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    label VARCHAR(255) NOT NULL,
    node_type VARCHAR(32) NOT NULL DEFAULT 'concept', -- topic | concept | skill | material | question | card | note | milestone
    parent_id VARCHAR(32) REFERENCES tree_nodes(id) ON DELETE CASCADE,
    children_order JSONB NOT NULL DEFAULT '[]',
    order_index INT NOT NULL DEFAULT 0,
    color VARCHAR(16) NOT NULL DEFAULT '',
    emoji VARCHAR(8) NOT NULL DEFAULT '',
    icon_url VARCHAR(512) NOT NULL DEFAULT '',
    position JSONB NOT NULL DEFAULT '{}', -- {x, y} for graph mode
    source_refs JSONB NOT NULL DEFAULT '[]',
    tags JSONB NOT NULL DEFAULT '[]',
    brief TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'active', -- active | collapsed | archived | deleted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INT NOT NULL DEFAULT 0
);
CREATE INDEX idx_tree_nodes_tree ON tree_nodes(tree_id);
CREATE INDEX idx_tree_nodes_user ON tree_nodes(user_id);
CREATE INDEX idx_tree_nodes_parent ON tree_nodes(parent_id);
CREATE INDEX idx_tree_nodes_tree_status ON tree_nodes(tree_id, status);
```

### 3.3 tree_edges
```sql
CREATE TABLE tree_edges (
    id VARCHAR(32) PRIMARY KEY,
    tree_id VARCHAR(32) NOT NULL REFERENCES knowledge_trees(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    source_node_id VARCHAR(32) NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    target_node_id VARCHAR(32) NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    edge_type VARCHAR(32) NOT NULL DEFAULT 'parent_child', -- parent_child | prerequisite | related | sequence | reference
    strength FLOAT NOT NULL DEFAULT 1.0,
    is_user_confirmed BOOLEAN NOT NULL DEFAULT TRUE,
    is_inferred BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tree_id, source_node_id, target_node_id, edge_type)
);
CREATE INDEX idx_tree_edges_tree ON tree_edges(tree_id);
CREATE INDEX idx_tree_edges_source ON tree_edges(source_node_id);
CREATE INDEX idx_tree_edges_target ON tree_edges(target_node_id);
```

### 3.4 tree_node_cognitive_links
```sql
CREATE TABLE tree_node_cognitive_links (
    id VARCHAR(32) PRIMARY KEY,
    tree_id VARCHAR(32) NOT NULL REFERENCES knowledge_trees(id) ON DELETE CASCADE,
    tree_node_id VARCHAR(32) NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    cognitive_node_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    link_role VARCHAR(32) NOT NULL DEFAULT 'primary', -- primary | reference | derived
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tree_id, tree_node_id, cognitive_node_id)
);
CREATE INDEX idx_tree_cognitive_links_tree ON tree_node_cognitive_links(tree_id);
CREATE INDEX idx_tree_cognitive_links_tree_node ON tree_node_cognitive_links(tree_node_id);
CREATE INDEX idx_tree_cognitive_links_cognitive ON tree_node_cognitive_links(cognitive_node_id);
CREATE INDEX idx_tree_cognitive_links_user ON tree_node_cognitive_links(user_id);
```

---

## 4. 后端服务拆分

### 4.1 保留与废弃
| 现状 | 处理 |
|------|------|
| `knowledge_node_service.py` | **废弃**，由 `tree_service.py` / `tree_node_service.py` 替代 |
| `conversation_service.py` | **保留**，但conversation关联从cognitive node改为tree_node（可选） |
| `navigation_service.py` | **保留**，负责导航文件系统 |
| `message_service.py` | **保留** |
| `event_bus_service.py` | **保留**，扩展事件类型 |

### 4.2 新建服务
- `backend/app/services/knowledge_tree/tree_service.py` — 知识树 CRUD
- `backend/app/services/knowledge_tree/tree_node_service.py` — 树节点 CRUD + 移动 + 排序
- `backend/app/services/knowledge_tree/tree_edge_service.py` — 树边 CRUD
- `backend/app/services/knowledge_tree/cognitive_link_service.py` — 树节点与认知节点关联
- `backend/app/services/knowledge_tree/node_material_service.py` — 跨壳材料聚合查询
- `backend/app/services/knowledge_tree/viewport_service.py` — 视图状态保存

### 4.3 API 路由调整
- 保留 `/api/knowledge-tree/nodes` 作为兼容层或移除？**决定移除**，前端统一使用 `/api/knowledge-trees/...`。
- 新增 `/api/knowledge-trees` 路由模块。
- 旧 `/api/knowledge-tree/...` 路由保留 conversation / navigation / message 子路径（这些不属于知识树核心结构）。

---

## 5. 事件发布

### 5.1 需要发布的事件
| 事件 | 触发场景 |
|------|----------|
| `TreeNodeCreated` | 创建树节点（含创建树时的根节点） |
| `TreeNodeUpdated` | 更新标签/颜色/位置 |
| `TreeNodeMoved` | 拖拽改变父节点或位置 |
| `TreeNodeDeleted` | 删除树节点 |
| `TreeEdgeCreated` | 创建边 |
| `TreeEdgeDeleted` | 删除边 |
| `TreeNodeLinkedToCognitiveNode` | 关联认知节点 |
| `TreeNodeUnlinkedFromCognitiveNode` | 解除关联 |
| `TreeViewChanged` | 保存视图状态 |
| `TreeImportedContent` | 从其他壳导入内容 |

### 5.2 事件总线集成
- 通过 `container.event_bus.publish()` 同步或异步发布。
- 知识树壳订阅 `CognitiveStateChanged`，刷新节点认知视图。

---

## 6. 前端改造

### 6.1 技术栈
- `@antv/g6` 作为图引擎
- Zustand 管理 viewport / filters / selectedNode
- Server-Sent Events (SSE) 订阅 `CognitiveStateChanged`

### 6.2 组件调整
| 组件 | 调整 |
|------|------|
| `KnowledgeTreePage.tsx` | 接入新 API，管理 tree / nodes / edges / viewport 状态 |
| `KnowledgeTreeGraph.tsx` | 新增 G6 图组件 |
| `TreeNodeDetailPanel.tsx` | 新增节点详情：认知视图 + 材料聚合 |
| `ContextMenu.tsx` | 新增「关联认知节点」「发起练习」「生成闪卡」「创建计划」 |
| `LayerPanel.tsx` | 筛选器、图例、视图模式切换 |
| `TopBar.tsx` | 树切换、新建树 |

### 6.3 API 客户端
- 新建 `frontend/src/lib/api/knowledge-trees-api.ts`，逐步替代 `knowledge-tree-api.ts`。

---

## 7. 数据迁移

当前为开发阶段，不保留旧知识结构数据。
- 新增表为空。
- 提供手动导入脚本（可选）：将旧 `knowledge_nodes` 中 `created_by='user'` 的节点导入为 `tree_nodes`，并建立与认知节点的 `primary` 链接。
- 该脚本不自动运行，作为后续工具保留。

---

## 8. 测试策略

| 类型 | 内容 |
|------|------|
| 单元测试 | tree_service / tree_node_service / tree_edge_service / cognitive_link_service 的 CRUD 和事件发布 |
| 集成测试 | API 端到端：创建树 → 创建节点 → 创建边 → 关联认知节点 → 查询认知视图 |
| 事件测试 | 验证 TreeNodeCreated / TreeEdgeCreated / TreeNodeLinkedToCognitiveNode 被正确发布和消费 |
| 前端测试 | 组件渲染、交互、API 调用 |
| 回归测试 | `rebuild.sh` 全量运行 |

---

## 9. 垂直切片（子任务）

### 切片 1：Schema 与迁移（2-3h）✅
- 创建 `knowledge_tree_schema.sql`
- 创建 Alembic 迁移 `47b28cb8e774_add_knowledge_tree_tables.py`
- 新增 ORM 模型 `knowledge_tree.py`
- 验收：迁移可 applied / reverted，表结构正确

### 切片 2：后端核心服务与事件（3-4h）✅
- 实现 tree_service / tree_node_service / tree_edge_service / cognitive_link_service
- 发布全部知识树事件
- 修复事件发布：统一使用 `publish_event_safe`，同步/异步上下文自适应
- 验收：`tests/test_knowledge_tree_services.py` 18/18 通过

### 切片 3：后端 API 与投影查询（2-3h）✅
- 新建 `/api/trees` 路由 `backend/app/api/trees.py`
- 实现 Tree/Node/Edge/Link/Viewport/Import/Cognitive 投影查询
- 认知视图可视化编码：颜色=掌握度，大小=紧迫度，光晕=不确定性
- 验收：`tests/test_knowledge_tree_api.py` 8/8 通过

### 切片 4：前端核心重构（3-4h）
- 接入新 API
- 实现 G6 树/图双模式
- 实现节点详情面板
- 验收：页面可加载、创建节点、显示认知视图

### 切片 5：集成验证与文档（2-3h）
- 编写集成测试
- `rebuild.sh` 验证
- 创建 ADR、更新设计文档
- 验收：全量测试通过，git 提交

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 与现有 cognitive nodes 命名冲突 | 代码理解混乱 | 在文档和代码中明确 `knowledge_nodes` = cognitive nodes；新增 `tree_nodes` |
| 前端改动大 | 延期 | 分切片推进，优先保证后端 API 和基础可视化 |
| G6 与现有组件库冲突 | 构建失败 | 先原型验证再全面替换 |
| 事件订阅遗漏 | 认知视图不更新 | 编写事件契约测试 |

---

## 11. 验收标准

- [x] 可创建/删除/归档知识树
- [x] 可在树上创建/编辑/移动/删除节点
- [x] 可创建/删除边
- [x] 可将树节点关联/解除关联到认知节点
- [x] 节点显示掌握度（颜色）、紧迫度（大小）、不确定性（光晕）
- [ ] 节点详情展示关联材料（闪卡、错题、笔记、计划项等）— 后端基础结构已就绪，待跨壳查询补齐
- [ ] 支持树/图/分屏三种视图 — 前端待实现
- [x] 视图状态可保存
- [x] 所有相关事件正确发布
- [x] `rebuild.sh` 通过，后端 API/服务测试通过
