# 对话系统重构：Vercel AI SDK + LangGraph

> 状态: 设计中 | 日期: 2026-07-06
> 目标: 用成熟轮子替换自研的流式管理 + Agent 编排，消除持续出现的 loading/分支/SSE bug

---

## 一、现状与问题

### 前端现状 (自研 Zutand + 手动 SSE)

```
useChatStream.ts (280 行)
  ├─ readSSEStream() — 手动 ReadableStream 逐行解析 SSE
  ├─ dispatchEvent() — 17 种事件类型 switch-case
  │   ├─ _handleToken() — 追加文本到 streaming message
  │   ├─ _handleToolCalls() — 工具调用状态管理
  │   ├─ _handleDone() — 完成收尾、清理 streamingId
  │   ├─ _handleError() — 错误消息替换
  │   └─ ... 13 种其他事件
  ├─ send() — generation 追踪 + stop 标志位
  └─ replay() — 页面刷新重连流

message-store.ts (800+ 行)
  ├─ nodeMap / currentPath / pathPosMap — 树结构
  ├─ load_state 状态机 (placeholder/loading/loaded/broken/streaming)
  ├─ loadingInFlight / loadingPromises / loadAttempted — 并发控制
  ├─ calcPath / fillAncestorPath / switchBranch — 路径算法
  └─ loadFullContent / loadMessages — 懒加载

send-message.ts (200+ 行)
  ├─ 乐观写入 + parent_id 推导
  ├─ sending 锁 + pathReady 守卫
  ├─ stop 超时 5000ms
  └─ 错误回滚

MessageList.tsx
  ├─ versionGroups 分组 (parent_id::role)
  ├─ itemContent 触发懒加载
  └─ 版本导航 (上一版本/下一版本)
```

**根因**: 所有状态管理、流处理、并发控制都是手写的，缺少统一的框架约束。

### 后端现状 (自研 Pipeline)

```
ReplyPipeline: 6 阶段顺序执行
  Stage 0: SaveMessageStage — 存用户消息
  Stage 1: InitStage — 创建 shell (占位 assistant)
  Stage 2: ClassifyStage — 分类器
  Stage 3: ToolLoopStage — LLM 调用 + 工具循环 + 挂起/恢复
  Stage 4: PostProcessStage — 后处理器链
  Stage 5: DoneStage — 完成

StreamBuffer: 内存事件缓冲
conversation_processor: 后台 pipeline 启动 + 事件发布
```

**根因**: 自研的状态管理 (挂起/恢复、错误传播) 靠手动 break/continue 和模块级字典，容易遗漏边界情况。

---

## 二、目标架构

```
┌─────────────────────────────────────────────────────────┐
│                    Vercel AI SDK                        │
│  useChat({ transport })                                  │
│  ├─ 流式文本渲染 (自动)                                  │
│  ├─ loading / error / streaming 状态 (自动)             │
│  ├─ stop / reload / append (自动)                        │
│  ├─ 消息去重 + 竞态处理 (自动)                           │
│  └─ 自定义 transport: 适配后端 SSE 协议                  │
│                                                          │
│  Zustand (仅保留树模型)                                  │
│  ├─ nodeMap — 消息索引 (O(1) 查询)                       │
│  ├─ currentPath — 当前活跃路径                           │
│  ├─ pathPosMap — 路径位置索引                            │
│  └─ 分支导航 + 版本切换                                  │
└─────────────────────────────────────────────────────────┘
                           │
                           │ HTTP POST (SSE)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    LangGraph                             │
│  StateGraph(ReplyState)                                  │
│  ├─ save_message — 存用户消息                            │
│  ├─ init_shell — 创建 assistant 占位                     │
│  ├─ classify — 分类器                                    │
│  ├─ tool_loop — LLM 调用 + 工具循环                      │
│  ├─ post_process — 后处理                                │
│  └─ done — 完成                                          │
│                                                          │
│  checkpointer: MemorySaver / SqliteSaver                 │
│  ├─ 工具挂起/恢复 → 自动 checkpoint                      │
│  └─ 中断恢复 → 原生支持                                  │
│                                                          │
│  事件桥接: LangGraph events → StreamBuffer               │
└─────────────────────────────────────────────────────────┘
```

---

## 三、Vercel AI SDK 集成设计

### 3.1 自定义 Transport

Vercel AI SDK v4 的 `useChat` 通过 `transport` 参数自定义后端协议：

