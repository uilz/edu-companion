# 知识图谱 · 编辑 API

> 节点和边的 CRUD 操作，支持 AI 辅助编辑。

---

## 节点编辑

| 操作 | 端点 | 说明 |
|------|------|------|
| 创建 | `POST /api/knowledge/graph/{pid}/node` | 在指定分区下创建节点 |
| 编辑 | `PATCH /api/knowledge/graph/{pid}/node/{nid}` | 修改标签/描述/标签 |
| 删除 | `DELETE /api/knowledge/graph/{pid}/node/{nid}` | 级联删除关联边 |
| 移动 | — | 修改 parent_id 实现 |
| 合并 | — | 将两个节点合并为一个 |
| 拆分 | — | 将一个节点拆分为多个 |

## 边编辑

| 操作 | 端点 | 说明 |
|------|------|------|
| 创建 | `POST /api/knowledge/graph/{pid}/edge` | 创建依赖边 |
| 删除 | `DELETE /api/knowledge/graph/{pid}/edge/{eid}` | 删除边 |

## AI 辅助编辑

| 操作 | 端点 | 说明 |
|------|------|------|
| AI 生成 | `POST /api/knowledge/graph/{pid}/generate` | 从对话自动生成完整知识树 |
| AI 扩充 | `POST /api/knowledge/graph/{pid}/ai-expand` | 为节点 AI 生成子节点 |
| AI 编辑 | `POST /api/knowledge/graph/{pid}/ai-edit` | AI 修改节点内容 |
| AI 对话 | `POST /api/knowledge/graph/{pid}/ai-chat` | 节点级 AI 对话编辑（作用域约束） |

## 会话关联

| 操作 | 端点 | 说明 |
|------|------|------|
| 关联 | `POST /api/knowledge/graph/{pid}/link-conversation` | 将会话关联到节点 |
| 解除 | `DELETE /api/knowledge/graph/{pid}/link-conversation/{nid}/{cid}` | 解除关联 |

关联后，节点详情面板会显示关联的会话列表，方便跳转。
