# ADR 0023: Round 4 知识树系统重构 — 数据模型重设计

> 状态: 实施中 — 新系统已建成，旧系统标记废弃待迁移  
> 日期: 2026-06-17  
> 轮次: 第四轮  
> 依赖: ADR 0022 (架构基线)  
> 原则: **开发阶段，不兼容旧版。旧代码直接删除，用最优方案。**

---

## 设计理念

**导航是导航，知识是知识，会话是桥。**

用户可以在会话中自由探索（无结构），也可以在知识树中审视元认知（结构化），两者通过会话自然关联，互不约束。

---

## 1. 核心数据模型

### 四实体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        KnowledgeNode                                │
│  知识树 — 唯一的知识体系，含认知状态                                      │
│                                                                      │
│  id, parent_id, label, level, brief, tags                           │
│  prerequisites, unlocks, associates                                 │
│  belief, activation, practice_events, error_clusters...              │
│  emoji, color, sort_order, is_visible                               │
│                                                                      │
│  存储: PG 表 knowledge_nodes                                         │
└───────────────┬─────────────────────────────────────────────────────┘
                │
                │ knowledge_node_ids (多对多)
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Conversation                                 │
│  会话 — 连接两个世界的桥                                              │
│                                                                      │
│  id, message_ids, knowledge_node_ids: list[str]                     │
│  summary_short, summary_dirty                                       │
│  created_at, updated_at                                             │
│                                                                      │
│  存储: PG 表 conversations                                           │
└───────┬─────────────────────────────────────┬───────────────────────┘
        │                                     │
        │ message_ids (1对多)                  │ knowledge_node_ids
        ▼                                     │ (多对多, 可选)
┌───────────────────────┐                     │
│       Message          │                    │
│  消息                  │                    │
│                       │                    │
│  id, conversation_id  │                    │
│  role, content        │                    │
│  content_blocks       │                    │
│  knowledge_node_ids   │  ← 可选, 精确标记    │
│  sub_branch_ids       │                    │
│                       │                    │
│  存储: PG 表 messages  │                    │
└───────────────────────┘                    │
                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       NavigationNode                                │
│  导航树 — 纯文件系统，用户自由组织                                       │
│                                                                      │
│  id, parent_id, node_type: "dir" | "conv"                           │
│  kind: general / temp / practice / secretary                        │
│  name, user_name, ai_name, children_order                           │
│  conversation_id: str          ← conv 类型, 指向 Conversation        │
│  knowledge_area_id: str | None ← dir 类型可选, 指向 KnowledgeNode     │
│                                                                      │
│  存储: PG 表 navigation_nodes                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 实体详解

