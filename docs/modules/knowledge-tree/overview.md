# 知识树壳（Knowledge Tree Shell）

> 用户独立创作知识结构，叠加认知数据视图的可视化学习工具。

---

## 定位

知识树壳是「认知操作系统 + 场景壳层」架构中的场景壳层之一，负责：

1. 让用户以树/图形式自由组织和编辑知识结构。
2. 将用户创作的 `tree_nodes` 与认知数据系统的 `cognitive_nodes` 解耦。
3. 通过显式链接把认知状态（掌握度、紧迫度、不确定性）投影到用户知识树上。

## 核心实体

| 实体 | 说明 | 对应表 |
|------|------|--------|
| Knowledge Tree | 知识树元数据 | `knowledge_trees` |
| Tree Node | 用户创作的节点 | `tree_nodes` |
| Tree Edge | 节点间关系 | `tree_edges` |
| Cognitive Link | 树节点 ↔ 认知节点映射 | `tree_node_cognitive_links` |

## 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 树 CRUD | 创建、编辑、归档、删除知识树 | ✅ 已实现 |
| 节点 CRUD | 创建、编辑、移动、删除节点 | ✅ 已实现 |
| 边 CRUD | 创建、删除节点间关系 | ✅ 已实现 |
| 认知关联 | 树节点关联/解除认知节点 | ✅ 已实现 |
| 认知视图 | 颜色=掌握度、大小=紧迫度、光晕=不确定性 | ✅ 已实现 |
| 树/图双视图 | G6 树视图与力导向图视图切换 | ✅ 已实现 |
| 视图状态 | 保存/恢复缩放、平移、布局 | ✅ 已实现 |
| 跨壳材料聚合 | 闪卡、笔记、错题、计划入口（预留） | 🔄 待后续壳层对接 |

## API 概览

统一前缀：`/api/trees`

| 方法 | 路由 | 功能 |
|------|------|------|
| GET | `/api/trees` | 列表 |
| POST | `/api/trees` | 创建树 |
| GET | `/api/trees/{tree_id}` | 获取树 |
| PATCH | `/api/trees/{tree_id}` | 更新树 |
| DELETE | `/api/trees/{tree_id}` | 删除树 |
| GET | `/api/trees/{tree_id}/nodes` | 节点列表（含认知视图） |
| POST | `/api/trees/{tree_id}/nodes` | 创建节点 |
| PATCH | `/api/trees/{tree_id}/nodes/{node_id}` | 更新节点 |
| POST | `/api/trees/{tree_id}/nodes/{node_id}/move` | 移动节点 |
| DELETE | `/api/trees/{tree_id}/nodes/{node_id}` | 删除节点 |
| GET | `/api/trees/{tree_id}/edges` | 边列表 |
| POST | `/api/trees/{tree_id}/edges` | 创建边 |
| DELETE | `/api/trees/{tree_id}/edges/{edge_id}` | 删除边 |
| POST | `/api/trees/{tree_id}/nodes/{node_id}/link-cognitive` | 关联认知节点 |
| DELETE | `/api/trees/{tree_id}/nodes/{node_id}/link-cognitive/{cognitive_node_id}` | 解除关联 |
| GET | `/api/trees/{tree_id}/viewport` | 获取视图状态 |
| PUT | `/api/trees/{tree_id}/viewport` | 保存视图状态 |
| GET | `/api/trees/cognitive-nodes/search` | 搜索认知节点 |
| GET | `/api/trees/cognitive-nodes/{id}/projection` | 认知节点投影 |

## 事件协议

### 发出的事件

- `TreeNodeCreated`
- `TreeNodeUpdated`
- `TreeNodeMoved`
- `TreeNodeDeleted`
- `TreeEdgeCreated`
- `TreeEdgeDeleted`
- `TreeNodeLinkedToCognitiveNode`
- `TreeNodeUnlinkedFromCognitiveNode`
- `TreeViewChanged`

### 消费的事件

- `CognitiveStateChanged`：刷新已关联节点的认知视图。

## 前端组件

| 组件 | 职责 |
|------|------|
| `KnowledgeTreePage` | 页面集成与状态协调 |
| `KnowledgeTreeGraph` | G6 图渲染与交互 |
| `TreeNodeDetailPanel` | 节点详情与认知视图 |
| `LayerPanel` | 层级导航 |
| `ContextMenu` | 节点右键菜单 |
| `StatusBar` | 统计与筛选 |
| `useKnowledgeTree` | 集中式状态管理 hook |
| `knowledge-trees-api` | `/api/trees` API 客户端 |

## 相关文档

- [设计文档](/docs/temp/task0024-knowledge-tree-shell-design.md)
- [实施计划](/docs/temp/task0024-knowledge-tree-shell-implementation-plan.md)
- [架构决策记录](/docs/adr/0022-knowledge-tree-shell.md)
