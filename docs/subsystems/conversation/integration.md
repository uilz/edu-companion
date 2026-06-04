# 对话系统前后端对接文档

> Frontend ↔ Backend API Contract for the Conversation System
> 基于 `backend-api.md` 和 `frontend-design.md`

---

## 目录

- [1. 数据模型](#1-数据模型)
- [2. 前端 → 后端 API 映射](#2-前端--后端-api-映射)
- [3. WebSocket 协议](#3-websocket-协议)
- [4. 错误处理契约](#4-错误处理契约)
- [5. 状态同步时序](#5-状态同步时序)

---

## 1. 数据模型

### 1.1 侧栏树结构

```
后端存储 (PgStorageEngine)                前端渲染 (PartitionSidebar)
─────────────────────────                ──────────────────────────
Partition (分区)                          PartitionItem
  ├── name, emoji, subject                 ├── name, emoji
  ├── children[]: Domain                   ├── children[]: TreeItem
  │     ├── name, emoji                    │     ├── name, emoji
  │     ├── children[]: Topic              │     ├── children[]: TreeItem
  │     │     ├── name, emoji              │     │     ├── name, emoji
  │     │     ├── children[]: Conversation │     │     ├── children[]: TreeItem
  │     │     │     ├── name               │     │     │     ├── name
  │     │     │     └── path: Node[]       │     │     │     └── (no path in tree)
  │     │     └── ...                      │     │     └── ...
  │     └── ...                            │     └── ...
  └── ...                                  └── ...
```

### 1.2 关键字段契约

| 字段 | 后端类型 | 前端类型 | 说明 |
|------|----------|----------|------|
| `id` | `str` (UUID) | `string` | 全局唯一 |
| `partition_id` | `str` | `string` | 所有子节点必须携带 |
| `path` | `List[TreeNode]` | `TreeNode[]` | 对话的消息路径 |
| `children` | 不存在 | `TreeItem[]` | 前端树结构专属 |
| `expanded` | 不存在 | `boolean` | 前端展开状态专属 |
| `level` | 不存在 | `"partition"\|"domain"\|"topic"\|"conversation"` | 前端标记层级 |

---

## 2. 前端 → 后端 API 映射

### 2.1 侧栏：树结构加载

```
前端操作          API 请求                        后端处理
────────────────────────────────────────────────────────────
页面加载/刷新     GET  /partitions                 加载所有分区
展开分区          GET  /partitions/{id}/domains     加载领域列表
展开领域          GET  /domains/{id}/topics         加载专题列表
展开专题          GET  /topics/{id}/conversations   加载对话列表
```

**契约：** 前端**懒加载**——只有用户展开节点时才触发 API，不预加载子节点。但自动展开路径（如 URL 恢复）会逐层触发。

### 2.2 侧栏：CRUD 操作

| 前端操作 | HTTP | API 路径 | 后端方法 |
|----------|------|----------|----------|
| 点击「➕新建分区」 | POST | `/partitions` | `tree_ops.create_partition` |
| 点击分区旁的「💬」 | POST | `/domains` | `tree_ops.create_domain` |
| 领域旁的「💬」 | POST | `/topics` | `tree_ops.create_topic` |
| 专题旁的「💬」 | POST | `/conversations` | `tree_ops.create_conversation` |
| 重命名(任何层级) | PATCH | `/{type}/{id}` | `tree_ops.{rename_xxx}` |
| 删除(任何层级) | DELETE | `/{type}/{id}` | `tree_ops.{delete_xxx}` |

**契约：** 所有 CRUD 返回 `{"ok": true}`（成功）或 `{"detail": "..."}`（失败，HTTP 4xx/5xx）。

### 2.3 对话：消息发送与加载

```
前端操作          API 请求                        后端处理
────────────────────────────────────────────────────────────
点击对话          GET  /conversations/{id}/messages   加载消息列表
                 (limit=50, offset=0)
发送消息          POST /message                      分类器路由 → AI 推理
                 (REST 模式, 非流式)
发送消息          WebSocket /ws                      分类器路由 → AI 推理
                 (流式模式, token 逐字返回)
编辑消息          PUT  /messages/{id}                 创建新版本节点
删除消息          DELETE /messages/{id}               软删除(标记 is_hidden)
切换消息版本      GET  /messages/{id}/versions        列出历史版本
```

### 2.4 消息 POST /message (REST 非流式)

**请求:**
```json
{
  "text": "什么是导数？",
  "partition_id": "p_id",
  "domain_id": "d_id",
  "topic_id": "t_id",
  "conversation_id": "c_id"
}
```

**响应:**
```json
{
  "user_message": TreeNode,        // 用户消息节点
  "assistant_message": TreeNode,   // AI 回复节点
  "conversation_id": "c_id",
  "partition_id": "p_id",
  "unread": 0
}
```

### 2.5 WebSocket /ws (流式)

**建立连接：** 前端的 `/learn` 页面挂载时打开 `ws://host/api/conversations/ws`

**客户端 → 服务端（3 种消息类型）：**

```json
// 发送消息
{"type": "message", "text": "什么是导数？", "conversation_id": "c_id", "partition_id": "p_id"}

// 创建新对话 (切换到新话题时由分类器自动触发)
{"type": "create_conversation", "topic_id": "t_id", "partition_id": "p_id"}

// 切换上下文 (用户侧栏切换到不同对话)
{"type": "context_switch", "conversation_id": "c_id", "partition_id": "p_id"}
```

**服务端 → 客户端（6 种消息类型）：**

```json
// 流式 Token
{"type": "token", "content": "微分", "stage": "thinking|answering|reasoning"}
// 流式结束
{"type": "done", "conversation_id": "c_id", "assistant_message": TreeNode}
// 响应块 (富文本内容)
{"type": "response_block", "block": {...}}
// 错误
{"type": "error", "text": "..."}
// 上下文切换确认
{"type": "context_switched", "conversation_id": "c_id", "partition_id": "p_id"}
// 心跳
{"type": "ping"}
```

---

## 3. WebSocket 协议

### 3.1 生命周期

```
页面加载 → 建立连接 → 身份验证(隐式) → 空闲(心跳)
                                              ↓
用户发送消息 → 服务端开始推理 → token流 → response_block → done
                                              ↓
用户切换对话 → context_switch → 服务端确认 → 新对话空闲
                                              ↓
页面关闭 → 连接断开
```

### 3.2 错误场景与重连

| 场景 | 行为 | 重试策略 |
|------|------|----------|
| WebSocket 连接失败 | 5s → 10s → 20s → 上限 30s 指数退避重连 | `onclose` 触发 |
| WebSocket 服务端断连 | 同连接失败 | 立即触发 `onclose` |
| 网络中断后恢复 | 自动重连，重连后发 `context_switch` 恢复状态 | 指数退避 |
| `{"type":"error"}` | 显示错误消息，不重连 | 用户手动重试 |
| HTTP 回退（WS 不可用） | 退化为 POST /message + 轮询 | 每次发送尝试 WS |

### 3.3 后端处理链

```
WebSocket 收到 message
  → classifier.auto_resolve(partition_id, text)  # 1. 意图分类
    → 创建/确认 domain + topic + conversation     # 2. 自动建链
      → conversation_llm.send_and_reply_stream()   # 3. AI 推理
        → _build_context_messages()                # 4. 构建 9 层上下文
          → llm_service.chat(stream=True)          # 5. LLM 流式调用
            → token → response_blocks → done       # 6. 逐字返回
              → _parse_follow_up_questions()       # 7. 追问问题解析（v0.9.11）
              → _analyze_evidence()                # 8. 异步: 知识证据分析
              → _trigger_cognitive_node_update()   # 9. 异步: CognitiveNode 更新
```

### 3.4 追问问题协议（v0.9.11）

LLM 回复末尾按约定输出 3 个追问问题，后端解析后从显示文本中摘除。

**LLM 输出格式：**
```
...
（回复正文）

<!--FOLLOW_UP-->
追问问题 1？
追问问题 2？
追问问题 3？
<!--/FOLLOW_UP-->
```

**存储：** 追问问题存入 `TreeNode.metadata.follow_up_questions`

**前端消费：**
- `assistant_message.metadata.follow_up_questions` → 提取为 `follow_up_questions` 顶层字段
- `FollowUpChips` 组件渲染 3 个编号按钮
- 点击 → `store.sendMessage(question)` 发送

**跳过规则：** 告别场景、情绪低落、纯隐私交流 — LLM 不输出标记块即可。

---

## 4. 错误处理契约

### 4.1 HTTP 错误码

| HTTP | 含义 | 前端处理 |
|------|------|----------|
| 200 | 成功 | 正常处理 |
| 304 | 未修改(ETag) | 使用缓存 |
| 400 | 请求参数错误 | 显示 toast 提示 |
| 404 | 资源不存在 | **侧栏**: 从树中移除该节点 (loadChildren 404 处理) |
|      |              | **消息**: 显示红色横幅"该对话已被删除"，不清除状态 |
| 409 | 冲突(重复创建) | 提示用户 |
| 500 | 服务端错误 | 显示"服务异常，请稍后重试" |

### 4.2 前端 404 处理策略

```typescript
// PartitionSidebar.tsx - 侧栏树加载
if (errMsg.includes("404")) {
  // 递归从树中移除该节点及其所有子节点
  // 用户下次展开父节点时自动获取最新列表
}

// learn/page.tsx - 消息加载
if (errMsg.includes("404")) {
  // setConvError("该对话已被删除") — 显示错误横幅
  // 不清除 activeConversationId
  // 不清除侧栏树状态
}
```

### 4.3 后端正则删除语义 (DELETE)

| 资源 | 实际行为 |
|------|----------|
| 分区 | 从 `data.partitions` 移除，save() 时从 DB 删除 + 级联删除子记录 |
| 领域 | 从分区 `domain_order` 移除，从 `data.domains` 移除 |
| 专题 | 从领域 `topic_order` 移除，从 `data.topics` 移除，归档子对话/消息 |
| 对话 | 从 `data.conversations` 移除，消息软删除 (`is_hidden=true`) |
| 消息 | 软删除 (`is_hidden=true`)，子树全部标记隐藏 |

---

## 5. 状态同步时序

### 5.1 页面加载

```
时间 →  前端                         后端
│        页加载
│        ├─ URL 解析: ?p=xxx&c=yyy
│        │  └─ setSelectedPartitionId, setActiveConversationId
│        ├─ 建立 WebSocket 连接       ──→  /ws 连接建立
│        ├─ loadPartitions()          ──→  GET  /partitions
│        │                            ←──  分区列表
│        │  └─ 自动展开路径(分区→领域→专题→对话)
│        │      ├─ loadChildren(分区)  ──→  GET  .../domains
│        │      │                      ←──  领域列表
│        │      ├─ loadChildren(领域)  ──→  GET  .../topics
│        │      │                      ←──  专题列表
│        │      └─ loadChildren(专题)  ──→  GET  .../conversations
│        │                             ←──  对话列表
│        ├─ 等待 urlInitialized && !isLoadingPartitions
│        ├─ loadMessages(c_id)         ──→  GET  .../messages
│        │                              ←──  消息列表
│        └─ 展示消息 + 侧栏展开状态    ←──  渲染完成
```

### 5.2 发送消息（流式）

```
时间 →  用户输入 → 发送按钮
│        前端                         后端
│        ├─ WS: {type:"message",...}  ──→  /ws
│        │                              ├─ classifier.auto_resolve()
│        │                              ├─ send_and_reply_stream()
│        │                              ├─ WS: {type:"token", content:"微分"}
│        │  ←── 追加流式文本            ├─ WS: {type:"token", content:"是"}
│        │  ←── 追加流式文本            ├─ ...
│        │                              ├─ WS: {type:"response_block", block:{...}}
│        │  ←── 渲染响应块              ├─ ...
│        │                              └─ WS: {type:"done", conversation_id:"...",
│        │  ←── 流式结束 + 完整节点            assistant_message: TreeNode}
│        ├─ loadPartitions()(300ms后)  ──→  刷新侧栏(新对话/新消息计数)
│        └─ 完成                         ←──  更新后的树
```

### 5.3 新建对话

```
时间 →  用户点击 💬 按钮
│        前端                         后端
│        ├─ handleNewConversation()
│        ├─ POST /domains              ──→  创建默认领域
│        │                              ←──  {id: "d_id"}
│        ├─ POST /topics               ──→  创建默认专题
│        │                              ←──  {id: "t_id"}
│        ├─ POST /conversations        ──→  创建空对话
│        │                              ←──  {conversation: {id: "c_id"}}
│        ├─ setActiveConversationId(id)
│        ├─ loadPartitions()(刷新侧栏)  ──→  获取最新树
│        └─ 进入新对话等待输入
```

---

## 附录：文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 后端 API 文档 | `docs/conversation-system/backend-api.md` | 35 个端点 + 18 个服务方法 |
| 前端设计文档 | `docs/conversation-system/frontend-design.md` | 组件树、状态管理、7 个事件流程 |
| **对接文档 (本文件)** | `docs/conversation-system/integration.md` | API 映射、WS 协议、错误契约、时序图 |
