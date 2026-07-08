# 数据规格：会话与消息

> 会话系统采用 **DirectoryNode 树形目录 → 消息** 两级结构（取代旧版五级 PDTC）。
> DirectoryNode 通过 `node_type` 区分目录（dir）和会话（conv），通过 `kind` 标记用途（temp/general/...）。
>
> 源码: [backend/app/schemas/conversation.py](../../backend/app/schemas/conversation.py) | [frontend/src/types/index.ts](../../frontend/src/types/index.ts)

---

## 层级结构

```
根目录 (root)
  └── DirectoryNode (node_type="dir")          ← 目录（如 "💬 临时"）
        └── DirectoryNode (node_type="conv")    ← 会话
              └── MessageNode (树形消息链)
                    ├── content_blocks[]        ← 内容块数组（文本/工具/推理/图片/文件/引用）
                    └── sub_branch_summaries    ← 子支摘要列表
```

**关键变化**：取消了 Partition/Domain/Topic 三层，改为通用的目录节点。前端侧边栏通过 `GET /tree/directory` 递归加载展示为树形菜单。

---

## DirectoryNode 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 全局唯一 ID |
| `node_type` | `"dir" \| "conv"` | dir=目录，conv=会话 |
| `kind` | str | `temp`(临时), `general`(通用), `learn`(学习), `knowledge_tree`(知识树) 等 |
| `name` | str | 显示名称 |
| `parent_id` | str\|null | 父节点 ID |
| `message_count` | int | 消息数（conv 类型时有效） |
| `created_at` | str | ISO 日期 |
| `metadata` | dict | 元数据 |

---

## MessageNode（消息节点）模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 全局唯一 ID |
| `directory_id` | str | 所属会话（conv）ID |
| `partition_id` | str | 所属目录（dir）ID |
| `conversation_id` | str | 所属会话 ID（冗余） |
| `parent_id` | str | 父消息 ID（树形） |
| `children_ids` | list[str] | 子消息 ID |
| `content_blocks` | list[ContentBlock] | 多模态内容块 |
| `text_summary` | str | 文本摘要 |
| `role` | `"user" \| "assistant" \| "system"` | 消息角色 |
| `version` | int | 版本号 |
| `timestamp` | float | 时间戳 |
| `token_count` | int | Token 数 |
| `is_deleted` | bool | 是否删除 |
| `is_archived` | bool | 是否归档 |
| `agent_label` | str\|null | 关联 Agent（tutor/coach/secretary） |
| `sub_branch_ids` | list[str] | 子支会话 ID 列表 |
| `sub_branch_summaries` | list[dict] | 子支摘要列表 |

---

## ContentBlock 类型

| type | 模型 | 关键字段 | 说明 |
|------|------|---------|------|
| `text` | TextBlock | `text: string` | 文本内容，assistant 消息中由 SSE token 事件增量追加 |
| `tool` | ToolBlock | `tool_call_id, name, status, args, result_content` | 工具调用（三态：pending→running→done） |
| `reasoning` | ReasoningBlock | `content?, signature?` | LLM 推理过程（可折叠展示） |
| `image` | ImageBlock | `file_id?, name?, material_id?` | 图片 |
| `file` | FileBlock | `name?, material_id?` | 文件附件 |
| `quote` | QuoteBlock | `quoted_text, source_message_id, source_conversation_id` | 引用（子支锚点） |

### ToolBlock（工具调用块）

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"tool"` | 块类型标记 |
| `tool_call_id` | str | LLM 工具调用 ID |
| `name` | str | 工具名称（如 `search_knowledge_tree`） |
| `status` | `"pending" \| "running" \| "done"` | 执行状态 |
| `args` | dict\|null | 调用参数 |
| `result_content` | dict\|null | 执行结果 |
| `result_block_type` | str\|null | 结果块类型 |

**状态变化时序**：

```
SSE tool_calls  → status: "pending"   ← LLM 宣告要调用工具
SSE tool_call_update → status: "running" ← 开始执行
SSE block_update → status: "done" + result_content ← 执行完成
```

### ReasoningBlock（推理过程块）

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"reasoning"` | 块类型标记 |
| `content` | str\|null | 推理文本（由 SSE reasoning 事件增量追加） |
| `signature` | str\|null | 推理签名 |

---

## 后端持久化格式

数据库 `content_blocks` 存储的格式与前端消费格式**完全一致**，无需转换：

```json
{
  "content_blocks": [
    {"type": "text", "text": "让我查一下"},
    {"type": "tool", "tool_call_id": "call_xxx", "name": "search_knowledge_tree",
     "status": "done", "args": {"query": "导数"}, "result_content": {"results": [...]}},
    {"type": "reasoning", "content": "用户想知道导数概念..."},
    {"type": "text", "text": "根据查询结果，导数是..."}
  ]
}
```

**无 `_response_block` 格式，无前端转换代码。** 旧格式数据读取时兼容但写入全为新格式。

---

## 子支系统

子支通过 `QuoteBlock` 实现消息级分支：

```
父会话消息 → QuoteBlock 标记引用文本 → 子支会话 (子 DirectoryNode)
                                        → 消息链 → 子支对话
                                        → 摘要写回父消息 sub_branch_summaries[]
                                        → 父会话 LLM 自动感知
```

**规则：**
- 子支引用通过 `QuoteBlock` 内容块实现（`source_message_id` + `quoted_text` + 偏移量）
- 子支摘要自动写回父消息 `sub_branch_summaries[]`
- 父会话 LLM 自动感知子支讨论结果
- 临时会话不支持创建子支
- 子支深度理论上不限制

---

## 数据流向

```
SSE 流期间（实时）:
  TokenBuffer → SSE EventSource → setup.ts subscriber → Zusstand store → UI 渲染
  格式: {type:"tool", ...} 直接消费

REST 加载历史（切换会话时）:
  GET /api/conversations/tree/conversation/{cid}/messages → loadMessages → store
  格式: 与 SSE 相同，零转换

SSE done 事件（最终持久化）:
  数据直接写入 store → 不回源 REST
  ← 之前修复: done 事件不带 REST 负载，避免丢工具块
```
