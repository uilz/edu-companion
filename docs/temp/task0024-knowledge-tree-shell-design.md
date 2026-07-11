# Task 0024: 知识树壳（Knowledge Tree Shell）深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核深度设计）、Task 0014（事件协议设计）、Task 0018（练习壳深度设计）、Task 0019（秘书编排器深度设计）、Task 0020（规划壳深度设计）、Task 0021（对话壳深度设计）、Task 0022（闪卡壳深度设计）、Task 0023（阅读壳深度设计）

---

## 1. 定位与边界

### 1.1 一句话定位

知识树壳是用户对「学习内容」进行**主观组织**与查看「认知状态」的**一体化空间**：它把用户手动搭建的项目/知识树结构，和认知 OS 内核推断出的节点掌握度、不确定性、行动建议合并呈现，让用户既能自由创作知识图谱，又能实时看到自己的认知数据。

### 1.2 知识树壳的职责（必须做）

| 职责 | 说明 |
|------|------|
| **用户知识结构创作** | 创建、编辑、拖拽、删除项目/节点/边，支持层级树与自由图两种形态 |
| **认知数据可视化** | 把 `cognitive_node_projections` 的掌握度、紧迫度、不确定性映射为节点的颜色、大小、光晕、标签 |
| **双重视角切换** | 用户可只看「我的结构」、只看「认知数据」、或叠加两者 |
| **节点材料聚合** | 在节点详情页聚合关联的闪卡、错题、对话笔记、阅读笔记、阅读材料、计划项 |
| **直接操作入口** | 在树上直接发起练习、生成闪卡、创建计划、开启对话、导入阅读材料 |
| **结构导入与同步** | 从对话、练习、阅读、闪卡等壳导入内容并关联到已有或新建节点 |
| **视图状态保存** | 保存用户的缩放、平移、筛选、布局偏好 |
| **图搜索与筛选** | 按掌握度、紧迫度、节点类型、标签、来源模块筛选节点 |

### 1.3 知识树壳的禁止（不由它做）

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 直接更新认知投影 | 破坏 SSOT | 认知状态中心 |
| 直接更新闪卡/错题/计划内容 | 各壳维护私有聚合根 | 闪卡壳、练习壳、规划壳 |
| 维护节点信念计算逻辑 | 属于认知模型 | 认知 OS 内核 |
| 替用户做最终学习决策 | 用户拥有最终控制权 | 用户 |
| 直接读写其他壳的私有表 | 违反 CQRS 与模块化 | 通过事件总线与投影视图 |

### 1.4 知识树壳在架构中的位置

```
┌─────────────────────────────────────────────────────────────────┐
│                         场景壳层                                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  对话壳  │ │  练习壳  │ │  闪卡壳  │ │  阅读壳  │ │  规划壳    │ │
│  │    │    │ │    │    │ │    │    │ │    │    │ │    │      │ │
│  └────┼────┘ └────┼────┘ └────┼────┘ └────┼────┘ └─────┼─────┘ │
│       │           │           │           │             │       │
│       └───────────┴───────────┴───────────┴─────────────┘       │
│                           │                                      │
│                    统一事件协议（shared/events.py）                │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│                      认知 OS 内核                                  │
│  ┌─────────────┐  ┌─────────────────────┐  ┌─────────────────┐  │
│  │  事件总线    │  │   认知状态中心       │  │   秘书编排器     │  │
│  └─────────────┘  └─────────┬───────────┘  └─────────────────┘  │
│                             │                                    │
│                  ┌──────────▼──────────┐                        │
│                  │  cognitive_node_    │                        │
│                  │  projections        │                        │
│                  └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│                        知识树壳                                   │
│  用户创作结构（tree_nodes / tree_edges）+ 认知数据视图（projections）│
└─────────────────────────────────────────────────────────────────┘
```

**知识树壳的特殊地位**：它是「用户主观知识结构」与「系统客观认知数据」唯一交汇的界面。它不负责计算认知状态，但负责把认知状态翻译成用户能看懂、能操作的视觉语言。

---

## 2. 领域模型

### 2.1 聚合根：KnowledgeTree

