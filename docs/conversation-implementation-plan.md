# 对话系统技术实现方案

> 基于 docs/conversation-system-design.md v4.0
> 最后更新: 2026-05-19

---

## v4 架构概览

**分区 → 领域 → 专题 → 对话** 四级体系，编辑消息内联版本切换（`<` `>`）。

### 关键变化（v3→v4）

| 旧 (v3) | 新 (v4) |
|---|---|
| 分区 → 分支 | 分区 → 领域 → 专题 → 对话 |
| `branch_id` | `conversation_id` |
| 编辑消息 = 新分支 | 编辑消息 = 内联版本 (`children_ids`) |
| 手动选择分区 | 自动路由 (auto_resolve) |
| 无切换感知 | context_switch 推荐事件 |

## 实现阶段

### Phase 1: 核心数据层 ✅

1. **数据模型** — `Partition / Domain / Topic / Conversation / TreeNode`
2. **存储引擎** — JSON 文件读写，按用户隔离
3. **树操作服务** — `tree_ops.py`: 四级树 CRUD + 内联版本切换
4. **分类服务** — `classifier.py`: 三级分类 (分区→领域→专题) + auto_resolve
5. **对话 API** — 
   - `POST /api/conversations/message` — 自动路由 + 发送消息
   - `GET /api/conversations/partitions` / `POST/PATCH/DELETE`
   - `GET /api/conversations/partitions/{id}/domains` / `POST/PATCH/DELETE`
   - `GET /api/conversations/domains/{id}/topics` / `POST/PATCH/DELETE`
   - `GET /api/conversations/topics/{id}/conversations` / `POST/PATCH/DELETE`
   - `WebSocket /api/conversations/ws` — 流式对话 + context_switch 事件
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

---

## 实施完成状态

### Phase 1: 后端核心 ✅
- [x] 数据模型 (schemas/conversation.py)
- [x] 存储引擎 (services/storage.py)
- [x] 树操作 (services/tree_ops.py)
- [x] 分类服务 (services/classifier.py)
- [x] LLM对话 (services/conversation_llm.py)
- [x] 工具执行器 (services/tool_executor.py)
- [x] 后台任务 (services/background_jobs.py)
- [x] API路由 (api/conversation.py)
- [x] 所有端点测试通过

### Phase 2: 前端界面 ✅
- [x] 分区侧边栏 (PartitionSidebar.tsx)
- [x] 分支列表 (BranchList.tsx)
- [x] 消息列表 (MessageList.tsx)
- [x] 多模态输入 (ChatInput.tsx)
- [x] ResponseBlock渲染 (ResponseBlockRenderer.tsx)
- [x] WebSocket流式接收
- [x] 构建验证通过

### Phase 3: 联调 ✅
- [x] 端到端测试通过
- [x] 设计文档更新