```python
# ═══════════════════════════════════════════════
# KnowledgeNode — 知识树节点
# ═══════════════════════════════════════════════
class KnowledgeNode:
    """唯一的知识点实体。合并原 KGNode + CognitiveNode"""
    id: str
    parent_id: str | None

    # 身份
    label: str                              # "决策树"
    level: str                              # domain | topic | concept | atom
    brief: str                              # 简介
    tags: list[str]                         # 标签

    # 关系 (原 CognitiveNode.prerequisites + KGEdge)
    prerequisites: list[Prerequisite]       # 前置知识
    unlocks: list[Unlock]                   # 后置解锁
    associates: list[Associate]             # 相关但不依赖

    # 树结构 (原 CognitiveNode.children + DirectoryNode.children_order)
    children_order: list[str]               # 有序子节点

    # 认知状态 (原 CognitiveNode, 仅 topic 层级)
    belief: Belief
    activation: Activation
    practice_events: list[PracticeEvent]
    practice_summary: PracticeSummary
    trend: Trend
    error_clusters: list[ErrorCluster]
    scheduling: Scheduling
    metacognition: Metacognition
    engagement: Engagement
    # ... 其余子系统

    # 可视化
    emoji: str
    color: str
    sort_order: int
    is_visible: bool

    # 元信息
    created_at: float
    updated_at: float
    meta: MetaInfo


# ═══════════════════════════════════════════════
# Conversation — 会话
# ═══════════════════════════════════════════════
class Conversation:
    """独立的会话实体，连接导航树和知识树"""
    id: str
    user_id: str

    # 消息
    message_ids: list[str]                  # 有序消息 ID

    # 知识点关联 (核心桥字段)
    knowledge_node_ids: list[str]           # 0-N 个知识点

    # 摘要
    summary_short: str
    summary_dirty: bool

    # 元信息
    created_at: float
    updated_at: float


# ═══════════════════════════════════════════════
# Message — 消息
# ═══════════════════════════════════════════════
class Message:
    """消息节点"""
    id: str
    conversation_id: str

    role: str                               # user | assistant
    content: str
    content_blocks: list[dict]
    text_summary: str

    # 可选精确标记
    knowledge_node_ids: list[str]           # 0-N 个知识点

    # 子支
    has_sub_branches: bool
    sub_branch_ids: list[str]
    sub_branch_summaries: list[dict]

    # 版本
    version: int
    is_deleted: bool

    timestamp: float
    token_count: int
    metadata: dict


# ═══════════════════════════════════════════════
# NavigationNode — 导航树节点
# ═══════════════════════════════════════════════
class NavigationNode:
    """纯导航节点，用户自由组织的文件夹结构"""
    id: str
    user_id: str
    parent_id: str | None

    node_type: str                          # "dir" | "conv"
    kind: str                               # general | temp | practice | secretary

    name: str
    user_name: str | None
    ai_name: str

    children_order: list[str]               # dir 类型: 有序子节点

    # conv 类型: 指向会话
    conversation_id: str | None

    # dir 类型可选: 指向知识区域
    knowledge_area_id: str | None           # ★ 新增

    created_at: float
    updated_at: float
```

---

## 2. 两种学习模式

### 模式 A: 会话自由探索

```
用户打开一个新会话
  → NavigationNode(conv) → Conversation
  → 自由讨论, 无知识结构约束
  → 系统后台检测: "这段对话涉及决策树和SVM"
  → 提案: "是否关联到知识点 [决策树] [SVM]?"
  → 用户确认 → Conversation.knowledge_node_ids += ["决策树","SVM"]
  → 后续: 该知识点掌握度自动更新, 侧边栏显示相关知识脉络
```

**特点**: 先有对话，后有知识关联。用户不被打断，事后可选关联。

### 模式 B: 知识树元认知探索

```
用户打开知识树页面
  → 浏览 KnowledgeNode 树
  → "决策树" — 掌握度 75%, 错误集中在"剪枝策略"
  → 点击"查看相关会话" → 列出所有 knowledge_node_ids 含"决策树"的 Conversation
  → 点击"开始练习" → 进入该知识点的针对性练习
  → 点击"相关知识点" → 看到 SVM (associate), 集成学习 (unlock)
  → 点击"创建新会话讨论" → 创建 Conversation, 自动关联 knowledge_node_ids=["决策树"]
```

**特点**: 先有知识结构，后产生对话。元认知驱动学习路径。

### 模式 C: 混合 — 从会话跳到知识树，从知识树跳到会话

```
对话中:
  → 侧边栏显示当前会话关联的知识点卡片
  → 卡片含: 掌握度、关联知识点、错误聚类
  → 点击卡片 → 跳转到知识树中该节点详情

知识树中:
  → 节点详情含"相关会话"列表
  → 点击 → 跳转到该会话
  → 或直接"创建新会话讨论该知识点"
```

---

## 3. NavigationNode 知识区域关联

### `knowledge_area_id` 的作用

```python
class NavigationNode:
    knowledge_area_id: str | None  # dir 类型可选
```