```python
@dataclass
class KnowledgeTree:
    """知识树聚合根 — 用户创作的一棵知识组织结构。"""

    tree_id: str
    user_id: str

    title: str = "我的知识树"
    description: str = ""
    tree_type: Literal["project", "domain", "map"] = "project"

    # 根节点引用
    root_node_id: str = ""

    # 视图偏好
    default_view_mode: Literal["tree", "graph", "split"] = "tree"
    default_layout: Literal["layered", "force", "radial", "manual"] = "layered"

    # 元数据
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    status: Literal["active", "archived", "deleted"] = "active"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    version: int = 0
```

**设计要点：**
- `KnowledgeTree` 是用户创作的容器，与认知节点数据系统解耦。
- 一棵树可以是项目（project）、学科域（domain）或自由图（map）。
- 树的结构由 `TreeNode` 和 `TreeEdge` 表达，不直接等于认知节点的层级。

### 2.2 聚合根：TreeNode

```python
@dataclass
class TreeNode:
    """知识树上的一个节点 — 用户主观创作单位。"""

    node_id: str
    tree_id: str
    user_id: str

    label: str = "新节点"
    node_type: Literal[
        "topic",        # 主题
        "concept",      # 概念
        "skill",        # 技能
        "material",     # 材料引用
        "question",     # 题目引用
        "card",         # 闪卡引用
        "note",         # 笔记引用
        "milestone",    # 里程碑
    ] = "concept"

    # 层级结构
    parent_id: str = ""
    children_ids: list[str] = field(default_factory=list)
    order_index: int = 0

    # 视觉属性
    color: str = ""
    emoji: str = ""
    icon_url: str = ""
    position: dict = field(default_factory=dict)  # {x, y} for graph mode

    # 与认知数据系统的关联（0..N）
    linked_cognitive_node_ids: list[str] = field(default_factory=list)
    link_role: Literal["primary", "reference", "derived"] = "primary"

    # 引用外部材料
    source_refs: list[SourceRef] = field(default_factory=list)

    # 元数据
    tags: list[str] = field(default_factory=list)
    brief: str = ""
    metadata: dict = field(default_factory=dict)

    status: Literal["active", "collapsed", "archived", "deleted"] = "active"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    version: int = 0
```

**设计要点：**
- `TreeNode` 是用户创作节点，不是认知节点。一棵树节点可以关联零个、一个或多个认知节点。
- `node_type` 表达用户在树上的语义意图，不影响认知状态计算。
- `source_refs` 允许节点引用闪卡、阅读材料、错题、对话笔记等材料，但只是引用，不复制内容。

### 2.3 实体：TreeEdge

```python
@dataclass
class TreeEdge:
    """知识树上的边 — 用户定义的结构关系。"""

    edge_id: str
    tree_id: str
    user_id: str

    source_node_id: str = ""
    target_node_id: str = ""

    edge_type: Literal[
        "parent_child",   # 层级父子
        "prerequisite",   # 前置依赖
        "related",        # 相关
        "sequence",       # 学习顺序
        "reference",      # 引用
    ] = "parent_child"

    strength: float = 1.0          # 用户定义的强度 [0, 1]
    is_user_confirmed: bool = True  # 用户是否确认过这条边
    is_inferred: bool = False       # 是否由系统推断后用户确认

    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
```

**设计要点：**
- `TreeEdge` 是**用户创作图**的边，与 `knowledge_edges`（认知数据系统的边）独立维护。
- 当用户确认一条系统推断的边时，系统可将其复制为 `TreeEdge`，但 `knowledge_edges` 中的推断记录仍然保留。
- 边的 `strength` 影响可视化粗细和布局紧密度，不直接影响信念传播。

### 2.4 值对象：CognitiveNodeView

```python
@dataclass(frozen=True)
class CognitiveNodeView:
    """认知节点在知识树壳中的只读视图 — 来自 cognitive_node_projections。"""

    cognitive_node_id: str
    label: str
    level: Literal["domain", "topic", "atom"] = "atom"

    # 信念状态
    proficiency: float = 0.0          # α / (α + β)
    uncertainty: float = 0.0          # Beta 熵
    belief_alpha: float = 1.0
    belief_beta: float = 1.0

    # 行动状态
    urgency: float = 0.0              # 复习紧迫度
    stagnation_days: int = 0          # 停滞天数
    next_review_at: datetime | None = None
    next_action_type: Literal[
        "review", "practice", "explore", "deep_processing", "idle"
    ] = "idle"

    # 统计
    attempt_count: int = 0
    correct_count: int = 0
    error_count: int = 0
    card_count: int = 0
    note_count: int = 0

    # 可视化派生
    display_color: str = ""
    display_size: float = 1.0
    display_glow: bool = False

    last_event_id: str = ""
    updated_at: datetime = field(default_factory=_now)
```

