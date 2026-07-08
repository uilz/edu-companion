# ADR 0005: 自由目录节点结构

用统一 `DirectoryNode` 取代固定三级层次 (Partition/Domain/Topic), 用户自由创建任意深度目录。

## Status

Accepted (updated 2026-06-12: conv_type→kind, conv 为末端节点)

## Context

原对话系统使用固定三级目录: Partition → Domain → Topic → Conversation。Conversation 只能挂在 Topic 下, 缺乏灵活性。

问题:
- 用户无法按自己的习惯组织知识结构
- 三级对某些场景过深 (简单学科), 对某些场景过浅 (复杂学科)
- AI 分类器需要硬编码层级逻辑, 难以适应多样化内容
- 子支 (sub-branch) 作为特例实现, 与主结构不一致

同时, MessageNode 与 CognitiveNode 的直接耦合 (`discussed_skill_ids`) 导致模块间依赖过紧, 需要解耦。

## Decision

### 1. DirectoryNode — 统一目录节点

```python
class DirectoryNode(BaseModel):
    id: str
    user_id: str
    parent_id: str | None
    node_type: str                # "dir" | "conv" (结构)
    kind: str                     # "general" | "temp" | "practice" | "secretary" (行为)
    
    path: list[str]               # 从根到自身的完整路径 ID 链
    children_order: list[str]     # 直接子级 ID 有序列表 (dir+conv 统一)
    
    conv_message_ids: list[str]   # conv 类专属
    payload: dict                 # conv 类专有数据 (原 Conversation 专有字段)
    
    # 名称三字段
    name: str                     # 显示用名: user_name or ai_name or "新会话"
    user_name: str | None         # 用户手动设置, None 则回退 ai_name
    ai_name: str                  # organize_conversation 时从 summary_short 截取
    
    # 组织工具
    summary_short: str            # 短摘要 → organize_conversation 生成
    summary_dirty: bool
    
    created_at: float
    updated_at: float
    metadata: dict
```

- `node_type="dir"`: 目录容器, 可挂子 dir 和子 conv
  - `kind="general"`: 普通目录
  - `kind="temp"`: 临时目录 (唯一, 托管 temp conv, 不可删除/重命名)
- `node_type="conv"`: 会话, 末端节点 (不能有子节点)
  - `kind="general"`: 普通会话, 挂在用户目录下
  - `kind="temp"`: 临时会话, 挂在 `dir(kind=temp)` 下, 首条消息触发分类器
  - `kind="practice"`: 练习会话
  - `kind="secretary"`: 秘书会话
- conv 不可挂子节点 — 子支概念取消
- 无深度上限

### 2. MessageNode — 改名并解耦

```python
class MessageNode(BaseModel):
    id: str
    directory_id: str             # 所属 conv 节点 ID (原 conversation_id)
    parent_id: str
    children_ids: list[str]
    content_blocks: list[ContentBlock]
    text_summary: str
    role: str
    timestamp: float
    token_count: int
    # 无 discussed_skill_ids — 通过 events 表事件化
    # 无 partition_id/conversation_id — 统一用 directory_id
    ...
```

### 3. 存储变化

```python
class UserData(BaseModel):
    # 旧: partitions + domains + topics + conversations + nodes(消息)
    # 新:
    directory_nodes: dict[str, DirectoryNode]  # dir + conv 统一
    messages: dict[str, MessageNode]           # 消息
    response_blocks: dict[str, ResponseBlock]
    ...
```

### 4. 侧边栏

递归渲染 DirectoryNode 树, 所有节点一视同仁。
- `node_type` 决定图标 (dir→📁, conv→💬)
- `kind` 决定角标/样式 (temp→角标, practice/secretary→标签)
- Store: `selectedNodeId` + `selectedNodeType` 取代旧四个字段

### 5. URL 模式

从 `/learn?p=xxx&d=yyy&t=zzz&c=...` 改为:
```
/learn?node_id=xxx
```
前端通过 node_id 读取 DirectoryNode, 从 `path` 字段获取祖先链。

## Consequences

- **正面**: 用户自由组织知识结构, 无需受固定层级约束
- **正面**: conv 末端化消除子支特例
- **正面**: URL 简化, 单一 node_id 参数
- **正面**: MessageNode 与 CognitiveNode 解耦, 通过事件记录追溯
- **负面**: 需要迁移现有 Partition/Domain/Topic/Conversation → DirectoryNode
- **负面**: 需要重构前端 store/侧边栏/URL 处理

## Considered Options

- **保留三级加扩展字段**: Partition/Domain/Topic 加 depth 允许跳过。否决 — 无法突破"固定三级"的概念限制, 代码复杂度反而更高。
- **只用 conv 不用 dir**: 所有节点都是 conv, 通过 type 区分纯目录行为。否决 — 语义不清晰, 纯目录节点不需要 conv 相关字段。
- **保持 TreeNode 原名**: 不改名。否决 — 与 DirectoryNode 都带 "node" 但语义不同, 改名 MessageNode 更清晰。
- **conv 允许挂子节点 (子支)**: 最初采用, 后否决 — 与 conv 作为对话容器的语义冲突, 末端化更简单。
