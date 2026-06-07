# 对话层级重构方案 — 统一节点模型

## 1. 设计目标

### 1.1 核心思路

将 `partition → domain → topic → conversation` 固定包含链 **去特殊化**，所有层级统一视为"节点"（Node），Conversation 可挂载到任意层级。对话类型统一模型，新增 `type` 和 `parent` 字段。

### 1.2 解决的问题

- 知识树节点（KGNode）探索对话需自动补全层级、挂载到对应节点下
- 空状态临时对话无处存放，需走临时分区
- 分区/领域/专题在代码中被特殊对待，无法统一操作
- 全局对话和节点对话是二分法，不匹配"节点可任意层级"的通用设计

---

## 2. Conversation 模型改造

### 2.1 新增字段

```python
class Conversation(BaseModel):
    # ── 原有字段 ──
    id: str
    topic_id: str                    # 保留兼容，新写入时同步填充
    name: str = ""
    path: list[str] = Field(default_factory=list)
    # ... 其余原有字段不变

    # ── 新增字段 ──
    parent_id: str = ""              # 直接父级 ID（partition_id / domain_id / topic_id）
    parent_type: str = ""            # "partition" | "domain" | "topic"
    type: str = "normal"             # "normal" | "tree_exploration" | "temporary"

    # ── 补全字段（跨级查找用，避免递归遍历） ──
    partition_id: str = ""
    domain_id: str = ""
    topic_id: str = ""               # 改为非必填，向下兼容
```

### 2.2 三种对话类型

| type | 场景 | parent_type | parent_id | 创建方式 |
|------|------|-------------|-----------|----------|
| `normal` | 对话系统常规对话 | topic | topic.id | `/learn` 页面 |
| `tree_exploration` | 知识树节点探索 | partition/domain/topic | 对应层级节点 ID | 知识树点击节点 |
| `temporary` | 空状态临时对话 | partition | 临时分区 ID | 知识树空状态 |

### 2.3 字段设置规则

```
创建时：
  parent_id   = 直接父级 ID
  parent_type = direct parent level
  type        = 按场景填写

  补全字段：沿 parent 链向上补全 partition_id / domain_id / topic_id
  例如 parent_type="topic" 时 → topic -> domain -> partition 回溯填充三级 ID
```

---

## 3. 后端模型与存储层改造

### 3.1 `tree_hierarchy.py` — 通用节点 CRUD

**现状问题**：4 个 level 有各自的 `create_*` 方法、各自的 `factory`、各自的 `collection`。

**改造方案**：

```python
class TreeHierarchyMixin:
    LEVELS = ["partition", "domain", "topic", "conversation"]

    # LEVEL_CONFIG 保留用于 partition/domain/topic 的创建配置
    # conversation 改为通用挂载，不走 LEVEL_CONFIG
```

**`create_node()` 统一入口**：

```python
def create_node(user_id, level, parent_id, name, emoji="", type="normal"):
    """统一创建任意层级节点"""
    data = self._storage.load(user_id)

    if level == "conversation":
        # conversation 特殊处理：不走 LEVEL_CONFIG
        return self._create_conversation(user_id, data, parent_id, name, type)
    else:
        return self._create_level_node(user_id, data, level, parent_id, name, emoji)
```

**`_create_conversation()` 新增**：

```python
def _create_conversation(user_id, data, parent_id, name, type):
    """在任意层级下创建 conversation"""
    # 1. 查找 parent 实体
    parent_type, parent_entity = self._resolve_parent(data, parent_id)

    # 2. 创建 conversation
    conv = Conversation(
        parent_id=parent_id,
        parent_type=parent_type,
        type=type,
        name=name or "新对话",
    )

    # 3. 补全层级 ID
    if parent_type == "partition":
        conv.partition_id = parent_id
    elif parent_type == "domain":
        conv.partition_id = parent_entity.partition_id
        conv.domain_id = parent_id
    elif parent_type == "topic":
        domain = data.domains.get(parent_entity.domain_id)
        conv.partition_id = domain.partition_id if domain else ""
        conv.domain_id = parent_entity.domain_id
        conv.topic_id = parent_id         # 兼容旧字段

    # 4. 根节点创建
    root_node = TreeNode(
        id=parent_entity.root_id if hasattr(parent_entity, "root_id") else str(uuid4()),
        parent_id=parent_id,
        partition_id=conv.partition_id,
        conversation_id=conv.id,
        role="assistant",
        content_blocks=[],
        text_summary="[virtual_root]",
    )
    data.nodes[root_node.id] = root_node
    conv.path.append(root_node.id)

    data.conversations[conv.id] = conv
    self._storage.save(user_id, data)
    return conv
```

**`_resolve_parent()` 辅助方法**：