**设计要点：**
- `CognitiveNodeView` 是**只读投影**，由知识树壳从 `cognitive_node_projections` 查询并做展示层派生。
- `display_color`、`display_size`、`display_glow` 由前端根据 `proficiency`、`uncertainty`、`urgency` 计算，后端不存储。
- 该视图让知识树壳在不写认知状态的情况下，完整呈现认知数据。

### 2.5 值对象：NodeMaterialBundle

```python
@dataclass(frozen=True)
class NodeMaterialBundle:
    """某认知节点关联的所有学习材料聚合 — 用于节点详情面板。"""

    cognitive_node_id: str
    user_id: str

    flashcards: list[dict] = field(default_factory=list)
    error_book_entries: list[dict] = field(default_factory=list)
    reading_notes: list[dict] = field(default_factory=list)
    conversation_notes: list[dict] = field(default_factory=list)
    reading_materials: list[dict] = field(default_factory=list)
    plan_items: list[dict] = field(default_factory=list)
    practice_sessions: list[dict] = field(default_factory=list)
```

**设计要点：**
- `NodeMaterialBundle` 是跨壳材料的**只读聚合视图**，由知识树壳调用各壳暴露的查询接口或读取统一投影组装。
- 各材料仍由所属壳维护，知识树壳只负责展示和跳转。

### 2.6 值对象：ViewportState

```python
@dataclass
class ViewportState:
    """用户的视图状态 — 每次进入知识树时恢复。"""

    user_id: str
    tree_id: str

    view_mode: Literal["tree", "graph", "split"] = "tree"
    layout: Literal["layered", "force", "radial", "manual"] = "layered"

    # 画布状态
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0

    # 筛选状态
    filters: dict = field(default_factory=dict)  # proficiency_range, urgency_range, node_types, tags

    # 展开/折叠状态
    collapsed_node_ids: list[str] = field(default_factory=list)
    focused_node_id: str = ""

    updated_at: datetime = field(default_factory=_now)
```

---

## 3. 状态机

### 3.1 TreeNode 状态机

```
                    ┌─────────────┐
                    │   active    │
                    │  （正常显示） │
                    └──────┬──────┘
                           │ user collapses
                           ▼
                    ┌─────────────┐     user expands      ┌─────────┐
                    │  collapsed  │ ─────────────────────▶│  active │
                    │  （折叠收起） │                       │         │
                    └──────┬──────┘                       └─────────┘
                           │ user archives
                           ▼
                    ┌─────────────┐
                    │  archived   │
                    └─────────────┘
                           │ user deletes
                           ▼
                    ┌─────────────┐
                    │   deleted   │
                    └─────────────┘
```

### 3.2 TreeEdge 状态机

```
                    ┌─────────────┐
                    │   active    │
                    │  （用户确认） │
                    └──────┬──────┘
                           │ system infers & user confirms
                           ▼
                    ┌─────────────┐
                    │   active    │
                    │  （推断确认） │
                    └──────┬──────┘
                           │ user dismisses
                           ▼
                    ┌─────────────┐
                    │  dismissed  │
                    └─────────────┘
```

### 3.3 视图模式状态机

```
        ┌─────────┐
        │  tree   │◀────────────────────┐
        │ 树模式   │                     │
        └────┬────┘                     │
             │ toggle view             │
             ▼                         │
        ┌─────────┐   toggle split    │
        │  graph  │ ─────────────────▶│  split  │
        │ 图模式   │                   │ 分屏模式 │
        └─────────┘◀──────────────────┘
```

---

## 4. 事件协议

### 4.1 知识树壳发布的事件

