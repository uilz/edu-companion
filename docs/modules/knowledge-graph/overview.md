# 知识图谱

> 知识树的结构化可视化，支持三种视图（力导向图/思维导图/依赖图）和 AI 对话编辑。

---

## 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 图谱查询 | 节点/边 CRUD | ✅ 已实现 |
| AI 生成 | 自动生成完整知识树 | ✅ 已实现 |
| AI 扩充 | 节点子级智能补充 | ✅ 已实现 |
| AI 编辑 | 节点内容智能编辑 | ✅ 已实现 |
| 作用域探索 | 节点级 AI 对话编辑 | ✅ 已实现 |
| 双向联动 | 对话 ↔ 图谱推荐 | ✅ 已实现 |
| 图遍历 | BFS/DFS 波纹扩展 | ✅ 已实现 |

## 实现文档

| 文档 | 说明 |
|------|------|
| [visualization.md](visualization.md) | 力导向图 vs 思维导图 vs 依赖图 |
| [editing-api.md](editing-api.md) | 节点编辑（移动/合并/拆分） |

## API 概览（14 端点）

| 方法 | 路由 | 功能 |
|------|------|------|
| GET | `/api/knowledge/graph/partitions` | 分区列表 |
| GET | `/api/knowledge/graph/recommendation` | 双向推荐 |
| GET | `/api/knowledge/graph/{pid}` | 获取知识树 |
| POST | `/api/knowledge/graph/{pid}/generate` | AI 生成知识树 |
| POST | `/api/knowledge/graph/{pid}/node` | 创建节点 |
| PATCH | `/api/knowledge/graph/{pid}/node/{nid}` | 编辑节点 |
| DELETE | `/api/knowledge/graph/{pid}/node/{nid}` | 删除节点 |
| POST | `/api/knowledge/graph/{pid}/edge` | 创建边 |
| DELETE | `/api/knowledge/graph/{pid}/edge/{eid}` | 删除边 |
| POST | `/api/knowledge/graph/{pid}/ai-expand` | AI 扩充子节点 |
| POST | `/api/knowledge/graph/{pid}/ai-edit` | AI 编辑节点 |
| POST | `/api/knowledge/graph/{pid}/link-conversation` | 关联会话 |
| DELETE | `/api/knowledge/graph/{pid}/link-conversation/{nid}/{cid}` | 解除关联 |
| POST | `/api/knowledge/graph/{pid}/ai-chat` | AI 对话编辑 |

## 双向联动

### 对话 → 知识树
- 7 组关键词模式检测
- 流式事件 `tree_recommendation` → 前端 Banner

### 知识树 → 对话
- `[RECOMMEND:tree_complete]` → 探索完成，推荐去对话
- `[RECOMMEND:deep_dive:node_id:label]` → 深入某个知识点
- `[RECOMMEND:parent:node_id:label]` → 切换到父节点关联会话