```python
def _resolve_parent(self, data, parent_id):
    """根据 ID 查找实体，返回 (level, entity)"""
    if parent_id in data.partitions:
        return "partition", data.partitions[parent_id]
    if parent_id in data.domains:
        return "domain", data.domains[parent_id]
    if parent_id in data.topics:
        return "topic", data.topics[parent_id]
    raise ValueError(f"Parent {parent_id} not found")
```

### 3.2 知识树节点探索 → 自动补全层级

**入口**：用户点击知识树上的 KGNode → 触发探索对话。

```python
def ensure_tree_exploration(data, partition_id, kg_node_id, kg_node_label, kg_node_level):
    """
    确保 partition 下存在对应 topic，返回 conversation

    kg_node_level: "partition" | "domain" | "topic" | "concept"
    规则：
      - partition 级 → parent = partition_id
      - domain 级   → 检查是否有同名 domain，无则创建 → parent = domain_id
      - topic/concept 级 → 检查是否有同名 domain/topic 链路，无则自动创建
    """

    if kg_node_level == "partition":
        # 直接挂在 partition 下
        parent_id = partition_id
        parent_type = "partition"
    elif kg_node_level == "domain":
        parent_id = _ensure_domain(data, partition_id, kg_node_label)
        parent_type = "domain"
    else:
        # topic/concept → 补全 domain → topic 链路
        parent_id = _ensure_topic(data, partition_id, kg_node_label)
        parent_type = "topic"

    # 查找已有探索会话
    for conv in data.conversations.values():
        if (conv.parent_id == parent_id
            and conv.type == "tree_exploration"
            and conv.metadata.get("bound_node_id") == kg_node_id):
            return conv

    # 创建新探索会话
    conv = Conversation(
        parent_id=parent_id, parent_type=parent_type,
        type="tree_exploration",
        metadata={"bound_node_id": kg_node_id, "bound_node_label": kg_node_label},
    )
    # ... 补全层级 ID、创建 root_node、保存
    return conv


def _ensure_domain(data, partition_id, name):
    """在 partition 下查找或创建同名 domain"""
    for d in data.domains.values():
        if d.partition_id == partition_id and d.name == name:
            return d.id
    domain = Domain(partition_id=partition_id, name=name)
    data.domains[domain.id] = domain
    return domain.id


def _ensure_topic(data, partition_id, name):
    """在 partition 下查找或创建 domain → topic 链路"""
    # 先找或创建 domain（用 partition_id 的默认 domain 或同名 domain）
    domain_id = _ensure_domain(data, partition_id, name)
    # 在 domain 下找或创建 topic
    for t in data.topics.values():
        if t.domain_id == domain_id and t.name == name:
            return t.id
    topic = Topic(domain_id=domain_id, name=name)
    data.topics[topic.id] = topic
    return topic.id
```

### 3.3 临时分区 & 临时对话

```python
def ensure_temporary_partition(data):
    """获取或创建临时分区"""
    for p in data.partitions.values():
        if getattr(p, "is_temp", False):
            return p
    p = Partition(name="💬 临时对话", subject="", direction="subject",
                  emoji="💬", color="#888888", is_temp=True)
    # 创建 root_node
    data.partitions[p.id] = p
    return p


def create_temporary_conversation(user_id):
    """空状态 → 创建临时对话"""
    data = storage.load(user_id)
    temp_part = ensure_temporary_partition(data)
    conv = Conversation(
        parent_id=temp_part.id, parent_type="partition",
        type="temporary", partition_id=temp_part.id,
        name="临时会话",
        metadata={"type": "temporary"},
    )
    # ... 创建 root_node, 保存
    return conv
```

### 3.4 临时对话迁移

```python
def migrate_temporary_conversation(user_id, conv_id, target_partition_id, target_type="normal"):
    """
    将临时对话迁移到正式分区

    途径：
      1. 迁到已有分区 → target_partition_id 指定
      2. 新建分区迁移 → 先创建分区再调用此方法

    操作：
      - 修改 conv.parent_id = target_partition_id
      - 修改 conv.parent_type = "partition"
      - 修改 conv.type = target_type ("normal" 或 "tree_exploration")
      - 修改 conv.partition_id = target_partition_id
      - 修改 conv.domain_id / conv.topic_id 为空（或按需补充）
      - 所有消息的 partition_id 更新为 target_partition_id
      - 如果原临时分区无其他活跃内容，清理临时分区
    """
    data = storage.load(user_id)
    conv = data.conversations.get(conv_id)
    if not conv or conv.type != "temporary":
        raise ValueError("Only temporary conversations can be migrated")

    # 更新对话挂载
    conv.parent_id = target_partition_id
    conv.parent_type = "partition"
    conv.type = target_type
    conv.partition_id = target_partition_id
    conv.domain_id = ""
    conv.topic_id = ""

    # 更新所有消息的 partition_id
    for nid in conv.path:
        node = data.nodes.get(nid)
        if node:
            node.partition_id = target_partition_id

    # 清理空临时分区
    _cleanup_empty_temp_partition(data, conv_id)

    storage.save(user_id, data)
```