| 场景 | knowledge_area_id | 效果 |
|------|-------------------|------|
| 普通目录 | null | 纯文件夹，无知识语义 |
| 知识专区 | "cog_ml" | 该目录下的会话默认推荐关联"机器学习"子树 |
| 课程专区 | "cog_math" | 管理"数学"相关的所有会话 |
| 临时目录 | null | 不关联任何知识 |

**使用方式**:
- 创建 dir 时可选关联 KnowledgeNode
- 知识树页面可"创建导航专区" — 一键创建 dir 并关联当前节点
- 该 dir 下的 conv 创建时，自动预填 `knowledge_node_ids` 为该知识区域的子树节点
- 用户可随时修改 dir 的关联，不影响已有 conv

---

## 4. 个性化学习场景

### 场景 1: 自由探索 → 事后整理

```
用户: 连续几天在临时目录随意聊天
  → 系统检测到高频出现的知识点: "决策树", "过拟合", "交叉验证"
  → 秘书提案: "检测到你最近在讨论机器学习相关主题，是否整理为知识专区？"
  → 用户确认 → 创建 NavigationNode(dir) "机器学习", knowledge_area_id="cog_ml"
  → 建议迁移相关会话到该目录
```

### 场景 2: 知识树巡游 → 发现薄弱 → 精准练习

```
用户: 浏览知识树, 看到"SVM"掌握度 45%
  → 点击详情 → 错误聚类: "核函数选择" 错误率 80%
  → 点击"靶向练习" → 生成 5 道关于核函数的选择题
  → 练习完成 → 掌握度更新 → 侧边栏实时刷新
```

### 场景 3: 对话中引用知识树

```
用户: (在会话中) "决策树和SVM哪个更好？"
  → AI 回复中引用知识树数据:
    "根据你的学习记录，决策树掌握度 75%，SVM 掌握度 45%。
     建议先巩固 SVM，它是决策树的进阶前置知识。"
  → 侧边栏显示两个知识点的对比卡片
```

### 场景 4: 自主规划学习路径

```
用户: 查看知识树, 看到"深度学习"需要前置"线性代数""概率论"
  → 两个前置节点掌握度: 线性代数 90%, 概率论 35%
  → 系统建议: "概率论掌握度不足，建议先巩固"
  → 用户点击"开始学习概率论" → 创建 Conversation, knowledge_node_ids=["概率论"]
  → 秘书自动生成学习计划: 先复习贝叶斯定理, 再讨论概率分布, 最后练习
```

---

## 5. 与当前设计的对比

| 维度 | 当前 (3实体混搭) | 新设计 (4实体解耦) |
|------|-----------------|-------------------|
| 知识实体 | KGNode(结构) + CognitiveNode(状态) 分离 | KnowledgeNode 统一 |
| 导航 | DirectoryNode 同时做 dir 和 conv | NavigationNode 纯导航 |
| 会话 | 内嵌在 DirectoryNode(conv) 中 | Conversation 独立实体 |
| 关联方向 | CognitiveNode.conversation_ids 单向 | Conversation.knowledge_node_ids 明确桥接 |
| 同步 | 双向同步，冲突风险 | 无同步，单一真源 |
| 无知识点会话 | kind=temp 特殊处理 | knowledge_node_ids=[] 自然 |
| 多知识点会话 | 数组字段 | 数组字段，天然支持 |
| 导航自由 | 低（与知识耦合） | 高（完全独立） |
| 知识专区 | 无 | knowledge_area_id 可选关联 |
| 存储 | JSONB 混存 | PG 独立表 |

---

## 6. 实施步骤

### Step 1: 合并 KGNode → CognitiveNode → KnowledgeNode

- 删除 `KGNode` / `KGEdge` / `KnowledgeGraph` 类
- `CognitiveNode` 重命名为 `KnowledgeNode`
- 新增字段: `tags`, `emoji`, `color`, `sort_order`, `is_visible`
- `knowledge_graphs` 从 `UserData` JSONB 迁移到 `knowledge_nodes` 表
- 删除 `_sync_graph_to_cognitive()` 和所有双向同步逻辑