```typescript
// frontend/src/lib/ai-sdk-transport.ts
import { DefaultChatTransport } from "ai";

function createEduCompanionTransport(convId: string, dirId: string) {
  return new DefaultChatTransport({
    // API 端点
    api: `/api/conversations/tree/conversation/${convId}/message`,

    // 自定义请求体
    prepareRequest({ messages }) {
      const lastMessage = messages[messages.length - 1];
      return {
        action: "send",
        text: typeof lastMessage.content === "string" ? lastMessage.content : "",
        dir_id: dirId,
        parent_id: getParentIdFromStore(), // 从 Zustand 取
      };
    },

    // 自定义 SSE 事件解析
    processData({ data }) {
      // 我们的 SSE 格式: data: {"type":"token","content":"xxx"}
      const event = JSON.parse(data);
      switch (event.type) {
        case "token":
          return { type: "text-delta", textDelta: event.content };
        case "tool_calls":
          return { type: "tool-call", toolCallId: event.id, toolName: event.name, args: event.args };
        case "tool_call_update":
          return { type: "tool-call-delta", toolCallId: event.id, ... };
        case "done":
          return { type: "finish", finishReason: "stop" };
        case "error":
          return { type: "error", error: new Error(event.data?.error || event.message) };
        // 其他事件：忽略或分流到 Zustand
        default:
          return { type: "other", event };
      }
    },
  });
}
```

### 3.2 替换清单

| 被替换的代码 | 替换为 | 理由 |
|---|---|---|
| `readSSEStream()` (70 行) | AI SDK 内置 | 不再手动解析 SSE |
| `dispatchEvent()` switch-case (100 行) | transport.processData | 事件映射而非手动分发 |
| `_handleToken()` (30 行) | AI SDK 自动累积 | 流式文本天然支持 |
| `_handleError()` (30 行) | AI SDK error 状态 | 自动错误状态 |
| `_handleDone()` (50 行) | AI SDK finish 状态 | 自动清理 |
| `generationRef` / `stoppedRef` | AI SDK 内部 | 自动竞态保护 |
| `sendPromiseRef` / `replayPromiseRef` | AI SDK 内置 | 自动并发控制 |
| `sending` 锁 + `pathReady` 守卫 | AI SDK 内置 | 自动发送锁 |
| `streamingId` 管理 | AI SDK `status` | 自动状态推导 |
| `load_state` 状态机 | AI SDK 消息状态 | 自动 loading/loaded/error |
| `_loadingInFlight` / `_loadingPromises` | AI SDK 内置 | 自动去重 |

**总计删除约 400+ 行手写状态管理代码**，替换为约 80 行 transport 适配。

### 3.3 保留的 Zustand Store

```typescript
// 精简后的 message-store.ts（约 200 行）
interface MessageStore {
  // 树模型（保留）
  nodeMap: Record<string, MessageNode>;
  currentPath: string[];
  pathPosMap: Map<string, number>;

  // 分支导航（保留）
  calcPath(targetId: string): Promise<void>;
  switchBranch(fromId: string, toId: string): void;
  handleDelete(nodeId: string): void;

  // 懒加载（保留，但简化）
  loadFullContent(msgId: string): Promise<void>;
  loadMessages(convId: string): Promise<void>;

  // URL 同步（保留）
  syncUrl(msgId: string): void;
}
```

### 3.4 版本分组 (保留)

```
MessageList.tsx 中的 versionGroups 逻辑不变。
它基于 nodeMap (Zustand) 做 parent_id::role 前缀分组，
与 useChat 的消息列表正交。
```

---

## 四、LangGraph 集成设计

### 4.1 StateGraph 定义

```python
# backend/app/domain/conversation/langgraph_pipeline.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated
import operator

class ReplyState(TypedDict):
    user_id: str
    dir_id: str
    conv_id: str
    user_text: str
    parent_id: str
    pending_quote: dict | None
    knowledge_node_id: str | None

    # 阶段产出
    user_msg_id: str
    msg_id: str          # assistant shell id
    assistant_node: dict | None
    response_blocks: Annotated[list, operator.add]
    full_reply: str
    content_blocks: list

    # 工具循环
    llm_messages: list
    tools: list
    tool_round: int
    tool_result: dict | None

    # 控制
    error: str | None
    suspended: bool

def build_reply_graph() -> StateGraph:
    graph = StateGraph(ReplyState)

    graph.add_node("save_message", save_message_node)
    graph.add_node("init_shell", init_shell_node)
    graph.add_node("classify", classify_node)
    graph.add_node("tool_loop", tool_loop_node)
    graph.add_node("post_process", post_process_node)
    graph.add_node("done", done_node)

    graph.set_entry_point("save_message")
    graph.add_edge("save_message", "init_shell")
    graph.add_edge("init_shell", "classify")
    graph.add_edge("classify", "tool_loop")

    # tool_loop 的两个出口:
    #   - 正常完成 → post_process
    #   - 挂起等待 → END (通过 interrupt)
    graph.add_conditional_edges("tool_loop", after_tool_loop, {
        "continue": "post_process",
        "suspend": END,
    })

    graph.add_edge("post_process", "done")
    graph.add_edge("done", END)

    return graph.compile(checkpointer=MemorySaver())
```