| 事件 | 消费者 | 说明 |
|------|--------|------|
| `TreeNodeCreated` | 秘书、分析 | 用户在树上创建节点 |
| `TreeNodeUpdated` | 秘书、分析 | 更新节点标签、颜色、位置等 |
| `TreeNodeDeleted` | 秘书、分析 | 删除节点 |
| `TreeNodeMoved` | 秘书、分析 | 拖拽移动节点 |
| `TreeEdgeCreated` | 认知中心、秘书 | 创建边 |
| `TreeEdgeDeleted` | 认知中心、秘书 | 删除边 |
| `TreeNodeLinkedToCognitiveNode` | 认知中心、秘书 | 树节点关联到认知节点 |
| `TreeNodeUnlinkedFromCognitiveNode` | 认知中心、秘书 | 解除关联 |
| `TreeViewChanged` | 分析 | 用户切换视图模式/筛选 |
| `TreeImportedContent` | 闪卡壳、阅读壳、对话壳 | 从其他壳导入内容到树 |

### 4.2 知识树壳订阅的事件

| 事件 | 来源 | 用途 |
|------|------|------|
| `CognitiveStateChanged` | 认知中心 | 更新节点颜色/大小/光晕 |
| `CognitiveNodeLinked` | 认知中心 | 系统推断关联时通知前端 |
| `FlashCardCreated` | 闪卡壳 | 在节点详情中展示新闪卡 |
| `ErrorRecorded` | 练习壳 | 在节点详情中展示新错题 |
| `ReadingNoteCreated` | 阅读壳 | 在节点详情中展示阅读笔记 |
| `AssistantReplied` | 对话壳 | 在节点详情中展示对话笔记 |
| `PlanItemCreated` | 规划壳 | 在节点详情中展示计划项 |
| `ProposalAccepted` | 秘书/前端 | 执行树上的提案（如创建节点、制卡） |

### 4.3 关键事件定义

```python
@dataclass(frozen=True)
class TreeNodeCreated(DomainEvent):
    """用户在知识树上创建节点。"""

    user_id: str
    tree_id: str
    node_id: str
    parent_id: str = ""
    label: str = ""
    node_type: str = "concept"
    linked_cognitive_node_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TreeNodeUpdated(DomainEvent):
    """用户更新知识树节点。"""

    user_id: str
    tree_id: str
    node_id: str
    changed_fields: list[str] = field(default_factory=list)
    old_label: str = ""
    new_label: str = ""


@dataclass(frozen=True)
class TreeNodeMoved(DomainEvent):
    """用户拖拽移动节点（改变父节点或位置）。"""

    user_id: str
    tree_id: str
    node_id: str
    old_parent_id: str = ""
    new_parent_id: str = ""
    new_position: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TreeEdgeCreated(DomainEvent):
    """用户创建知识树边。"""

    user_id: str
    tree_id: str
    edge_id: str
    source_node_id: str = ""
    target_node_id: str = ""
    edge_type: str = "parent_child"
    strength: float = 1.0
    is_inferred: bool = False


@dataclass(frozen=True)
class TreeNodeLinkedToCognitiveNode(DomainEvent):
    """知识树节点关联到认知节点。"""

    user_id: str
    tree_id: str
    tree_node_id: str
    cognitive_node_id: str
    link_role: str = "primary"


@dataclass(frozen=True)
class TreeImportedContent(DomainEvent):
    """从其他壳导入内容到知识树。"""

    user_id: str
    tree_id: str
    target_node_id: str = ""
    source_module: str = ""  # flashcard / reading / conversation / practice
    source_ref_id: str = ""
    auto_create_node: bool = False
```

---

## 5. 核心流程

### 5.1 创建知识树

```
用户点击「新建知识树」
  │
  ▼
KnowledgeTreeService.create_tree()
  │
  ▼
写入 knowledge_trees 表，创建根 TreeNode
  │
  ▼
publish(TreeNodeCreated) — 根节点
  │
  ▼
前端进入编辑状态
```

### 5.2 创建树节点并关联认知节点

```
用户在树上右键 → 新建节点
  │
  ▼
KnowledgeTreeService.create_node(label="贝叶斯定理")
  │
  ▼
写入 tree_nodes 表
  │
  ▼
publish(TreeNodeCreated)
  │
  ▼
用户搜索并选择已有认知节点（或让秘书推荐）
  │
  ▼
KnowledgeTreeService.link_to_cognitive_node(
    tree_node_id, cognitive_node_id, role="primary"
)
  │
  ▼
publish(TreeNodeLinkedToCognitiveNode)
  │
  ▼
认知中心订阅 → 更新 cognitive_node 的 metadata.anchors
前端订阅 → 节点立即显示掌握度/紧迫度
```