### Step 2: 拆分 Conversation 独立实体

- 从 `DirectoryNode(node_type="conv")` 中提取 `Conversation` 类
- `Conversation` 独立 PG 表 `conversations`
- `NavigationNode(conv).conversation_id` 指向 `Conversation`
- 迁移 `UserData.directory_nodes` 中 `node_type="conv"` 的数据

### Step 3: NavigationNode 纯导航化

- `DirectoryNode` 重命名为 `NavigationNode`
- 删除 `conv_message_ids`（迁移到 Conversation）
- 删除 `payload` 字段（迁移到 Conversation）
- 新增 `knowledge_area_id` (可选)
- 迁移到 PG 表 `navigation_nodes`

### Step 4: Message 独立存储

- 从 `UserData.nodes` 迁移到 `messages` PG 表
- 新增 `knowledge_node_ids` (可选)
- 删除 `partition_id` / `conversation_id` 旧字段

### Step 5: 统一 API 前缀 `/api/knowledge-tree`

- 删除旧路由
- 新路由基于四实体设计

### Step 6: 前端适配

- 统一 Graph 数据源
- 适配新 API
- 知识树页面支持双向导航

### Step 7: 模块联动

- 事件总线
- SSE 实时推送
- 秘书提案

---

## 7. 问题

**Q1**: 四实体是否全部搬到 PG 独立表？
- 推荐: **是。** `knowledge_nodes` + `navigation_nodes` + `conversations` + `messages` 四张 PG 表。`UserData` JSONB 退化为用户配置（偏好、订阅等）。独立表支持索引、分页、全文搜索、事务。
- 备选: 保留 JSONB，仅 CognitiveNode 在 PG 表

**Q2**: `NavigationNode.knowledge_area_id` 是否必要？
- 推荐: **是。** 提供"知识专区"概念，让导航树可以有知识语义。用户可选使用，不强制。默认 null。
- 备选: 不需要，导航完全独立

**Q3**: `Message.knowledge_node_ids` 是否必要？
- 推荐: **是，可选。** 子支场景必须精确到消息级别。对话证据分析 (`_analyze_conversation_evidence`) 填充此字段。大部分消息为空。
- 备选: 仅 Conversation 级别

**Q4**: 知识树中如何反向查询"某个知识点的所有会话"？
- 推荐: **查询推导，不冗余存储。** `SELECT * FROM conversations WHERE knowledge_node_ids @> '["{node_id}"]'`。高频访问加缓存。
- 备选: `KnowledgeNode` 冗余存储 `conversation_ids`，写入时同步

**Q5**: `Prerequisite` / `Unlock` / `Associate` 三种关系是否保留？
- 推荐: **是。** 三种关系各有语义：
  - `prerequisite`: 必须先学 A 才能学 B
  - `unlock`: 学完 A 后推荐学 B
  - `associate`: A 和 B 相关，无先后顺序
  前端可视化时用不同颜色/箭头样式区分。
- 备选: 合并为一种关系，用 `relation_type` 区分

**Q6**: `NavigationNode` 和 `KnowledgeNode` 是否需要直接关联？
- 推荐: **仅 dir 可选，conv 不关联。** `NavigationNode(dir).knowledge_area_id` → `KnowledgeNode`。`NavigationNode(conv)` 通过 `Conversation` 间接关联知识点。两级不混淆。
- 备选: 不加任何直接关联，完全通过 Conversation 间接

**Q7**: 迁移脚本的执行顺序？
- 推荐: Step 1→2→3→4 顺序执行。迁移脚本一次性完成：
  1. 遍历 `UserData.knowledge_graphs` → 写入 `knowledge_nodes`
  2. 遍历 `UserData.directory_nodes` → 拆分写入 `navigation_nodes` + `conversations`
  3. 遍历 `UserData.nodes` → 写入 `messages`
  4. 删除 `UserData` 中的旧字段
  5. 前端一次性切换新 API
