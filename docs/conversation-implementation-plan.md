# 对话系统技术实现方案

> 基于 docs/conversation-system-design.md v0.2.2
> 创建: 2026-05-17

---

## 实现阶段

### Phase 1: 核心数据层（本次实现）

**目标**：后端能存储、读取、操作树结构对话

1. **数据模型定义** (`backend/app/schemas/conversation.py`)
   - TreeNode, ContentBlock, FileRecord, Partition, Branch, LinkNode
   - 所有Pydantic模型

2. **存储引擎** (`backend/app/services/storage.py`)
   - JSON文件读写，按用户隔离
   - 树节点CRUD
   - 分区/分支管理
   - 活跃路径缓存

3. **树操作服务** (`backend/app/services/tree_ops.py`)
   - 添加消息（挂载到分支）
   - 创建分支（从任意节点分叉）
   - 修改消息（在父节点下挂新节点）
   - 删除消息（软删除 + re-parent）
   - 摘要生成（调用LLM）

4. **分类服务** (`backend/app/services/classifier.py`)
   - Embedding计算（Granite R2）
   - 分区匹配（余弦相似度）
   - 分支决策规则
   - 跨分区标记

5. **文件服务** (`backend/app/services/file_service.py`)
   - 上传存储到Branch Workspace
   - FileRecord管理
   - 异步处理（OCR/ASR/文档提取）

6. **对话API** (`backend/app/api/conversation.py`)
   - POST /api/conversations/message — 发送消息（含分类+回复）
   - GET /api/conversations/partitions — 获取分区列表
   - GET /api/conversations/partitions/{id}/branches — 获取分支列表
   - GET /api/conversations/branches/{id}/messages — 获取分支消息
   - POST /api/conversations/branches/{id}/switch — 切换活跃分支
   - POST /api/conversations/branches — 创建新分支
   - PUT /api/conversations/messages/{id} — 修改消息
   - DELETE /api/conversations/messages/{id} — 删除消息
   - POST /api/conversations/files/upload — 上传文件

### Phase 2: 前端对话界面（后续）

### Phase 3: 多模态处理管线（后续）

### Phase 4: 摘要/压缩/整理（后续）

---

## Phase 1 文件清单

```
backend/app/
├── schemas/
│   └── conversation.py        # 所有数据模型
├── services/
│   ├── storage.py             # 存储引擎
│   ├── tree_ops.py            # 树操作
│   ├── classifier.py          # 分类服务
│   ├── file_service.py        # 文件服务
│   └── embedding.py           # Embedding服务
├── api/
│   └── conversation.py        # 对话API路由
```
