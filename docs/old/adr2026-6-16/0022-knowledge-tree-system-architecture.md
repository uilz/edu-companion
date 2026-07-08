# ADR 0022: 知识树系统架构全景分析 (Round 4 基线)

> 状态: 分析完成  
> 日期: 2026-06-17  
> 轮次: 第四轮重构基线  
> 范围: 后端知识服务 + 前端知识树 + 认知域 + 对话系统 + 秘书联动 + 练习联动

---

## 目录

1. [系统总览](#1-系统总览)
2. [数据模型与存储](#2-数据模型与存储)
3. [后端模块架构](#3-后端模块架构)
4. [前端模块架构](#4-前端模块架构)
5. [API 路由全景](#5-api-路由全景)
6. [运行时流程与数据流](#6-运行时流程与数据流)
7. [模块间联动关系](#7-模块间联动关系)
8. [当前架构问题与优化方向](#8-当前架构问题与优化方向)

---

## 1. 系统总览

### 1.1 知识树系统的双重身份

知识树系统在架构中承担两个核心角色：

| 角色 | 载体 | 职责 |
|------|------|------|
| **结构/可视化** | `KnowledgeGraph` + `KGNode` + `KGEdge` | 可编辑的知识主题有向图，表示学习依赖关系，前端可视化呈现 |
| **认知状态追踪** | `CognitiveNode` (15+子系统) | 贝叶斯信念(Beta分布)、ACT-R激活、练习历史、掌握度追踪 |

**关键区分**：`KGNode` 是知识结构的"骨架"，`CognitiveNode` 是学习状态的"血液"。两者通过桥接层 (`knowledge_trace.py`, `_sync_graph_to_cognitive()`) 保持同步。

### 1.2 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│  前端 Layer                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ 页面路由  │  │ Zustand  │  │  React   │  │  API 调用  │  │
│  │ /knowledge│  │  Stores  │  │  Hooks   │  │  Layer     │  │
│  │ -tree     │  │          │  │          │  │            │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  HTTP/SSE                                                   │
├─────────────────────────────────────────────────────────────┤
│  后端 Layer                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API 路由 (5 组)                                      │   │
│  │  /api/knowledge/graph/*  /api/conversations/tree/*   │   │
│  │  /api/knowledge/*        /api/learning/*              │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  服务层 (knowledge/)                                  │   │
│  │  tree_service  tree_directory  tree_messages         │   │
│  │  tree_sub_branch  cognitive_queries  cognitive_sync  │   │
│  │  knowledge_graph_service  knowledge_state            │   │
│  │  zpd_scheduler  knowledge_expander                   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  领域层 (domain/)                                     │   │
│  │  cognitive/  knowledge/  secretary/  conversation/   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  基础设施层 (infrastructure/)                         │   │
│  │  DB(PG+pgvector)  LLM  EventBus  ToolRepository      │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  共享层 (shared/)                                     │   │
│  │  protocols  knowledge_trace  events  constants       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 数据模型与存储

### 2.1 核心存储: `conversation_user_meta` (JSONB)

所有知识树相关数据存储在 PostgreSQL 的 `conversation_user_meta` 表，以 JSONB 格式存储完整的 `UserData` 对象。

```python
# UserData (app/schemas/conversation.py)
class UserData(BaseModel):
    user_id: str
    # 旧层级模型 (逐步废弃)
    partitions: dict[str, Partition]
    domains: dict[str, Domain]
    topics: dict[str, Topic]
    conversations: dict[str, Conversation]
    # 知识图谱
    knowledge_graphs: dict[str, KnowledgeGraph]  # key=partition_id
    # 新统一目录模型
    directory_nodes: dict[str, DirectoryNode]     # 取代旧四层模型
    # 消息
    nodes: dict[str, MessageNode]                 # 旧名 TreeNode
    response_blocks: dict[str, ResponseBlock]
    # 其他
    links: dict[str, LinkNode]
    files: dict[str, FileRecord]
```

### 2.2 DirectoryNode — 统一目录节点 (v6.0 新模型)

**文件**: `backend/app/schemas/directory_node.py`

取代旧 `Partition → Domain → Topic → Conversation` 四层模型。所有节点统一为 `DirectoryNode`，通过 `node_type` 和 `kind` 区分：

```python
class DirectoryNode(BaseModel):
    id: str                           # "dir_xxxx" 或 "conv_xxxx"
    user_id: str
    parent_id: str | None
    node_type: str                    # "dir" | "conv"
    kind: str                         # "general" | "temp" | "practice" | "secretary"

    name: str                         # "新节点"
    path: list[str]                   # ["root_id", "l1_id", "this_id"]
    children_order: list[str]         # 有序子级 ID (dir 类型)
    conv_message_ids: list[str]       # conv 类下的消息 ID

    user_name: str | None             # 用户手动命名
    ai_name: str                      # AI 自动生成命名
    summary_short: str                # 简短摘要
    summary_dirty: bool               # 摘要需更新标记

    payload: dict[str, Any]           # conv 类特有数据
    created_at: float
    updated_at: float
    metadata: dict[str, Any]
```

**关键属性**:
- `display_name` → `user_name or ai_name or name`
- `is_temp` → `kind == "temp"`
- `is_dir` → `node_type == "dir"`
- `is_conv` → `node_type == "conv"`

### 2.3 MessageNode — 消息节点

**文件**: `backend/app/schemas/directory_node.py`

取代旧 `TreeNode`，统一用 `directory_id` 指向所属 conv 节点：

```python
class MessageNode(BaseModel):
    id: str                           # "msg_xxxx"
    directory_id: str                 # 所属 conv 节点 ID

    # 向后兼容 (废弃中)
    partition_id: str = ""
    conversation_id: str = ""
    parent_id: str | None = None
    children_ids: list[str] = []

    # 内容
    role: str                         # "user" | "assistant"
    content: str
    content_blocks: list[dict]        # ContentBlock dicts
    text_summary: str

    # 元信息
    timestamp: float
    token_count: int
    version: int                      # 取代 has_modified_version
    is_deleted: bool
    is_archived: bool

    # 子支
    has_sub_branches: bool
    sub_branch_ids: list[str]
    sub_branch_summaries: list[dict]
```

### 2.4 KnowledgeGraph / KGNode / KGEdge — 知识图谱

**文件**: `backend/app/schemas/conversation.py`

```python
class KnowledgeGraph(BaseModel):
    partition_id: str
    name: str
    nodes: dict[str, KGNode]
    edges: list[KGEdge]
    generated_by: str = "manual"      # "ai" | "manual"
    version: int = 1
    updated_at: float

class KGNode(BaseModel):
    id: str
    label: str
    description: str
    mastery: float = 0.0              # 0-100
    mastery_level: str = ""           # 中文标签
    priority: int = 5
    tags: list[str] = []
    created_by: str = "user"          # "user" | "ai"
    conversation_ids: list[str] = []  # 关联的对话 ID
    version: int = 1

class KGEdge(BaseModel):
    id: str
    from_id: str
    to_id: str
    relation: str = "prerequisite"
    label: str = ""
```

### 2.5 CognitiveNode — 认知量子实体

**文件**: `backend/app/domain/cognitive/models.py`

15+ 子系统追踪学习状态：

| 子系统 | 字段 | 说明 |
|--------|------|------|
| 身份 | id, label, level, parent, path_id | 五层层级: partition→domain→topic→concept→atom |
| 贝叶斯信念 | belief: Belief(alpha, beta, proficiency_mean) | Beta(α,β) 分布，先验 α=β=2 |
| ACT-R 激活 | activation: Activation(base_level, retrieval_prob, latency_ms) | 记忆检索模型 |
| 预测编码 | prediction: Prediction(top_down_mean, prediction_error) | 预测误差 |
| 认知负荷 | cognitive_load: CognitiveLoad(intrinsic, extraneous, germane) | 三类认知负荷 |
| 练习摘要 | practice_summary: PracticeSummary(total_attempts, correct_attempts) | 练习统计 |
| 趋势 | trend: Trend(direction, stagnation_days) | ascending/descending/plateau/volatile |
| 错误诊断 | error_clusters: list[ErrorCluster] | 错误聚类 |
| 调度 | schedule: Schedule(urgency, last_practiced) | 三级队列: urgency×2 / ZPD×1.5 / exploration×0.5 |
| 对话上下文 | dialogue_contexts: list[DialogueContext] | 对话历史摘要 |
| 元认知 | metacognition: Metacognition(calibration_error) | 校准误差 |
| 激励 | engagement: Engagement(streak_current, xp) | 连续学习天数、经验值 |
| 知识编译 | compilation: KnowledgeCompilation | 知识编译状态 |

**掌握度等级** (`shared/constants.py`):
```
未接触 (<0.3) / 初学 (0.3-0.6) / 发展中 (0.6-0.8) / 接近掌握 (0.8-0.9) / 已掌握 (>0.9)
```

### 2.6 存储适配桥

**`knowledge_trace.py`** → 从 CognitiveNode 读取 `proficiency_mean`，转换为 `KnowledgeState` DTO：
```python
KnowledgeState(skill_id, p_known, attempt_count, correct_count)
```

**`knowledge_state.py`** → 规范版查询：优先 CognitiveNode → 回退 BKT：
```python
get_knowledge_state(user_id, skill_id) → {skill_id, p_known, mastery_level, source}
```

---

## 3. 后端模块架构

### 3.1 知识服务层 (`app/services/knowledge/`)

**13 个文件**，按职责分为 4 组：

#### 组 A: 树操作 (核心 CRUD)

| 文件 | 类/混入 | 职责 |
|------|---------|------|
| `tree_service.py` | `TreeOpsService` | 主入口，组合 6 个 Mixin，提供完整 API |
| `tree_ops.py` | `tree_ops` | 重导出 shim，向后兼容 |
| `tree_directory.py` | `TreeDirectoryMixin` | 目录/会话节点 CRUD、树构建、迁移 |
| `tree_messages.py` | `TreeMessagesMixin` | 消息 CRUD、不可变编辑模式 |
| `tree_sub_branch.py` | `TreeSubBranchMixin` | 子支(分支对话)创建/查询/删除 |

**TreeOpsService 组合结构**:
```
TreeOpsService
├── TreeDirectoryMixin     # create_dir, create_conv, delete_node, build_tree, migrate_conv
├── TreeMessagesMixin      # add_message, modify_message, delete_message
├── TreeSubBranchMixin     # create_sub_branch, get_sub_branches
├── TreeSyncMixin          # _sync_skill (CognitiveNode 同步)
├── TreeNamingMixin        # rename_node (委托到 TreeDirectoryMixin)
└── TreeContextMixin       # get_dir_context, switch_conversation
```

#### 组 B: 知识查询与同步

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| `cognitive_queries.py` | 10 个函数 | 从 CognitiveNode 读取数据，生成 LLM 上下文 |
| `cognitive_sync.py` | 4 个函数 | 消息存储后异步同步：元历史、分支命名、图谱更新、对话证据 |
| `knowledge_query_service.py` | `KnowledgeQueryServiceImpl` | Facade 模式，委托到 queries + sync |
| `knowledge_state.py` | `get_knowledge_state` | 规范版掌握状态查询 (CognitiveNode → BKT 回退) |

#### 组 C: 知识图谱服务

| 文件 | 类 | 职责 |
|------|-----|------|
| `knowledge_graph_service.py` | `KnowledgeGraphServiceImpl` | 监听领域事件(练习答案、错误记录)，同步到 CognitiveNode |

#### 组 D: 学习算法

| 文件 | 类 | 职责 |
|------|-----|------|
| `zpd_scheduler.py` | `ZPDScheduler` | 最近发展区自适应选题，基于 Vygotsky 理论 |
| `knowledge_expander.py` | `KnowledgeExpander` | LLM 驱动知识扩展：深层解释、变体题、关系发现 |

### 3.2 认知域 (`app/domain/cognitive/`)

**10 个文件**，实现 CognitiveNode 的完整生命周期：

| 文件 | 职责 |
|------|------|
| `__init__.py` | `get_repo()` 单例入口 |
| `models.py` | CognitiveNode 完整数据模型 (15+ 子系统) |
| `memory_repository.py` | 内存仓储实现 (PG 存储) |
| `writer.py` | CognitiveNode 写入器 |
| `events.py` | 认知事件系统 (`submit_dialogue_context` 等) |
| `operation_registry.py` | 认知操作注册中心 |
| `growth_engine.py` | 成长引擎 |
| `edge_models.py` | 边模型 |
| `constants.py` | 常量定义 |

### 3.3 知识图谱 API 路由 (`app/api/knowledge/`)

**前缀**: `/api/knowledge/graph`

| 子模块 | 端点 | 职责 |
|--------|------|------|
| `query.py` | `GET /partitions` | 分区列表 |
| | `GET /recommendation` | 知识树↔对话双向推荐 |
| | `GET /{partition_id}` | 获取完整知识树 |
| `crud.py` | `POST /{pid}/node` | 添加节点 |
| | `PATCH /{pid}/node/{nid}` | 编辑节点 |
| | `DELETE /{pid}/node/{nid}` | 删除节点 |
| | `POST /{pid}/edge` | 添加边 |
| | `DELETE /{pid}/edge/{eid}` | 删除边 |
| `ai.py` | `POST /{pid}/generate` | AI 生成知识图谱 |
| | `POST /{pid}/ai-expand` | AI 扩充节点 |
| | `POST /{pid}/ai-edit` | AI 编辑节点 |
| `conv.py` | `POST /{pid}/link-conversation` | 关联对话到节点 |
| | `DELETE /{pid}/link-conversation/{nid}/{cid}` | 取消关联 |
| | `POST /{pid}/explore` | 节点探索对话 |
| | `POST /{pid}/ai-chat` | AI 对话编辑知识树 |

### 3.4 对话树 API 路由 (`app/api/conversation/`)

**前缀**: `/api/conversations`

| 端点 | 方法 | 职责 |
|------|------|------|
| `/tree/{level}` | GET | 按层级列节点 (partition/domain/topic/conversation/directory) |
| `/tree/directory` | POST | 创建目录节点 |
| `/tree/{level}` | POST | 创建层级节点 (向后兼容) |
| `/tree/directory/{id}` | GET | 获取单个节点详情 |
| `/tree/directory/{id}` | PATCH | 重命名目录节点 |
| `/tree/directory/{id}` | DELETE | 删除目录节点 |
| `/tree/conversation/temporary` | POST | 创建临时对话 |
| `/tree/conversation/{id}/migrate` | POST | 迁移临时对话到正式分区 |
| `/tree/switch` | POST | 切换对话上下文 |
| `/tree/conversation/{id}/messages` | GET | 获取对话消息列表 |
| `/tree/conversation/{id}/message` | POST | 发送消息 (触发后台 pipeline) |
| `/tree/message/{id}` | GET/PUT | 获取/修改消息 |
| `/tree/message/{id}/switch-version` | POST | 切换消息版本 |
| `/tree/message/{id}/reply` | POST | 编辑后重新生成回复 |
| `/sub-branch` | POST | 创建子支 |
| `/messages/{id}/sub-branches` | GET | 获取消息子支列表 |
| `/sub-branch/{id}/parent` | GET | 获取子支父会话 |

### 3.5 知识图谱 API (`/api/knowledge`)

| 端点 | 职责 |
|------|------|
| `GET /graph` | 获取用户知识图谱 (nodes + edges + 力导向布局) |
| `POST /explain` | AI 解释知识点 |
| `GET /retention` | 获取遗忘曲线 |

### 3.6 秘书工具集成

**文件**: `backend/app/domain/secretary/tools/knowledge_tree_tools.py`

定义 2 个秘书工具，触发前端路由导航：

| 工具名 | 触发条件 | 效果 |
|--------|----------|------|
| `search_knowledge_tree` | 用户要求搜索知识树 | 前端导航到 `/knowledge-tree?search=xxx` |
| `expand_knowledge_node` | 用户要求展开节点 | 前端导航到 `/knowledge-tree?node=xxx` |

---

## 4. 前端模块架构

### 4.1 路由页面

| 路由 | 文件 | 功能 |
|------|------|------|
| `/knowledge-tree` | `app/knowledge-tree/page.tsx` | 知识树独立页面 (Phase 11 设计) |

### 4.2 状态管理层 (Zustand Stores)

```
┌─────────────────────────────────────────────────────┐
│  conversation-store.ts (协调器)                      │
│  ├── tree-store.ts      (树数据、展开/折叠、懒加载)    │
│  ├── message-store.ts   (消息数据、流式更新)          │
│  └── streaming.ts       (SSE 流状态)                 │
│                                                      │
│  动作实现层:                                          │
│  ├── tree-ops.ts        (创建新会话)                  │
│  ├── dir-ops.ts         (目录列表 CRUD)               │
│  ├── nav-ops.ts         (会话选择、上下文切换)         │
│  ├── sub-branch.ts      (子支操作)                   │
│  ├── send-message.ts    (发送消息)                   │
│  └── message-ops.ts     (消息操作)                   │
└─────────────────────────────────────────────────────┘
```

**tree-store.ts 核心逻辑**:
- `loadRootNodes()` → `GET /tree/directory` (新) → `GET /tree/partition` (旧回退)
- `loadChildren(nodeId)` → `GET /tree/directory?parent_id={id}` (新) → `GET /graph/nodes?parent_id={id}` (旧回退)
- `toggleExpand(node)` → 展开/折叠 + localStorage 持久化
- 使用 `childMap` (Map<string, GraphNode[]>) 缓存所有层级的子节点
- 使用 `loadingSet` 防止重复请求

### 4.3 React Hooks 层

| Hook | 文件 | 职责 |
|------|------|------|
| `useTreeNavigation` | `hooks/graph/useTreeNavigation.ts` | 树导航 CRUD: 创建/重命名/删除/展开/新建会话 |
| `useTreeLayout` | `hooks/graph/useTreeLayout.ts` | 布局偏好: 面板显隐/宽度/图谱模式/层级 |
| `useGraphData` | `hooks/graph/useGraphData.ts` | 图谱数据加载 + 重试 + ResizeObserver |
| `useGraphCanvas` | `hooks/graph/useGraphCanvas.ts` | 画布主 Hook: 缩放/搜索/聚焦/快捷键/右键菜单/内联编辑 |
| `useGraphNodeActions` | `hooks/graph/useGraphNodeActions.ts` | 节点 CRUD + AI 操作: 删除/编辑/创建/AI扩充/AI编辑/AI对话 |
| `useGraphDialogue` | `hooks/graph/useGraphDialogue.ts` | 对话式图谱页: 节点选择/关联会话/练习/反思/分栏拖拽 |

### 4.4 API 客户端层

| 文件 | 职责 |
|------|------|
| `lib/api/graph-api.ts` | `fetchGraphData(pid)`, `fetchPartitions()` → 调用 `/api/knowledge/graph/*` |
| `lib/api/api.ts` | 基础 HTTP 客户端 (tree/v2 实例) |
| `store/conversation/tree-helpers.ts` | `apiFetch`, `v2Fetch`, `ensureConversationAtLevel` |

### 4.5 类型与数据转换

| 文件 | 职责 |
|------|------|
| `lib/types/graph-types.ts` | 后端类型 (`KGTreeResponse`) → 前端类型 (`GraphData`) 转换 |
| | `kgTreeToGraphData()`: 从 prerequisite 边推导父子关系、分配层级深度 |
| | `filterByLevel()`, `subtreeFilter()`, `getNodeAncestors()` 等工具函数 |

### 4.6 组件层

| 组件 | 职责 |
|------|------|
| `components/conversation/tree/SidebarTreeNode.tsx` | 递归树节点渲染: 图标/展开/内联编辑/快捷操作 |
| `knowledge-tree-preview.html` | 独立 HTML 原型: 演示布局/交互/图谱/对话 |

---

## 5. API 路由全景

### 5.1 后端 API 完整清单

```
/api/knowledge/graph/*           (知识图谱 CRUD + AI)
├── GET  /partitions             分区列表
├── GET  /recommendation         双向推荐
├── GET  /{partition_id}         获取知识树
├── POST /{pid}/node             添加节点
├── PATCH /{pid}/node/{nid}      编辑节点
├── DELETE /{pid}/node/{nid}     删除节点
├── POST /{pid}/edge             添加边
├── DELETE /{pid}/edge/{eid}     删除边
├── POST /{pid}/generate         AI 生成图谱
├── POST /{pid}/ai-expand        AI 扩充节点
├── POST /{pid}/ai-edit          AI 编辑节点
├── POST /{pid}/link-conversation 关联对话
├── DELETE /{pid}/link-conversation/{nid}/{cid} 取消关联
├── POST /{pid}/explore          节点探索对话
└── POST /{pid}/ai-chat          AI 对话编辑

/api/conversations/tree/*        (对话树 CRUD)
├── GET/POST  /tree/{level}      层级节点 CRUD
├── GET/POST/PATCH/DELETE /tree/directory[/{id}]  目录节点 CRUD
├── POST /tree/conversation/temporary              临时对话
├── POST /tree/conversation/{id}/migrate            迁移对话
├── POST /tree/switch                               切换上下文
├── GET  /tree/conversation/{id}/messages           消息列表
├── POST /tree/conversation/{id}/message            发送消息
├── GET/PUT /tree/message/{id}                      消息 CRUD
├── POST /tree/message/{id}/switch-version          版本切换
├── POST /tree/message/{id}/reply                   重新生成回复
├── POST /sub-branch                                子支创建
├── GET  /messages/{id}/sub-branches                子支列表
└── GET  /sub-branch/{id}/parent                    子支父会话

/api/knowledge/*                  (知识图谱旧版)
├── GET  /graph                  知识图谱 (nodes+edges+layout)
├── POST /explain                AI 解释
└── GET  /retention              遗忘曲线
```

### 5.2 前端调用映射

| 前端 Store/Hook | 调用的后端 API |
|-----------------|---------------|
| `tree-store.loadRootNodes()` | `GET /tree/directory` → `GET /tree/partition` |
| `tree-store.loadChildren(id)` | `GET /tree/directory?parent_id={id}` → `GET /graph/nodes?parent_id={id}` |
| `useTreeNavigation.confirmCreateChild()` | `POST /tree/directory` |
| `useTreeNavigation.handleRename()` | `PATCH /tree/directory/{id}` |
| `useTreeNavigation.handleRenameConv()` | `PATCH /tree/conversation/{id}` |
| `useTreeNavigation.confirmDelete()` | `DELETE /tree/directory/{id}` / `DELETE /tree/conversation/{id}` |
| `useGraphData.reload()` | `GET /api/knowledge/graph/{pid}` |
| `useGraphNodeActions.deleteNode()` | `DELETE /api/knowledge/graph/{pid}/node/{nid}` |
| `useGraphNodeActions.editNode()` | `PATCH /api/knowledge/graph/{pid}/node/{nid}` |
| `useGraphNodeActions.createNode()` | `POST /api/knowledge/graph/{pid}/node` |
| `useGraphNodeActions.aiExpand()` | `POST /api/knowledge/graph/{pid}/ai-expand` |
| `useGraphNodeActions.aiChat()` | `POST /api/knowledge/graph/{pid}/ai-chat` |
| `dir-ops.loadDirListImpl()` | `GET /tree/directory` → `GET /tree/partition` |
| `dir-ops.createDirectoryImpl()` | `POST /tree/directory` |
| `sub-branch.createSubBranchImpl()` | `POST /sub-branch` |
| `nav-ops.switchConfirmImpl()` | `POST /api/conversations/tree/switch` |
| `tree-helpers.ensureConversationAtLevel()` | `POST /tree/directory` |
| `tree-helpers.getNextConversationName()` | `GET /tree/directory?parent_id={id}` |

---

## 6. 运行时流程与数据流

### 6.1 用户发送消息 — 完整链路

```
用户输入文本
  │
  ▼
[前端] sendMessage(text) → conversation-store.ts
  │
  ▼
[前端] POST /api/conversations/tree/conversation/{id}/message
  │
  ▼
[后端] start_background_pipeline(user_id, text, partition_id, conversation_id)
  │
  ├─→ [后端] ContextPipeline.assemble()  ← 6 个 Provider 按序执行
  │   ├── Provider 1: TutorPersona       → 系统提示词
  │   ├── Provider 2: ConversationLocation → PDTC 层级位置
  │   ├── Provider 3: LearnerEmotion     → 情绪感知 + 策略建议
  │   ├── Provider 4: LearnerCognition   → 知识状态 + 认知画像 + 知识图谱概览
  │   │     ├── get_knowledge_query().get_knowledge_context()  → 薄弱/掌握技能
  │   │     ├── get_repo().get_node()                          → CognitiveNode 认知画像
  │   │     └── data.knowledge_graphs[pid]                     → 知识图谱掌握概览
  │   ├── Provider 5: LearningActivity   → 练习上下文 + 选题建议
  │   └── Provider 6: TutorCapability    → 工具 + RAG 资料 + 题库
  │
  ├─→ [后端] LLM 流式生成 → TokenBuffer → SSE 推送
  │
  └─→ [后端] 消息存储后 hooks (异步):
      ├── _p0_post_message_hooks()
      │   ├── write_to_meta_history()       → 元历史写入
      │   ├── try_auto_rename_branch()      → 自动重命名分支
      │   ├── generate_branch_summary()     → 生成分支摘要
      │   └── update_partition_context()    → 更新分区上下文
      ├── _analyze_conversation_evidence()  → 对话证据分析
      │   └── analyze_dialogue_evidence()   → 知识证据检测
      │       └── submit_dialogue_context() → 写入 CognitiveNode
      └── _trigger_graph_update()           → 触发知识图谱更新
          └── generate_graph_logic()        → AI 重新生成图谱
```

### 6.2 知识图谱生成流程

```
触发: POST /api/knowledge/graph/{pid}/generate
  或: _trigger_graph_update() (会话分支重命名后)

  │
  ▼
generate_graph_logic(partition_id, user_id, data, branch_name, depth)
  │
  ├── 1. 收集分区上下文 (name, subject, domain_tags, 现有分支, 现有节点)
  ├── 2. 构建 LLM system prompt (含上下文 + 格式要求)
  ├── 3. LLM 生成 JSON (nodes + edges)
  ├── 4. 解析 JSON, 创建 KGNode + KGEdge
  ├── 5. 合并用户创建的节点 (user_nodes 优先)
  ├── 6. 保存到 data.knowledge_graphs[partition_id]
  └── 7. _sync_graph_to_cognitive() → 同步到 CognitiveNode 仓储
```

### 6.3 知识树 ↔ 对话双向推荐流

```
知识树 → 对话:
  用户探索知识树节点 → 全部叶子节点已探索
  → GET /api/knowledge/graph/recommendation?source=tree
  → 返回 {type: "tree_complete", action: "go_conversation"}
  → 前端显示推荐横幅

对话 → 知识树:
  AI-chat 中 LLM 输出 [RECOMMEND:tree_complete] 标记
  → 前端解析 → 推荐去对话系统

  AI-chat 中 LLM 输出 [RECOMMEND:deep_dive:node_id:label]
  → 前端解析 → 推荐深入特定知识点

  AI-chat 中 LLM 输出 [RECOMMEND:parent:node_id:label]
  → 前端解析 → 推荐切换到父节点
```

### 6.4 练习 → 知识树联动

```
练习完成 → submit_answer()
  │
  ├── practice_secretary_integration.check_and_generate_proposals()
  │   ├── _check_error_accumulation()    → 错题积累达阈值 → error_alert 提案
  │   ├── _check_mastery_stall()         → 掌握度停滞 → intervention 提案
  │   ├── _generate_review_reminder()    → 到期复习提醒
  │   └── _generate_reflection_prompt()  → 练习后反思引导
  │
  └── knowledge_graph_service.on_answer_submitted()
      └── get_repo().sync_from_practice_event() → 更新 CognitiveNode 信念
```

### 6.5 数据存储流

```
读取:
  UserData = get_data_repo().load(user_id)
  → PgStorageEngine.load() → PostgreSQL conversation_user_meta JSONB

写入:
  get_data_repo().save(user_id, data)
  → PgStorageEngine.save() → PostgreSQL UPSERT JSONB

CognitiveNode 独立存储:
  get_repo().upsert_node(node, user_id) → cognitive_nodes 表
  get_repo().get_node(node_id, user_id) → cognitive_nodes 表
```

---

## 7. 模块间联动关系

### 7.1 联动矩阵

```
                ┌──────┬──────┬──────┬──────┬──────┬──────┐
                │知识树│对话  │认知  │练习  │秘书  │文件  │
                │API   │系统  │域    │系统  │系统  │系统  │
┌───────┬───────┼──────┼──────┼──────┼──────┼──────┼──────┤
│知识树 │ 自身  │  ✓   │  ✓   │  -   │  ✓   │  -   │
│API    │       │      │      │      │      │      │
├───────┼───────┼──────┼──────┼──────┼──────┼──────┼──────┤
│对话   │  推荐  │ 自身  │  ✓   │  ✓   │  ✓   │  ✓   │
│系统   │ 双向  │      │      │      │      │      │
├───────┼───────┼──────┼──────┼──────┼──────┼──────┼──────┤
│认知域 │ 同步  │ 证据  │ 自身  │ 事件  │  -   │  -   │
│       │       │ 分析  │      │ 驱动  │      │      │
├───────┼───────┼──────┼──────┼──────┼──────┼──────┼──────┤
│练习   │  -    │ 选题  │ 信念  │ 自身  │  提案 │ 题目  │
│系统   │       │ 建议  │ 更新  │      │  生成 │  生成  │
├───────┼───────┼──────┼──────┼──────┼──────┼──────┼──────┤
│秘书   │ 工具  │  分类 │  -   │ 监督  │ 自身  │  -   │
│系统   │ 导航  │  推荐 │      │      │      │      │
├───────┼───────┼──────┼──────┼──────┼──────┼──────┼──────┤
│文件   │  -    │  RAG  │  -   │ 题目  │  -   │ 自身  │
│系统   │       │  注入 │      │ 生成  │      │      │
└───────┴───────┴──────┴──────┴──────┴──────┴──────┴──────┘
```

### 7.2 关键联动详解

**A. 知识树 ↔ 对话 (双向推荐)**
- 知识树 → 对话: 叶子节点全部探索 → `tree_complete` 推荐
- 对话 → 知识树: LLM 输出 `[RECOMMEND:deep_dive/parent]` 标记 → 前端解析导航

**B. 知识树 ↔ 认知域 (同步)**
- `_sync_graph_to_cognitive()`: 图谱节点创建/更新时 → upsert 到 CognitiveNode
- `_sync_skill()`: 对话回复提及知识点时 → upsert 到 CognitiveNode
- `knowledge_trace.py`: 从 CognitiveNode 读取 `proficiency_mean` → 填充 KGNode.mastery

**C. 对话 ↔ 认知域 (证据分析)**
- 每轮对话后 → `analyze_dialogue_evidence()` → 检测 4 种证据类型
- `submit_dialogue_context()` → 写入 CognitiveNode.dialogue_contexts

**D. 练习 ↔ 认知域 (信念更新)**
- `sync_from_practice_event()` → 更新 `Belief(alpha, beta, proficiency_mean)`
- 练习答案事件 → `KnowledgeGraphServiceImpl.on_answer_submitted()`

**E. 练习 ↔ 秘书 (提案生成)**
- `check_and_generate_proposals()` → 4 种提案类型 → 写入 `secretary_proposals`

**F. 对话 ↔ 文件 (RAG 注入)**
- `ContextPipeline Provider 6: TutorCapability` → `material_search.search_sync()` → RAG 上下文注入

---

## 8. 当前架构问题与优化方向

### 8.1 数据结构问题

| 问题 | 影响 | 建议 |
|------|------|------|
| 双模型并存: DirectoryNode 新模型 + Partition/Domain/Topic/Conversation 旧模型 | 代码中大量 `if conv_node else conv` 兼容分支，维护成本高 | 彻底迁移到 DirectoryNode，移除旧模型 |
| 双知识系统: KGNode(mastery: float) vs CognitiveNode(Belief: Beta分布) | 数据不一致，两套掌握度可能不同步 | 统一掌握度数据源，KGNode 只做展示 |
| `knowledge_trace.py` 桥接层脆弱 | 依赖 CognitiveNode 可用性，回退到默认值可能不准确 | 缓存层 + 降级策略 |
| `conv_message_ids` 与旧 `conv.path` 并存 | 消息查询需要两套逻辑 | 统一到 `conv_message_ids` |

### 8.2 逻辑问题

| 问题 | 影响 | 建议 |
|------|------|------|
| `tree_service.py` 过于庞大 (6 个 Mixin 组合) | 单文件职责过重，修改风险高 | 拆分为独立服务，Mixin 改为组合模式 |
| 向后兼容 stub 过多 (create_partition, delete_partition 等) | 旧 API 仍然可用，新 API 推广受阻 | 标记 deprecated，前端全部迁移后移除 |
| 知识图谱 API 与目录树 API 分离 | 前端需要两套 API 调用，数据不一致 | 统一为单一大知识树 API |
| `_sync_graph_to_cognitive()` 在每次 CRUD 后同步 | 同步不完整，新节点创建但不更新信念 | 改为事件驱动，异步批量同步 |
| AI-chat 作用域约束依赖 BFS 遍历 | 大图时性能差 | 预计算作用域，缓存到边表 |

### 8.3 功能缺口

| 缺口 | 说明 |
|------|------|
| 知识树节点与 CognitiveNode 的双向链接不完整 | KGNode 只有 `conversation_ids`，缺少 `cognitive_node_id` |
| 缺少知识树版本/历史 | 图谱修改无历史记录，无法回退 |
| 缺少节点合并/拆分 | 目前只支持基本 CRUD，无高级编辑操作 |
| 缺少知识树导出 | 无导出为 JSON/Markdown/图片 功能 |
| 缺少协作编辑 | 单用户编辑，无协作/分享功能 |
| 前端 `useGraphCanvas` 和 `useGraphDialogue` 功能重叠 | 两个 Hook 有大量重复的图谱加载逻辑 |

### 8.4 前端优化方向

| 方向 | 说明 |
|------|------|
| 统一图谱数据源 | `useGraphCanvas` 和 `useGraphDialogue` 共享数据加载逻辑 |
| 虚拟化树渲染 | 大量节点时 (500+) 需要虚拟滚动 |
| 图谱布局缓存 | 力导向布局结果缓存到 localStorage，避免重复计算 |
| 离线支持 | 图谱数据 IndexedDB 缓存 |
| 移动端适配 | 当前设计面向桌面端，移动端需要触摸手势和响应式布局 |

### 8.5 模块联动优化

| 方向 | 说明 |
|------|------|
| 统一事件总线 | 知识树变更、认知状态变更、对话变更都通过事件总线广播 |
| 知识树变更 → 认知域自动同步 | 替代当前手动 `_sync_graph_to_cognitive()` |
| 练习结果 → 知识树掌握度实时更新 | 通过 WebSocket 推送掌握度变化到前端 |
| 秘书提案 → 知识树操作 | 秘书可主动建议知识树节点操作 (创建/扩充/关联) |

---

## 附录: 文件清单

### 后端文件 (知识树相关)

```
app/services/knowledge/
├── __init__.py                    # 空包
├── tree_service.py                # TreeOpsService 主入口 (6 Mixin 组合)
├── tree_ops.py                    # 重导出 shim
├── tree_directory.py              # TreeDirectoryMixin: 目录节点 CRUD
├── tree_messages.py               # TreeMessagesMixin: 消息 CRUD
├── tree_sub_branch.py             # TreeSubBranchMixin: 子支操作
├── knowledge_graph_service.py     # KnowledgeGraphServiceImpl: 事件监听
├── knowledge_state.py             # get_knowledge_state: 规范版查询
├── cognitive_queries.py           # 10 个查询函数: 认知上下文生成
├── cognitive_sync.py              # 4 个同步函数: 消息后钩子
├── knowledge_query_service.py     # KnowledgeQueryServiceImpl: Facade
├── zpd_scheduler.py               # ZPDScheduler: 自适应选题
└── knowledge_expander.py          # KnowledgeExpander: LLM 知识扩展

app/api/knowledge/
├── knowledge.py                   # /api/knowledge 路由
├── knowledge_routes/
│   ├── __init__.py                # 共享模型 + 辅助函数 + generate_graph_logic
│   ├── query.py                   # 查询: 分区列表/推荐/图谱获取
│   ├── crud.py                    # CRUD: 节点/边增删改
│   ├── ai.py                      # AI: 生成/扩充/编辑
│   └── conv.py                    # 会话: 关联/探索/AI对话

app/api/conversation/
├── conversation.py                # 聚合路由
├── conversation_routes.py         # REST 端点 (树 CRUD + 消息 + 子支)
└── stream_sse.py                  # SSE 流式端点

app/domain/cognitive/
├── __init__.py                    # get_repo() 入口
├── models.py                      # CognitiveNode 完整模型
├── memory_repository.py           # PG 仓储实现
├── writer.py                      # 写入器
├── events.py                      # 事件系统
├── operation_registry.py          # 操作注册中心
├── growth_engine.py               # 成长引擎
├── edge_models.py                 # 边模型
└── constants.py                   # 常量

app/domain/secretary/tools/
└── knowledge_tree_tools.py        # 秘书知识树工具

app/services/conversation/
└── context_pipeline.py            # 上下文管线 (6 Provider)

app/services/practice/
└── practice_secretary_integration.py  # 练习-秘书联动

app/schemas/
├── directory_node.py              # DirectoryNode + MessageNode
└── conversation.py                # UserData + KnowledgeGraph + KGNode + KGEdge

shared/
├── knowledge_trace.py             # CognitiveNode → KnowledgeState 桥接
├── protocols/
│   ├── knowledge_query.py         # KnowledgeQueryService 协议
│   ├── cognitive.py               # CognitiveNodeRepository 协议
│   └── data_repository.py         # DataRepository 协议
└── constants.py                   # 掌握度等级等常量
```

### 前端文件 (知识树相关)

```
src/
├── app/knowledge-tree/
│   └── page.tsx                   # 知识树页面路由
├── store/conversation/
│   ├── conversation-store.ts      # 协调器 Store
│   ├── tree-store.ts              # 树数据 Store
│   ├── tree-helpers.ts            # API 助手 + 命名逻辑
│   ├── message-store.ts           # 消息 Store
│   ├── streaming.ts               # SSE 流状态
│   └── actions/
│       ├── tree-ops.ts            # 创建新会话
│       ├── dir-ops.ts             # 目录列表操作
│       ├── nav-ops.ts             # 选择/切换
│       ├── sub-branch.ts          # 子支操作
│       ├── send-message.ts        # 发送消息
│       └── message-ops.ts         # 消息操作
├── hooks/graph/
│   ├── useTreeNavigation.ts       # 树导航 CRUD
│   ├── useTreeLayout.ts           # 布局偏好
│   ├── useGraphData.ts            # 图谱数据加载
│   ├── useGraphCanvas.ts          # 画布主 Hook
│   ├── useGraphNodeActions.ts     # 节点 CRUD + AI
│   └── useGraphDialogue.ts        # 对话式图谱
├── lib/
│   ├── api/graph-api.ts           # 图谱 API 客户端
│   ├── api/api.ts                 # 基础 HTTP 客户端
│   └── types/graph-types.ts       # 类型定义 + 转换函数
├── components/conversation/tree/
│   └── SidebarTreeNode.tsx        # 递归树节点组件
└── public/
    └── knowledge-tree-preview.html # 独立 HTML 原型
```

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-17 | 初始版本: 完整架构分析，为 Round 4 重构提供基线 |