### 5.3 从练习/阅读/对话导入到知识树

```
用户在错题本/阅读笔记/对话笔记中点击「加入知识树」
  │
  ▼
前端选择目标树与目标节点（或新建节点）
  │
  ▼
KnowledgeTreeService.import_content(
    tree_id, source_module="practice", source_ref_id="err_xxx",
    auto_create_node=True
)
  │
  ▼
如 auto_create_node=True → 创建 TreeNode
  │
  ▼
调用对应壳的查询接口获取材料摘要
  │
  ▼
写入 source_refs
  │
  ▼
publish(TreeImportedContent)
  │
  ▼
认知中心订阅 → 关联 cognitive_node_ids（如材料本身已有）
```

### 5.4 认知状态变化驱动前端视觉更新

```
用户完成练习 → AnswerSubmitted
  │
  ▼
认知中心更新 cognitive_node_projections
  │
  ▼
publish(CognitiveStateChanged)
  │
  ▼
知识树壳订阅 → 查询 CognitiveNodeView
  │
  ▼
WebSocket / 轮询推送到前端
  │
  ▼
前端更新对应树节点的颜色、大小、光晕、标签
```

### 5.5 在树上直接发起学习行动

```
用户点击薄弱节点 → 选择「生成 5 道题」
  │
  ▼
前端调用练习壳组题接口 POST /practice/sessions
  │ 参数：cognitive_node_ids=[node_id], context="from_tree"
  ▼
练习壳创建 PracticeSession
  │
  ▼
publish(PracticeSessionStarted)
  │
  ▼
前端打开练习弹窗或跳转练习壳
```

---

## 6. 关键设计决策与多方案对比

### 6.1 决策 1：用户知识树节点与认知节点是否合一？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 完全合一：一个表同时存用户结构和认知状态 | 简单，无同步问题 | 用户创作自由度被认知模型污染；系统推断节点会出现在用户的树上 | ❌ |
| **B** | **完全分离：tree_nodes + cognitive_nodes，通过关联表连接** | 用户结构与认知数据独立；支持多对多关联；双方可独立演化 | 需要维护关联关系 | ✅ **推荐** |
| C | 树节点是认知节点的子集：认知节点包含树字段 | 认知模型驱动树结构 | 用户创作被系统推断覆盖 | ❌ |

**选择 B 的理由：**
用户痛点明确提到「知识图谱知识树是用户独立的创作」，不能混同于认知数据系统。只有分离，才能让用户自由组织知识结构，同时让系统基于事件推断认知状态，两者通过显式关联映射。

### 6.2 决策 2：认知数据如何可视化？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 只有颜色： proficiency 映射绿→红 | 简单直观 | 无法表达紧迫度和不确定性 | ❌ |
| **B** | **多通道编码：颜色=掌握度，大小=复习紧迫度，光晕=不确定性** | 信息密度高，用户一眼识别薄弱环节 | 需要图例和新手引导 | ✅ **推荐** |
| C | 纯数字标签：节点上显示百分比 | 精确 | 视觉噪音大，不符合「美观现代」要求 | 备选 |

**选择 B 的理由：**
满足用户对「无法查看认知节点数据」和「知识图谱前端落后」的痛点。多通道编码让掌握度、紧迫度、不确定性同时可见。

**具体映射规则：**
- **颜色（掌握度）**：
  - 0.00–0.30：深红（薄弱）
  - 0.30–0.55：橙黄（待加强）
  - 0.55–0.80：浅绿（良好）
  - 0.80–1.00：深绿（精通）
- **大小（紧迫度）**：urgency 越大节点半径越大
- **光晕（不确定性）**：uncertainty 高于阈值时显示脉冲光晕，提示需要更多探测
- **图标（next_action）**：review / practice / explore / deep_processing / idle

### 6.3 决策 3：前端图渲染技术选型

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 自研 SVG + D3.js 力导向 | 完全可控，定制能力强 | 开发成本高，性能优化复杂 | 备选 |
| **B** | **React + Canvas/WebGL 图引擎（如 @antv/g6 / react-flow）** | 成熟、性能好、支持缩放/拖拽/聚焦 | 需要封装学习成本 | ✅ **推荐** |
| C | 保留旧版力导向图逐步改造 | 改动小 | 无法满足用户对「美观现代」的要求 | ❌ |

