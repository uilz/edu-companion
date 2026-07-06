# 对话系统

> 基于 DirectoryNode 树形目录 + SSE 流式协议 + Block Renderer 的统一对话架构。
> 源码: [frontend/src/store/conversation/](../../frontend/src/store/conversation/) | [backend/app/domain/conversation/](../../backend/app/domain/conversation/)

---

## 核心概念

```
根目录 → DirectoryNode (dir) → DirectoryNode (conv) → MessageNode
                                  ├─ 子支引用（QuoteBlock）
                                  └─ 子支会话 → 可递归
```

**DirectoryNode 取代了旧的分区(Partition)→领域(Domain)→专题(Topic)五级层级**，改为统一的树形节点结构，每个节点有 `node_type`（`dir` | `conv`）和 `kind`（`temp` | `general` | ...）。

---

## 数据流（发消息）

```
用户在 Conversation 页输入文本 → 点击发送
│
├─ Phase 1: ensureAndSelectConversation()
│   ├─ GET  /tree/directory               → 查临时目录
│   ├─ POST /tree/directory               → 创建临时目录（如不存在）
│   ├─ GET  /tree/directory?parent_id=pId → 查空会话
│   ├─ POST /tree/directory               → 创建会话（如无空会话）
│   ├─ 刷新侧边栏（loadRootNodes + loadChildren + loadDirList）
│   └─ 选中会话（selectedNode）
│
├─ Phase 2: 发送消息
│   ├─ beginStream(cId, pId, asstId)      → 建立 SSE 连接
│   ├─ 乐观写入（user 消息 + assistant 占位符）
│   └─ POST /tree/conversation/{cId}/message → 触发后端 pipeline
│       │
│       ▼
│   后端 ReplyPipeline（5 阶段）
│   ├─ Stage 1 (ClassifyStage): 分类器 → context_switch
│   ├─ Stage 2 (SaveMessageStage): 存用户消息 → user_message 事件
│   ├─ Stage 3 (ToolLoopStage): LLM tool loop → token/tool_calls/block_update
│   ├─ Stage 4 (PostProcessStage): blocking 后处理器 (Socratic/Source/Saver)
│   └─ Stage 5 (DoneStage): done 事件 → 发布 AssistantReplied 领域事件
│       │
│       ▼
│   SSE 事件流 → setup.ts(12 个 subscriber)
│   ├─ token         → 流式文本追加
│   ├─ tool_calls    → 插入 ToolBlock[](status:pending)
│   ├─ tool_call_update → ToolBlock status:pending→running
│   ├─ block_update  → ToolBlock status:running→done + result_content
│   ├─ reasoning     → 追加/创建 ReasoningBlock
│   ├─ done          → 替换消息 ID + 合并最终块
│   ├─ error         → 错误消息节点
│   ├─ context_switch / tree_recommendation → 通知
│   └─ phase_change  → isLoading / wsConnected
│
└─ MessageList 实时渲染
    └─ Block Renderer Registry 按 type 查表渲染
```

### 管线副作用（AssistantReplied 事件驱动）

回复管线的非阻塞副作用已从 PostProcessor 链中移除，改为通过事件总线订阅 `AssistantReplied` 事件：

```
ReplyPipeline done → AssistantReplied 事件发布
├─ ReplyHooks (reply_hooks.py)
│   ├─ CognitiveSync: SourceParser 缓存 → CognitiveNode 联动
│   ├─ KnowledgeEvidence: 对话知识证据分析
│   └─ MetaHistory: 分支重命名 / 图谱更新
├─ MultimediaService: 多媒体生成
├─ EventMemory: 事件记忆持久化
└─ SecretaryPolicyEngine: 秘书上下文更新
```

### 后端源文件