### 4.2 挂起/恢复 — 原生中断

LangGraph 的 `interrupt()` 机制原生支持挂起：

```python
# tool_loop_node 内部
async def tool_loop_node(state: ReplyState) -> dict:
    while state["tool_round"] < MAX_ROUNDS:
        # ... LLM 调用 ...
        if tool_name == "ask_question":
            # LangGraph 原生中断：保存当前状态并返回
            from langgraph.types import interrupt
            interrupt({
                "type": "suspended",
                "tool_call_id": tool_call.id,
                "question": tool_call.args["question"],
            })
            # 恢复时从这行继续执行
            # state["tool_result"] 已由 resume 调用注入
        # ...
    return {"full_reply": full_reply}
```

恢复：
```python
# 注入 tool_result 后，从同一 checkpoint 继续
async for event in graph.astream_events(
    Command(resume=tool_result),
    config={"configurable": {"thread_id": conv_id}},
):
    yield map_langgraph_event(event)
```

### 4.3 事件桥接

LangGraph 的 `astream_events` 产出标准事件，映射到我们的 `ReplyEvent`：

```python
async def map_langgraph_event(event: dict) -> ReplyEvent:
    t = event["event"]
    name = event["name"]
    data = event["data"]

    if t == "on_chat_model_stream":
        return ReplyEvent(type="token", content=data["chunk"].content)
    elif t == "on_tool_start":
        return ReplyEvent(type="tool_calls", data={...})
    elif t == "on_tool_end":
        return ReplyEvent(type="tool_call_update", data={...})
    elif t == "on_custom_event" and name == "pending_msg":
        return ReplyEvent(type="pending_msg", data=data)
    elif t == "on_custom_event" and name == "error":
        return ReplyEvent(type="error", data=data)
    # ...
```

### 4.4 替换清单

| 被替换 | 替换为 | 理由 |
|---|---|---|
| `ReplyPipeline` (编排器, 100 行) | `StateGraph` | 原生状态管理 |
| `PipelineCtx` (可变上下文) | `ReplyState` (TypedDict) | 类型安全 |
| `_suspend_loop` / `_pop_suspended` (模块级字典) | `checkpointer` | 原生持久化 |
| `ToolLoopStage` while 循环 (200 行) | `tool_loop_node` + `interrupt` | 原生中断 |
| 阶段间 try/except + break | 条件边 + `error` 字段 | 声明式错误处理 |
| `asyncio.CancelledError` 优雅关闭 | LangGraph 内置 | 标准取消 |

**总计删除约 400 行自研 pipeline 编排代码**，替换为约 150 行 graph 定义 + 事件桥接。

---

## 五、迁移步骤

### Phase 1: 后端 LangGraph (不改前端)

1. 安装 `langgraph` + `langchain-core`
2. 实现 `langgraph_pipeline.py` (StateGraph + 事件桥接)
3. 修改 `conversation_processor.py`：新 `_run_pipeline_task` 调 `graph.astream_events`
4. 保持 `StreamBuffer` + `SSE generator` 不变
5. **验证**: 发消息→正常回复→工具调用→挂起恢复→错误处理

### Phase 2: 前端 Vercel AI SDK (后端已稳定)

1. 安装 `ai` + `@ai-sdk/openai` (或只用 `ai` 的 transport)
2. 实现 `ai-sdk-transport.ts` (自定义 transport)
3. 重构 `useChatStream.ts` → `useChat({ transport })`
4. 精简 `message-store.ts` (删除 load_state 状态机、并发控制)
5. 简化 `send-message.ts` (删除乐观写入、锁、守卫)
6. **验证**: 发消息→流式显示→停止→分支切换→刷新恢复→URL 同步

### Phase 3: 清理

1. 删除 `useChatStream.ts`、`readSSEStream`、`dispatchEvent` 等
2. 删除 `message-store.ts` 中的 load_state 相关代码
3. 删除 `send-message.ts` 中的锁/守卫/乐观写入
4. 更新文档 `frontend-design.md`、`backend-api.md`

---

## 六、风险与决策

| 风险 | 缓解 |
|---|---|
| Vercel AI SDK 版本迭代快 | 锁定主版本，我们的 transport 很薄（80 行），升级成本低 |
| LangGraph 学习曲线 | 我们的 pipeline 本身就是图结构，1:1 映射，学习成本可控 |
| 自定义 transport 不支持所有事件 | 只映射核心事件（token/tool/done/error），其他事件走 `onOther` 分流到 Zustand |
| 分支导航与 useChat 消息列表不一致 | 分支切换时调 `useChat.setMessages()` 重新设置消息列表 |
| 懒加载与 useChat 集成 | 懒加载走 Zustand 单独管理，useChat 只管理当前路径的活跃消息 |