### 3.5 前端 AI 工具接口（后续扩展）

```python
# 对话系统 AI 工具调用端点 — 未来支持
TOOL_REGISTRY = {
    "migrate_conversation": migrate_temporary_conversation,
    "rename_node": tree_ops.rename_node,          # 通用重命名（任意层级）
    "move_node": move_conversation,               # 移动会话到其他父级
    "copy_node": copy_conversation,               # 复制会话
    "delete_node": tree_ops.delete_node,           # 通用删除
    "create_partition": tree_ops.create_partition, # 新建分区
}
```

---

## 4. 后端 API 端点改造

### 4.1 创建对话端点 — 通用化

```python
# 现有：POST /tree/conversation — 固定 topic_id
# 改为：POST /tree/conversation — 接受任意 parent_id

@router.post("/tree/conversation")
async def create_conversation(body: CreateConversationRequest):
    """在任意层级下创建对话"""
    conv = tree_ops.create_conversation(
        USER_ID, body.parent_id, body.name, type=body.type,
    )
    return {"conversation": conv}
```

### 4.2 知识树探索对话端点

```python
# 重构现有 ai-chat 端点
@router.post("/{partition_id}/explore")
async def explore_node(partition_id: str, body: ExploreRequest):
    """在知识树上点击节点，创建/恢复探索对话"""
    conv = tree_ops.ensure_tree_exploration(
        USER_ID, partition_id, body.node_id,
        body.node_label, body.node_level
    )
    return {"conversation_id": conv.id, "messages": [...]}
```

### 4.3 临时对话端点

```python
@router.post("/temporary/conversation")
async def start_temporary_conversation():
    """空状态创建临时对话"""
    conv = tree_ops.create_temporary_conversation(USER_ID)
    return {"conversation_id": conv.id}


@router.post("/temporary/conversation/{conv_id}/migrate")
async def migrate_conversation(conv_id: str, body: MigrateRequest):
    """迁移临时对话到正式分区"""
    result = tree_ops.migrate_temporary_conversation(
        USER_ID, conv_id, body.target_partition_id,
    )
    return {"ok": True, "conversation_id": conv_id, "partition_id": body.target_partition_id}
```

### 4.4 查询对话列表 — 按类型/父级过滤

```python
@router.get("/tree/conversation")
async def list_conversations(
    parent_id: str = None,
    parent_type: str = None,
    type: str = None,          # normal / tree_exploration / temporary
):
    """对话列表，支持按父级和类型过滤"""
    data = storage.load(USER_ID)
    convs = list(data.conversations.values())

    if parent_id:
        convs = [c for c in convs if c.parent_id == parent_id]
    if parent_type:
        convs = [c for c in convs if c.parent_type == parent_type]
    if type:
        convs = [c for c in convs if c.type == type]

    return {"conversations": [c.model_dump() for c in convs]}
```

---

## 5. 前端改造

### 5.1 知识树页面状态重构

`KnowledgeTreePage.tsx` — `dialogMode` 从二分改为节点绑定：

```typescript
// 旧：mode: "global" | "node"
// 新：对话状态统一

interface DialogState {
  type: "normal" | "tree_exploration" | "temporary";
  conversationId: string;
  parentId: string;        // 节点/分区 ID
  parentType: "partition" | "domain" | "topic";
  boundNode?: GraphNode;   // 绑定 KGNode（如果是 tree_exploration）
}
```

### 5.2 空状态 — 临时对话入口

`NoPartitionState` 新增：

```
┌─────────────────────────────────────────┐
│            🕳️ 还没有学习分区              │
│                                           │
│    创建分区开始规划你的学习路径             │
│    或者先和 AI 临时聊聊天探索学习方向       │
│                                           │
│  ┌─────────────────┐  ┌───────────────┐  │
│  │  ✨ 创建学习分区 │  │  💬 临时对话 │  │
│  └─────────────────┘  └───────────────┘  │
│                                           │
│        快捷模板: [高等数学] [Python] ...    │
└─────────────────────────────────────────┘
```

点击"临时对话" → 调用 `POST /api/conversations/tree/conversation` 传入 `type: "temporary"` → 自动创建临时分区 + conversation → 进入对话界面。

对话界面底部/顶部显示"迁移到分区"按钮。

### 5.3 迁移面板

临时对话中的迁移操作：

