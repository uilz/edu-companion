# Project 事件 schema

> Project 模块产生和消费的事件定义。

**ADR**：[`docs/adr/0001-project-based-exploration.md`](../../adr/0001-project-based-exploration.md)

---

## 1. 事件清单

| 事件 | 触发时机 | 类别 |
|------|---------|------|
| `ProjectCreated` | 用户创建项目 | 生命周期 |
| `ProjectArchived` | 用户归档项目 | 生命周期 |
| `ProjectCompleted` | 所有节点完成 | 生命周期 |
| `ProjectMilestoneMarked` | 用户标记里程碑 | 里程碑 |
| `ProjectNodeCreated` | 创建节点 | 节点操作 |
| `ProjectNodeUpdated` | 修改节点 | 节点操作 |
| `ProjectNodeVersionCreated` | 新版本入栈 | 节点操作 |
| `ProjectNodeRolledBack` | 节点回滚 | 节点操作 |
| `ProjectNodeCompleted` | 节点标记完成 | 节点操作 |
| `ProjectNodeArchived` | 节点归档 | 节点操作 |
| `ProjectNodeExported` | 节点导出为 FlashCard/Material/注释 | 跨模块输出 |

---

## 2. 事件 Schema

### 2.1 生命周期

```python
class ProjectCreated(DomainEvent):
    project_id: str
    user_id: str
    name: str
    template_id: str | None
    template_version: int | None
    created_at: datetime

class ProjectArchived(DomainEvent):
    project_id: str
    user_id: str
    archived_at: datetime

class ProjectCompleted(DomainEvent):
    project_id: str
    user_id: str
    total_nodes: int
    completed_nodes: int
    duration_days: int
    completed_at: datetime
```

### 2.2 里程碑

```python
class ProjectMilestoneMarked(DomainEvent):
    project_id: str
    user_id: str
    milestone_id: str
    milestone_name: str
    snapshot_data: dict  # {"node_count": ..., "completed_count": ..., "link_count": ...}
    is_user_marked: bool
    marked_at: datetime
```

### 2.3 节点操作

```python
class ProjectNodeCreated(DomainEvent):
    project_id: str
    user_id: str
    node_id: str
    parent_id: str | None
    type: int  # 1-7
    title: str
    created_at: datetime

class ProjectNodeUpdated(DomainEvent):
    project_id: str
    user_id: str
    node_id: str
    version: int
    changed_fields: list[str]  # 字段级粒度
    updated_at: datetime

class ProjectNodeVersionCreated(DomainEvent):
    project_id: str
    user_id: str
    node_id: str
    version_number: int
    is_rollback: bool
    rolled_back_from_version: int | None
    change_source: Literal["user_edit", "api", "rollback", "system"]
    created_at: datetime

class ProjectNodeRolledBack(DomainEvent):
    project_id: str
    user_id: str
    node_id: str
    from_version: int
    to_version: int
    rolled_back_fields: list[str]
    rolled_back_at: datetime

class ProjectNodeCompleted(DomainEvent):
    project_id: str
    user_id: str
    node_id: str
    completion_method: Literal["manual", "auto", "imported"]  # 手动 / 关联练习完成触发 / 从外部导入
    linked_node_ids: list[str]  # 关联的 CognitiveNode（与 LanguageRoom/Reading 命名保持一致）
    completed_at: datetime

class ProjectNodeArchived(DomainEvent):
    project_id: str
    user_id: str
    node_id: str
    archived_at: datetime
```

### 2.4 跨模块输出

```python
class ProjectNodeExported(DomainEvent):
    """节点内容导出到其他模块"""
    project_id: str
    user_id: str
    node_id: str
    # target_module 必须为 CrossModuleTarget 枚举的合法值（来自 shared.events.CrossModuleTarget）
    #   - flashcard        : 导出为 FlashCard
    #   - material         : 导出为阅读材料
    #   - cognitive_node   : 导出为知识点
    #   - plan             : 创建计划项
    #   - language_room    : 导出为语言房间话题
    target_module: CrossModuleTarget = CrossModuleTarget.FLASHCARD
    target_ref_id: str
    export_data: dict  # 导出内容快照
    exported_at: datetime
```

---

## 3. 事件消费者

### 3.1 本模块消费

- `FlashCardCreated`（`source='project'`）→ 在节点详情显示关联的 FlashCard
- `CognitiveNodeMetadataChanged` → 更新节点的关联显示（描述/标签/层级等元数据变化）
- `CognitiveNodeLinked` → 更新节点与 CognitiveNode 的链接展示
- `AnswerSubmitted` → 更新关联节点的完成进度

### 3.1.1 Project → PlanItemCompleted 回写（不重发源事件）

Project 消费 `PlanItemCompleted` 后**不**重新发布 `ProjectNodeCompleted`，避免与 Planning 形成事件循环。

幂等检查：
- 通过 `plan_item_id` 作为幂等键
- 已处理的 `plan_item_id` 直接丢弃
- 重复触发不产生新事件

### 3.2 其他模块消费

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `ProjectNodeCompleted` | 秘书系统 | 记录项目活动，更新习惯分析 |
| `ProjectMilestoneMarked` | 全局事件流 | 时间线展示 |
| `ProjectNodeExported`（target=flashcard）| FlashCard 模块 | 在卡片页面显示项目来源 |
| `ProjectNodeExported`（target=cognitive_node）| 知识图谱 | 在知识点页面显示项目引用 |
| `ProjectNodeExported`（target=plan）| 规划模块 | 在计划项显示项目来源 |
| `ProjectCompleted` | 秘书系统 | 项目完成记录，更新"项目级习惯" |

---

## 4. 事件粒度

### 4.1 节点级 vs 项目级

| 粒度 | 事件 |
|------|------|
| **节点级** | `ProjectNodeCreated` / `ProjectNodeUpdated` / `ProjectNodeCompleted` / `ProjectNodeArchived` / `ProjectNodeRolledBack` |
| **项目级** | `ProjectCreated` / `ProjectArchived` / `ProjectCompleted` / `ProjectMilestoneMarked` |

### 4.2 字段级版本

- `ProjectNodeVersionCreated.changed_fields` 是**字段列表**（如 `["title", "content"]`）
- 一次修改只对**被修改字段**入栈新版本
- 未修改字段不产生新版本

### 4.3 跨模块输出粒度

- `ProjectNodeExported` 每次**单个目标**发一次事件
- 例如：节点内容同时导出到 FlashCard 和 Material，发**两次** `ProjectNodeExported` 事件

---

## 5. 不触发认知状态更新的事件

**关键设计原则**：Project 模块事件**不**直接更新 `CognitiveNode.Belief`。

理由：

- 节点创建/完成是**用户的整理行为**，不是**学习行为**
- `Belief` 的合法来源：练习答题、FlashCard 复习、对话深度参与、错题标记
- 项目节点关联到 `CognitiveNode` 时，只更新关联显示，**不**改变 Belief

**例外**：当 `ProjectNodeExported.target='cognitive_node'` 且类型是"个人注释"时，触发"个人注释"事件（由知识图谱模块消费），但不更新 Belief（保持 0001 与现有系统的设计一致）。