**选择 B 的理由：**
用户明确不满旧版前端。采用成熟图引擎（如 G6 的 TreeGraph / Graph）可快速实现美观现代的交互，且支持大规模节点渲染。

### 6.4 决策 4：用户结构边与认知边是否共享？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 共享同一张边表 | 无冗余 | 用户创作边和系统推断边语义冲突 | ❌ |
| **B** | **分离：tree_edges（用户）+ knowledge_edges（认知）** | 语义清晰；用户可确认/拒绝系统推断边 | 推断边确认时需要复制 | ✅ **推荐** |
| C | 只有系统推断边，用户只能查看 | 简化数据 | 剥夺用户创作能力 | ❌ |

**选择 B 的理由：**
符合目标架构愿景中「知识图谱的边（用户创作）与认知数据系统的边（推断/确认的认知关系）独立维护」的约束。

---

## 7. API 契约（知识树壳对外暴露）

### 7.1 写操作

| 端点 | 方法 | 输入 | 输出 | 发布事件 |
|------|------|------|------|----------|
| `/trees` | POST | title, tree_type | KnowledgeTree | — |
| `/trees/{tree_id}/nodes` | POST | label, parent_id, node_type, position | TreeNode | TreeNodeCreated |
| `/trees/{tree_id}/nodes/{node_id}` | PATCH | label, color, emoji, position | TreeNode | TreeNodeUpdated |
| `/trees/{tree_id}/nodes/{node_id}/move` | POST | new_parent_id, new_position | TreeNode | TreeNodeMoved |
| `/trees/{tree_id}/nodes/{node_id}/link-cognitive` | POST | cognitive_node_id, role | TreeNode | TreeNodeLinkedToCognitiveNode |
| `/trees/{tree_id}/edges` | POST | source_node_id, target_node_id, edge_type, strength | TreeEdge | TreeEdgeCreated |
| `/trees/{tree_id}/import` | POST | source_module, source_ref_id, target_node_id, auto_create_node | TreeNode | TreeImportedContent |
| `/trees/{tree_id}/viewport` | PUT | view_mode, zoom, pan, filters | ViewportState | TreeViewChanged |

### 7.2 读操作

| 端点 | 方法 | 说明 |
|------|------|------|
| `/trees` | GET | 列出用户的知识树 |
| `/trees/{tree_id}` | GET | 获取知识树元数据 |
| `/trees/{tree_id}/nodes` | GET | 获取树的所有节点（含认知视图） |
| `/trees/{tree_id}/edges` | GET | 获取树的所有边 |
| `/trees/{tree_id}/nodes/{node_id}/materials` | GET | 获取节点关联材料聚合 |
| `/cognitive-nodes` | GET | 查询认知节点列表（用于关联搜索） |
| `/cognitive-nodes/{node_id}/projection` | GET | 获取认知节点投影详情 |

### 7.3 关键 Schema

```python
class TreeNodeResponse(BaseModel):
    node_id: str
    tree_id: str
    label: str
    node_type: str
    parent_id: str | None
    children_ids: list[str]
    position: dict
    color: str
    emoji: str

    # 认知数据（可选，取决于 view_mode）
    cognitive_view: CognitiveNodeView | None
    linked_cognitive_node_ids: list[str]

    # 材料计数
    material_counts: dict[str, int]

    created_at: datetime
    updated_at: datetime


class CognitiveNodeViewResponse(BaseModel):
    cognitive_node_id: str
    label: str
    level: str
    proficiency: float
    uncertainty: float
    urgency: float
    stagnation_days: int
    next_review_at: datetime | None
    next_action_type: str
    display_color: str
    display_size: float
    display_glow: bool
```

---

## 8. 与现代前端可视化方案的集成

### 8.1 推荐技术栈

- **图引擎**：@antv/g6（树图 + 网图双模式）或 react-flow（更贴近 React 生态）
- **状态管理**：Zustand 或 Jotai（管理 viewport、selectedNode、filters）
- **数据同步**：WebSocket 订阅 `CognitiveStateChanged`，实时更新节点视觉
- **布局策略**：
  - 树模式：layered / indented 布局
  - 图模式：force / radial / dagre 布局
  - 分屏模式：左侧树 + 右侧图，选中节点同步高亮

