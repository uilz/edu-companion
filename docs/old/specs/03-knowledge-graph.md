# 数据规格：知识图谱

> 知识树是知识的结构化可视化，支持力导向图、思维导图、依赖图三种视图。
>
> 源码：[backend/app/schemas/conversation.py](../../backend/app/schemas/conversation.py)（KGNode/KGEdge/KnowledgeGraph）

---

## KnowledgeGraph 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `partition_id` | str | 所属分区 ID |
| `name` | str | 图谱名称 |
| `nodes` | dict[str, KGNode] | 节点字典（ID → 节点） |
| `edges` | list[KGEdge] | 边列表 |
| `generated_by` | str | 生成方式（ai/manual） |
| `version` | int | 版本号 |

## KGNode（知识图谱节点）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `label` | str | 节点显示名称 |
| `description` | str | 节点描述 |
| `mastery` | float | 掌握度 [0,1] |
| `mastery_level` | str | 掌握等级（中文描述） |
| `priority` | int | 优先级 |
| `tags` | list[str] | 标签 |
| `created_by` | str | 创建方式（ai/user） |
| `conversation_ids` | list[str] | 关联的会话 ID 列表 |

## KGEdge（知识图谱边）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `from_id` | str | 源节点 ID |
| `to_id` | str | 目标节点 ID |
| `relation` | str | 关系类型（默认 `prerequisite`） |
| `label` | str | 边标签 |
| `weight` | float | 关联强度（默认 1.0） |

## 边类型

| relation | 语义 | 图例 |
|----------|------|------|
| `prerequisite` | A → B：必须先学 A 再学 B | 有向 |
| 其他自定义 | 用户/AI 定义的关系 | 视定义 |

## 波纹扩展

知识图谱支持 BFS 波纹扩展：

```
从节点 A 出发
  第 1 层：A 的直接子节点 + 依赖边节点
  第 2 层：子节点的子节点
  ...
  第 N 层：直到达到最大深度或节点数上限
```

### 作用域约束

AI 对话编辑时的操作边界：

- 只能操作当前节点及其 BFS 子孙节点
- 不能操作同层节点、父节点或树外节点
- 后端辅助：`_get_descendant_ids(graph, node_id)` + `_find_scope_violations()`

## 视图类型

| 视图 | 说明 |
|------|------|
| 力导向图 (ForceGraph) | 自由布局，适合探索关联 |
| 思维导图 (MindMap) | 树形布局，适合自上而下学习 |
| 依赖图 (DAG) | DAG 布局，突出前置依赖关系 |