| 文件 | 职责 |
|------|------|
| `reply_pipeline.py` | 编排器：PostProcessor 接口 + 4 内置处理器 + 5 阶段调度 |
| `pipeline_stages.py` | 5 阶段实现：ClassifyStage / SaveMessageStage / ToolLoopStage / PostProcessStage / DoneStage |
| `reply_hooks.py` | AssistantReplied 事件订阅：3 个副作用 hook |
| `conversation_processor.py` | 编排层：管线启动 + StreamBuffer 发布 + AssistantReplied 事件发布 |
| `session_bridge.py` | SessionCompleted 事件 → 练习记忆写回对话 |
| `context_pipeline.py` | 上下文构建管线：6 个 ContextProvider |
| `tree_store.py` | 对话树 CQS 存储：TreeQuery / TreeMutate |

---

## 功能总览

| 功能 | 说明 | 状态 |
|------|------|------|
| DirectoryNode 树形目录 | 统一 dir/conv 两级树，按 kind 区分用途 | ✅ 已实现 |
| SSE 流式对话 | 事件流协议，Line-delimited JSON（非 WebSocket） | ✅ 已实现 |
| ToolBlock 执行展示 | pending→running→done 三态实时更新 | ✅ 已实现 |
| ReasoningBlock 推理展示 | LLM 思考过程可折叠展示 | ✅ 已实现 |
| Block Renderer Registry | type→组件查表渲染，新增类型只需注册 | ✅ 已实现 |
| 子支系统 v3.0 | 消息级引用+QuoteBlock+摘要写回 | ✅ 已实现 |
| 临时目录 | 48h 自动清理，不参与学习数据 | ✅ 已实现 |
| 临时会话 | 空状态自动创建，发消息时自动生成 | ✅ 已实现 |
| SSE 原生断线重连 | Last-Event-ID 自动恢复 | ✅ 已实现 |
| 分类器 | 自动分区/意图分类 | ✅ 已实现 |
| 消息持久化统一格式 | 后端存 `type:"tool"`，前端零转换 | ✅ 已实现 |

---

## 核心设计原则

### 1. SSE 是唯一写入口（流期间）

SSE 流期间，REST `loadMessages` 被锁定（不替换消息数组），只有 SSE done 事件能写入最终数据。避免双路径竞态。

### 2. 消息格式统一（零转换）

数据库 `content_blocks` 存储格式即前端消费格式：
```typescript
{ type: "text" | "tool" | "reasoning" | "image" | "file" | "quote", ... }
```
没有 `_response_block` 中转，无格式转换代码。

### 3. 发消息两阶段

创建会话（含侧边栏刷新 + 选中）和发送消息完全分离，用户先看到会话出现，再看到消息发出。

### 4. 断线重连用 SSE 原生

服务端每条事件带 `id:`（自增序号），浏览器 `EventSource` 断开后自动带 `Last-Event-ID` 重连，服务端从断点回放。

---

## 子支设计

子支是消息级别的分支，锚定在某条消息的指定文本上：

- 引用通过 `QuoteBlock` 内容块实现
- 子支摘要自动写回父消息 `metadata.sub_branch_summaries[]`
- 父会话 LLM 自动看到子支讨论结果

## 临时会话

临时会话用于"随便聊聊"场景：

- 目录名固定为 `💬 临时`，不可改名
- 不参与 CognitiveNode 更新、图谱生成、间隔重复
- 48h 无活动自动清理
- 发消息时自动在临时目录下创建（无 pId/cId 时）

## 实现文档

| 文档 | 说明 |
|------|------|
| [backend-api.md](backend-api.md) | REST + SSE 接口规范 |
| [frontend-design.md](frontend-design.md) | 前端组件架构、Zustand 状态管理 |
| [specs/02-conversation-messages.md](../../specs/02-conversation-messages.md) | 数据模型定义 |
| [tool-architecture.md](../../architecture/tool-architecture.md) | AI Tool 系统（LLM Function Calling 定义/注册/执行） |
| [architecture/message-tree.md](../../architecture/message-tree.md) | 消息树路径架构（分支/版本/加载/恢复） |
