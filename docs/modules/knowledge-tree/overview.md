# 知识树壳（Knowledge Tree Shell）

> 用户独立创作知识结构，叠加认知数据视图的可视化学习工具。

---

## 定位

知识树壳是「认知操作系统 + 场景壳层」架构中的场景壳层之一，负责：

1. 让用户以树/图形式自由组织和编辑知识结构。
2. 将用户创作的 `tree_nodes` 与认知数据系统的 `knowledge_nodes` / `cognitive_nodes` 解耦。
3. 通过显式链接把认知状态（掌握度、紧迫度、不确定性）投影到用户知识树上。
4. 提供基于知识图谱的对话探索与 AI 辅助扩展能力。

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
| 跨壳材料聚合 | 闪卡、阅读标注/笔记、练习会话/错题、计划项展示 + 创建 + source_ref 回写 | ✅ 已实现 |
| AI 知识扩展 | 基于节点自动生成子节点、前置/关联节点 | ✅ 已实现 |
| 图谱对话 | 围绕知识点进行苏格拉底式对话探索 | ✅ 已实现 |

## 后端架构

```
frontend / TestClient
      │
      ▼
┌─────────────────────────────────────────┐
│ app/api/trees.py                        │  ← /api/trees 统一入口
│ app/api/knowledge_graph*.py             │  ← /api/knowledge-graph 认知图谱入口
│ app/api/learning/explain.py             │  ← /api/learning/explain 通用解释
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│ app/services/knowledge_tree/            │  ← 领域服务
│   tree_service.py         — 知识树 CRUD
│   tree_node_service.py    — 节点 CRUD、移动、排序
│   tree_edge_service.py    — 边 CRUD
│   cognitive_link_service.py — 认知节点关联
│   ai_expansion_service.py — AI 节点扩展
│   conversation_service.py — 图谱对话生命周期
│   navigation_service.py   — 导航节点管理
│   message_service.py      — 图谱对话消息
│   knowledge_node_service.py — 知识点 CRUD（认知图谱）
│   event_bus_service.py    — 事件发布
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│ DB + Event Bus                          │
└─────────────────────────────────────────┘
```

## API 概览

### 知识树端点（稳定）

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
| GET | `/api/trees/{tree_id}/nodes/{node_id}/materials` | 跨壳材料聚合 |
| POST | `/api/trees/{tree_id}/nodes/{node_id}/source-refs` | 追加 source_ref（去重） |

### 认知图谱端点（新增 / 迁移中）

统一前缀：`/api/knowledge-graph`

| 方法 | 路由 | 功能 |
|------|------|------|
| GET | `/api/knowledge-graph/nodes` | 列出知识点 |
| POST | `/api/knowledge-graph/nodes` | 创建知识点 |
| GET/PUT/DELETE | `/api/knowledge-graph/nodes/{node_id}` | 知识点详情/更新/删除 |
| GET | `/api/knowledge-graph/nodes/{node_id}/subtree` | 知识点子树 |
| GET | `/api/knowledge-graph/nodes/{node_id}/conversations` | 关联对话 |
| POST/DELETE | `/api/knowledge-graph/nodes/{node_id}/prerequisites/{prereq_id}` | 前置关系管理 |
| POST | `/api/knowledge-graph/nodes/{node_id}/associates` | 添加关联 |
| POST | `/api/knowledge-graph/nodes/{node_id}/reorder` | 子节点排序 |
| GET/POST/PUT/DELETE | `/api/knowledge-graph/conversations` | 图谱对话 CRUD |
| GET/POST | `/api/knowledge-graph/navigation` | 导航节点管理 |
| GET/POST/PUT/DELETE | `/api/knowledge-graph/messages` | 对话消息管理 |
| POST | `/api/knowledge-graph/ai/expand/{node_id}` | AI 扩展节点 |
| POST | `/api/knowledge-graph/ai/edit/{node_id}` | AI 编辑节点 |
| POST | `/api/knowledge-graph/ai/chat/{node_id}` | 图谱对话初始化 |
| POST | `/api/knowledge-graph/ai/generate` | 生成知识图谱 |
| GET | `/api/knowledge-graph/ai/recommendation` | 知识点推荐 |

### 通用学习解释

| 方法 | 路由 | 功能 |
|------|------|------|
| POST | `/api/learning/explain` | 通用 AI 解释（选中文字/知识点/对话式） |

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
| `TreeNodeDetailPanel` | 节点详情、认知视图、跨壳材料聚合与创建入口 |
| `Create*Dialog` | 闪卡/阅读笔记/练习会话/计划项创建弹窗 |
| `LayerPanel` | 层级导航 |
| `ContextMenu` | 节点右键菜单 |
| `StatusBar` | 统计与筛选 |
| `useKnowledgeTree` | 集中式状态管理 hook |
| `knowledge-trees-api` | `/api/trees` API 客户端 |
| `knowledge-graph-api` | `/api/knowledge-graph` API 客户端 |
| `GraphDialoguePage` | 图谱对话页面 |
| `KnowledgeTreeRecommendBanner` | 对话页知识点推荐 |

## 相关文档

- [架构决策记录](/docs/adr/0022-knowledge-tree-shell.md)