### 8.2 交互设计要点

| 交互 | 行为 |
|------|------|
| 缩放/平移 | 鼠标滚轮缩放，拖拽画布平移，状态保存到 ViewportState |
| 节点拖拽 | 树模式下可调整兄弟顺序；图模式下可自由布局 |
| 点击节点 | 右侧滑出详情面板：认知数据 + 材料聚合 + 快捷操作 |
| 右键节点 | 创建子节点、删除、关联认知节点、发起练习、生成闪卡、创建计划 |
| 筛选器 | 按掌握度、紧迫度、节点类型、来源模块、标签筛选 |
| 聚焦模式 | 选中节点后只显示 N 跳邻居，减少视觉噪音 |
| 搜索 | 实时搜索节点标签和认知节点标签 |

### 8.3 性能策略

- **虚拟化**：超过 500 节点时启用 viewport culling，只渲染可见区域节点。
- **分层加载**：先加载树结构，再异步加载认知视图和材料计数。
- **增量更新**：`CognitiveStateChanged` 只推送变化的节点 ID，前端局部更新。
- **聚合节点**：用户折叠父节点时，子节点的认知状态聚合成父节点显示。

---

## 9. 与其他壳的集成

### 9.1 与对话壳的集成

- 对话中识别到的节点可一键「加入知识树」，携带对话上下文摘要。
- 知识树壳可发起「针对此节点对话」，由对话壳打开 tutor 模式并注入节点上下文。

### 9.2 与练习壳的集成

- 知识树壳按薄弱节点直接调用练习壳组题接口。
- 练习结果通过 `CognitiveStateChanged` 回写节点视觉。

### 9.3 与闪卡壳的集成

- 节点详情中展示关联闪卡，可跳转复习。
- 节点上可「生成闪卡」，调用闪卡壳创建卡片并关联同一认知节点。

### 9.4 与阅读壳的集成

- 阅读材料/笔记可导入知识树，形成「材料引用」类型节点。
- 节点详情中点击材料引用可跳转阅读壳并恢复阅读位置。

### 9.5 与规划壳的集成

- 秘书提案在知识树壳中渲染为节点上的「建议徽章」。
- 用户接受提案后，规划壳生成 plan item，知识树壳在节点详情中展示计划进度。

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 用户结构与认知数据关联关系复杂 | 查询性能差 | 建立 `(tree_id, cognitive_node_id)` 索引；异步加载认知视图 |
| 节点数量大导致前端卡顿 | 体验差 | 虚拟化、分层加载、聚合节点、聚焦模式 |
| 用户误删大量结构 | 数据丢失 | 软删除 + 回收站 + 版本快照 |
| 认知状态更新频繁 | 前端重绘过多 | WebSocket 增量推送 + debounce |
| 图布局抖动 | 视觉不稳定 | 保存用户手动位置；力导向布局稳定后冻结 |

---

## 11. 验收标准

1. 用户可创建多棵知识树，每棵树支持层级树与自由图两种视图。
2. 用户创作的 tree_nodes / tree_edges 与 cognitive_nodes / knowledge_edges 独立存储。
3. 树节点可关联一个或多个认知节点，关联后实时显示掌握度/紧迫度/不确定性。
4. 前端支持缩放、拖拽、筛选、聚焦、搜索，视觉现代美观。
5. 可从对话/练习/阅读/闪卡导入内容到知识树，并正确发布 `TreeImportedContent` 事件。
6. 认知状态变化后，知识树节点视觉在 1 秒内更新。
7. 用户可在树上直接发起练习、生成闪卡、创建计划、开启对话。
8. 节点详情面板聚合展示关联的所有材料（闪卡、错题、笔记、计划等）。

---

## 12. 与现有文档的关系

| 文档 | 关系 |
|------|------|
| `docs/adr/0015-cognitive-probabilistic-graph.md` | 认知节点与边的数学基础 |
| `docs/temp/task0015-target-architecture-vision.md` | 知识树壳在目标架构中的定位（§5.6） |
| `docs/temp/task0016-cognitive-os-kernel-design.md` | 认知状态中心与投影构建器实现依据 |
| 本文档 | 知识树壳详细设计，后续实现依据 |