```
┌─────────────────────────────────────┐
│ 💬 临时对话                          │
│                                     │
│ [消息列表...]                        │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 📦 此对话为临时对话              │ │
│ │ 迁移到正式分区以永久保存并生成    │ │
│ │ 知识树                          │ │
│ │                                 │ │
│ │ [选择已有分区 ▼]  [新建分区]     │ │
│ │ [让 AI 处理]                     │ │
│ └─────────────────────────────────┘ │
│ ┌──────────────────────────────┐    │
│ │ 输入...           [发送]     │    │
│ └──────────────────────────────┘    │
└─────────────────────────────────────┘
```

三种迁移途径：

1. **选择已有分区** — 下拉列出 `partition_id` 列表，确认后迁移
2. **新建分区** — 弹出创建分区表单（名称+图标），创建后迁移
3. **AI 迁移** — 用户输入"把这个对话迁移到数学分区"或"帮我创建一个高等数学分区并迁移" → 对话系统通过工具调用执行

### 5.4 DialogContainer — 通用对话面板

`DialogContainer` 从接收 `mode: "global" | "node"` 改为接收 `dialogState: DialogState`：

```typescript
interface DialogContainerProps {
  dialogState: DialogState;
  onDialogStateChange: (s: DialogState) => void;
  // ... 其余 props
}
```

渲染逻辑：
- `type === "tree_exploration"` → 显示 `boundNode.label` 作用域提示
- `type === "temporary"` → 显示迁移提示横幅
- `type === "normal"` → 标准对话

### 5.5 知识树节点点击 → 创建探索对话

```typescript
const handleNodeExplore = async (node: GraphNode) => {
  // 获取节点在 partition 下的层级
  const level = node.level || "concept";  // partition | domain | topic | concept

  const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/explore`, {
    method: "POST",
    body: JSON.stringify({
      node_id: node.id,
      node_label: node.label,
      node_level: level,
    }),
  });
  const data = await res.json();

  setDialogState({
    type: "tree_exploration",
    conversationId: data.conversation_id,
    parentId: node.id,
    parentType: "topic",
    boundNode: node,
  });
};
```

---

## 6. 存储层兼容

### 6.1 JSON Storage

`Conversation` 新增字段写入 `userData.json`，旧数据中 `topic_id` 保留兼容读取：

```python
# 加载时兼容
if not hasattr(conv, "parent_id") or not conv.parent_id:
    conv.parent_id = conv.topic_id
    conv.parent_type = "topic"
    conv.type = "normal"
```

### 6.2 PG Storage

`conversation_branches` 表加列：

```sql
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS parent_id TEXT;
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS parent_type TEXT DEFAULT 'topic';
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'normal';
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS domain_id TEXT DEFAULT '';
ALTER TABLE conversation_branches ADD COLUMN IF NOT EXISTS partition_id TEXT DEFAULT '';
```

---

## 7. 分阶段实施计划

### Phase A：后端模型 + 存储 （核心）

1. `Conversation` 模型新增字段（`parent_id`, `parent_type`, `type`, `partition_id`, `domain_id`）
2. `tree_hierarchy.py` 新增 `_create_conversation()`, `_resolve_parent()`, `ensure_tree_exploration()`
3. `tree_ops` 暴露 `create_temporary_conversation()`, `migrate_temporary_conversation()`
4. PG storage 加列

### Phase B：后端 API

1. `POST /tree/conversation` — 改为通用创建（接受任意 `parent_id`）
2. `POST /{partition_id}/explore` — 知识树探索对话端点
3. `POST /temporary/conversation` — 临时对话
4. `POST /temporary/conversation/{id}/migrate` — 迁移
5. `GET /tree/conversation` — 增加 `type`/`parent_id` 过滤

### Phase C：前端知识树对话重构

1. DialogState 类型重构（`"global"|"node"` → 统一状态）
2. DialogContainer / FloatDialogWrapper 接入真实 API
3. 临时对话入口 + 迁移面板
4. 知识树节点点击 → 探索对话流程

### Phase D：AI 工具集（后续）

1. 注册 `migrate_conversation` / `rename_node` / `move_node` 等工具
2. classifier 中处理临时对话的迁移意图

---

## 8. 边界情况

| 场景 | 处理 |
|------|------|
| 临时分区无活跃对话 | 自动清理临时分区和孤 root_node |
| 多次迁移 | 不允许（`type` 已为 `normal` 的不可再迁移） |
| 分区下已有同名 domain/topic | create_or_get，不重复创建 |
| 删除父级节点 | 级联删除其下的 conversation 和消息（同现有 `_delete_node`） |
| 知识树节点重命名 | 不影响已有探索对话（通过 `bound_node_id` 关联） |
