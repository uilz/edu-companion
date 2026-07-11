# ADR 0022: 知识树壳 — 用户创作结构与认知数据视图解耦

## 状态

已接受 / 已实现

## 背景

旧版「知识树」直接操作认知节点（`knowledge_nodes` / `cognitive_nodes`），导致两个问题：

1. **用户失去创作自由**：用户调整知识结构（增删节点、改层级）会直接影响底层认知评估数据。
2. **可视化与评估耦合**：同一批节点既要表达「用户理解的知识结构」，又要承载「AI 评估的掌握状态」，字段和语义混杂。

因此引入独立的知识树壳（Knowledge Tree Shell），将「用户创作结构」与「认知数据视图」完全分离。

## 决策

### 1. 四实体解耦

新增四个独立实体：

| 实体 | 职责 |
|------|------|
| `knowledge_trees` | 用户创建的知识树元数据（标题、类型、默认视图等） |
| `tree_nodes` | 用户创作的知识树节点（标签、层级、颜色、emoji 等） |
| `tree_edges` | 用户/系统创建的节点间关系（父子、前置、相关等） |
| `tree_node_cognitive_links` | 树节点与认知节点的显式映射 |

理由：用户结构可以独立增删改，认知系统只需维护投影，两侧通过显式链接同步。

### 2. 认知状态可视化编码

节点样式由关联认知节点的投影驱动：

- **颜色** = 掌握度（proficiency）
- **大小** = 紧迫度（urgency）
- **光晕** = 不确定性（uncertainty）

理由：三种指标分别对应视觉通道的色、形、辉度，互不干扰，用户可快速识别复习优先级。

### 3. 图引擎采用 @antv/g6

使用 `@antv/g6` 统一实现树视图、力导向图、思维导图等布局。

理由：成熟图引擎，支持大规模节点、交互丰富、布局可插拔，避免自研布局带来的维护成本。

### 4. API 路径统一为 `/api/trees`

前端不再调用旧的 `/api/knowledge-tree/...` 结构接口，统一使用 `/api/trees` 下的树/节点/边/关联/视图/导入端点。

理由：路径语义清晰，与四实体模型对齐，便于后续版本演进。

### 5. 事件协议补齐

知识树壳发布以下事件供认知 OS 内核、秘书编排器等消费：

- `TreeNodeCreated`
- `TreeNodeUpdated`
- `TreeNodeMoved`
- `TreeNodeDeleted`
- `TreeEdgeCreated`
- `TreeEdgeDeleted`
- `TreeNodeLinkedToCognitiveNode`
- `TreeNodeUnlinkedFromCognitiveNode`
- `TreeViewChanged`

同时订阅 `CognitiveStateChanged`，刷新已关联节点的认知视图。

理由：事件是跨壳联动的唯一通道，避免直接调用其他壳内部服务。

### 6. 前端状态集中管理

新建 `useKnowledgeTree` hook 集中管理树列表、选中树、节点/边、视图模式、视口状态。

理由：知识树页面涉及多个交互源（图点击、层级面板、详情面板、对话框），集中状态可避免 prop drilling 和不一致。

## 影响

- 知识树从「认知数据的可视化」升级为「用户独立创作 + 认知数据叠加」的复合壳层。
- 旧版 `/api/knowledge-tree/graph/...` 结构接口不再被知识树页使用，仅保留给对话推荐等历史路径。
- 秘书编排器、规划壳、练习壳后续可通过事件协议感知用户知识结构变化。

## 实现要点

### 后端

- `backend/app/services/knowledge_tree/tree_service.py`：知识树 CRUD。
- `backend/app/services/knowledge_tree/tree_node_service.py`：节点 CRUD、移动、排序。
- `backend/app/services/knowledge_tree/tree_edge_service.py`：边 CRUD。
- `backend/app/services/knowledge_tree/cognitive_link_service.py`：认知节点关联。
- `backend/app/api/trees.py`：`/api/trees` 路由，含投影查询。
- `backend/app/infrastructure/db/models/knowledge_tree.py`：四实体 ORM 模型。
- Alembic 迁移 `47b28cb8e774_add_knowledge_tree_tables.py`。

### 前端

- `frontend/src/lib/api/knowledge-trees-api.ts`：`/api/trees` API 客户端与类型。
- `frontend/src/hooks/knowledge-tree/useKnowledgeTree.ts`：集中状态管理。
- `frontend/src/components/knowledge-tree/KnowledgeTreeGraph.tsx`：G6 图组件，支持树/图双模式。
- `frontend/src/components/knowledge-tree/TreeNodeDetailPanel.tsx`：节点详情 + 认知视图 + 材料聚合预留。
- `frontend/src/components/knowledge-tree/KnowledgeTreePage.tsx`：页面集成。
- `frontend/src/app/knowledge-tree/page.tsx`：独立路由入口。

## 验证

- `test_knowledge_tree_services.py`：18/18 通过。
- `test_knowledge_tree_api.py`：8/8 通过。
- 前端 `npx tsc --noEmit`：无类型错误。
- `rebuild.sh`：前端构建、后端启动、admin 构建均成功，服务全部就绪。
- 浏览器端到端验证：可创建知识树、添加根节点、节点在 G6 树视图中渲染。

## 相关文档

- `docs/temp/task0024-knowledge-tree-shell-design.md`
- `docs/temp/task0024-knowledge-tree-shell-implementation-plan.md`
- `docs/modules/knowledge-tree/overview.md`