- 备选: 分步上线，新旧并存过渡

**Q8**: 导航树中 `kind="temp"` 的节点如何处理？
- 推荐: 保留。`NavigationNode(dir, kind="temp")` 不关联 `knowledge_area_id`。其下的 `NavigationNode(conv)` 的 `Conversation.knowledge_node_ids=[]`。临时目录纯粹是"未分类"的收纳区。
- 备选: 删除 temp 概念，所有节点默认 kind="general"

---

## 8. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-17 | 初始版本: 14 步重构计划 |
| 2026-06-17 | 修订: 去除兼容过渡，直接删除旧代码 |
| 2026-06-17 | 重设计: 四实体解耦架构，会话桥模式 |
| 2026-06-17 | 实施状态更新: 新系统已建成，旧系统标记废弃 |

---

## 9. 实施状态 (2026-06-17)

### 已完成

| 步骤 | 内容 | 状态 | 文件 |
|------|------|------|------|
| Step 1 | KnowledgeNode 合并 | ✅ | `schemas/knowledge.py`, `migrations/004_knowledge_tree_v5.sql`, `services/knowledge_v2/knowledge_node_service.py` |
| Step 2 | Conversation 独立 | ✅ | `services/knowledge_v2/conversation_service.py`, `migrations/004_knowledge_tree_v5.sql` |
| Step 3 | NavigationNode 导航化 | ✅ | `services/knowledge_v2/navigation_service.py`, `migrations/004_knowledge_tree_v5.sql` |
| Step 4 | Message 独立存储 | ✅ | `services/knowledge_v2/message_service.py`, `services/conversation/message_repository.py` (已适配 v5) |
| Step 5 | 统一 API `/api/knowledge-tree` | ✅ | `api/knowledge_tree_v5.py` (CRUD), `api/knowledge_tree_ai.py` (AI), `api/knowledge_tree_sse.py` (SSE) |
| Step 6 | 前端适配 | ✅ | `lib/api/knowledge-tree-api.ts`, `lib/api/graph-api.ts`, 所有 hooks + 组件已适配 |
| Step 7a | 事件总线 | ✅ | `services/knowledge_v2/event_bus_service.py` |
| Step 7b | SSE 实时推送 | ✅ | `api/knowledge_tree_sse.py` |
| Step 7c | 数据迁移 | ✅ | `migrations/005_migrate_to_v5.py` |
| — | 推荐接口 | ✅ | `api/knowledge_tree_ai.py` → `GET /ai/recommendation` |

### 未完成（旧代码未删除，原因: 对话系统/LLM系统深度耦合）

| 待删除项 | 引用方数量 | 影响模块 | 说明 |
|----------|-----------|---------|------|
| `KGNode/KGEdge/KnowledgeGraph` 类 | 3 文件 | knowledge_routes 内部 | 仅内部引用，可安全删除路由时一并删除 |
| `DirectoryNode/MessageNode` 类 | 11 文件 | conversation_routes, tree_directory, tree_service, tree_messages, pg_storage, classifier, organization | 对话系统核心依赖，需单独迁移项目 |
| `UserData.knowledge_graphs` | 16 文件 | pg_storage, llm_core, tool_executor, context_builder, context_pipeline, data_routes | LLM + 对话 + 数据管理 多层依赖 |
| `UserData.directory_nodes` | 14 文件 | conversation_routes, tree_directory, tree_service, classifier, organization, data_routes | 对话系统全链路依赖，80+ 引用点 |
| `_sync_graph_to_cognitive()` | 4 文件 | knowledge_routes 内部 | 仅内部调用 |
| 旧 API 路由 `/api/knowledge/graph` | 2 文件 | main.py, cognitive_sync.py | 路由注册 + 懒导入 |

**下一步**: 对话系统迁移到 v5 数据模型后，方可删除旧代码。当前新旧系统并存运行，前端已全部切换到 v5 端点。