# 学习空间对话系统 — 重构方案

> 基于架构审查报告的 6 个候选，逐一深化设计。每个候选记录：接口形状、Provider/Adapter 清单、关键决策。

---

## #1 ContextPipeline — 上下文构建器深化 ✅

**文件**: `backend/app/services/conversation/context_builder.py` → 删除，替换为 Pipeline + 6 个 Provider

### 关键决策

| # | 问题 | 决策 |
|---|------|------|
| 1 | Provider 如何访问数据源 | **独立访问存储**。每个 Provider 直接调 `get_data_repo()` / `emotion_analyzer` / `cognitive_repo` 等，不通过 Pipeline 预加载 bag |
| 2 | Provider 注册方式 | **静态注册**。Pipeline 构造时传入 `list[ContextProvider]`，按序执行。顺序稳定，Provider 内部自行判断是否产出 |
| 3 | Provider 输出格式 | **`SystemChunk \| ContextPayload` 联合类型**。SystemChunk 纯文本，ContextPayload 带 key+data+render 结构化字段 |
| 4 | Provider 粒度 | **按数据域合并为 6 个** |
| 5 | 跨层引用 | **`previous_payloads` 通道**。ContextInput 携带前序 Provider 的结构化 payload，后续 Provider 可选引用 |

### 接口

```python
class ContextInput:
    user_id: str
    partition_id: str
    user_text: str
    conversation_id: str
    previous_payloads: dict[str, Any]   # key → data

class SystemChunk:
    text: str

class ContextPayload:
    key: str          # e.g. "emotion", "cognition", "activity"
    data: dict
    render: str       # LLM 可见的文本摘要

ContextOutput = SystemChunk | ContextPayload

class ContextProvider(Protocol):
    async def build(self, input: ContextInput) -> ContextOutput | None: ...

class ContextPipeline:
    def __init__(self, providers: list[ContextProvider]): ...
    async def assemble(self, input: ContextInput) -> list[dict[str, str]]:
        # 遍历 providers → 收集 outputs → 
        # render 合并为一个 system message → 
        # 追加历史消息 + 用户消息 → 返回 LLM messages
```

### 6 个 Provider

| # | Provider | 数据源 | 产出 | 语义 |
|---|----------|--------|------|------|
| 1 | `TutorPersona` | `SYSTEM_PROMPT` (静态) | `SystemChunk` | AI 人格 |
| 2 | `ConversationLocation` | `conversation.parent_chain` + `partition.context_summary` | `SystemChunk` + `ContextPayload(key="location")` | 对话层级位置 (PDTC/PDC/PC) |
| 3 | `LearnerEmotion` | `emotion_analyzer` (两个函数) | `SystemChunk` + `ContextPayload(key="emotion")` | 会话情绪 + 即时情绪策略 |
| 4 | `LearnerCognition` | `knowledge_query` + `cognitive_repo` + KG | `ContextPayload(key="cognition")` | 知识状态 + BKT 信念 + 认知画像 + 知识点掌握分布 |
| 5 | `LearningActivity` | `practice_integrator` + `practice_recall` + `context_trigger` | `SystemChunk` + `ContextPayload(key="activity")` | 练习上下文 + 选题建议 |
| 6 | `TutorCapability` | `TOOL_DEFINITIONS` + `material_search` + `list_banks` | `SystemChunk` + `ContextPayload(key="capability")` | 可用工具 + RAG + 题库 |

### 调用方适配

当前 `_build_context_messages` 有 5 个调用点 → 替换为 `pipeline.assemble(ContextInput(...))`。

---

## #2 ReplyPipeline — LLM Facade 合并 🔄

**文件**: `backend/app/domain/conversation/llm.py` + `backend/app/services/llm/llm_core.py` + `backend/app/services/llm/tool_dispatch.py` + `backend/app/services/knowledge/cognitive_sync.py` → 合并为 `ReplyPipeline`

### 关键决策

| # | 问题 | 决策 |
|---|------|------|
| 1 | 接口形状 | **`invoke() → AsyncGenerator[Event]`** 单一入口。非流式消费 `async for event in pipeline.invoke(): if type == "done": break` |

### 内部阶段

```
invoke(user_id, text, conversation_id)
  │
  ├─ Stage 1: classifier.auto_resolve → context_switch 事件
  ├─ Stage 2: tree_ops.add_message → user_message 事件
  ├─ Stage 3: predict_tools → 工具预执行 → tool_block 事件 + 注入上下文
  ├─ Stage 4: [无工具] LLM function-calling probe 流式探测
  ├─ Stage 5: ContextPipeline.assemble() → LLM 流式生成 → token 事件
  ├─ Stage 6: 追问解析 + 来源解析 + tree_ops.add_message(assistant)
  ├─ Stage 7: cognitive_sync (fire-and-forget) + knowledge_evidence (fire-and-forget)
  └─ done 事件 {assistant_message, response_blocks, follow_up_questions}
```

### TODO

- [ ] Stage 5 中 ContextPipeline 与 LLM 调用之间的接口
- [x] Stage 6 的后处理器 → **PostProcessor 适配器链**。每个步骤独立实现 PostProcessor 接口
- [x] PostProcessor 的 blocking vs fire-and-forget → **Pipeline 感知**。PostProcessor 有 `is_blocking: bool`，Pipeline 对 blocking 做 `await`，对非 blocking 做 `asyncio.create_task()`
- [x] cognitive_sync 归属 → **保留在 knowledge 模块**。ReplyPipeline 创建薄 PostProcessor 适配器 import 它，模块不搬家
- [ ] 非流式 vs 流式的差异处理（非流式需要 tools+LLM 二轮调用，流式用 pre-execute probe）
- [ ] 现有调用方适配：`conversation_ws.py` + `conversation_routes.py` HTTP 降级 + `ConversationServiceImpl`

---

## #3 多 Agent 体系 + Orchestrator 🔄

**新建文件**: `backend/app/domain/agents/` (orchestrator, tutor, coach, secretary)  
**重构文件**: `backend/app/api/conversation/conversation_ws.py`, `classifier.py`, `backend/app/api/system/secretary.py`  
**前端**: `ConversationMessageArea`, `MessageList`, `agent-store.ts`, `AgentFloat.tsx`

### Agent 矩阵（4 个，全在对话流中可见）

| Agent | agent_label | 代表色 | 典型职责 | 可用工具 | 在流中出声 |
|-------|------------|--------|---------|---------|:---:|
| **Orchestrator** | `orchestrator` | 紫色 | 意图分析、Agent 调度、切换解释 | 路由决策工具 | 条件性（多 Agent 协作时） |
| **Tutor** | `tutor` | 蓝色 | 讲解、答疑、出题、搜视频、导图 | generate_practice, search_media, generate_mindmap, generate_document, generate_image | 是 |
| **Coach** | `coach` | 绿色 | 学习计划、进度追踪、习惯养成 | 计划查看/调整、习惯追踪、目标管理 | 是 |
| **Secretary** | `secretary` | 橙色 | 学情分析、提案生成、复习提醒 | 诊断分析、提案生成、薄弱点查询 | 是（提案卡片 + 流中总结） |

### Orchestrator 行为（模式 C）

```
单 Agent 场景（大多数情况）:
  用户 → Orchestrator 静默路由 → Tutor 直接回复 → 前端仅显示 Tutor 标签

多 Agent 协作场景:
  用户 → Orchestrator 出声解释 → Agent1 → Agent2 按序回复
  "这需要教学和规划两方。Tutor 讲课程差异，Coach 给学习路径。"
```

### 关键决策

- [x] 消息带 `agent_label` → 前端 MessageList 渲染不同头像/颜色
- [x] Orchestrator 条件出声：单 Agent 静默，多 Agent 先解释
- [x] Secretary 对话中可见 + SecretaryInlineBanner 提案卡片 + AgentFloat 侧边面板（三种形态共享同一后端）
- [x] 工具全开放，Agent 不限制（共享 ToolRepository 实例，Agent 内部自行决定是否调用）

- [x] Orchestrator 永远是调度中转型。Agent 间互调用发出 `agent_delegate` 事件 → Orchestrator 接收 → 生成转述 → 调用目标 Agent。Agent 不直接调 Agent
- [x] Agent 间相互调用 → AgentAdapter 持有 `AgentRegistry`，可引用所有 Agent。通过 `agent_delegate` 事件委托

### 对齐决策（2026-06-11）

| # | 问题 | 决策 |
|---|------|------|
| 1 | 意图分析 | **双轨**：强规则 + LLM fallback。规则足够强大，存疑时调 LLM。短消息（≤3字）沿用上一轮 Agent |
| 2 | agent_delegate 深度 | **无限制**，不设深度上限 |
| 3 | Context 组装 | Orchestrator **统一组装** context，切换 Agent 时经中转**刷新 context**（前序 Agent 输出可注入给下个 Agent） |
| 4 | 工具权限 | **全开放**，所有 Agent 共享 ToolRepository，不做按 Agent 过滤 |
| 5 | 多 Agent 消息结构 | **独立消息节点**，按 `conversation.path` 链顺序排列，前端逐个渲染，通过 `agent_label` 区分头像 |

### AgentAdapter 接口

```python
class AgentAdapter(Protocol):
    agent_label: str           # "orchestrator" | "tutor" | "coach" | "secretary"
    tools: ToolRegistry        # Agent 自己的工具集
    agents: AgentRegistry      # 可调用的所有 Agent（相互调用用）

    async def reply_stream(
        self, 
        user_id: str,
        user_text: str,
        context: ReplyContext,       # ContextPipeline 已组装的上下文
        conversation_id: str,
    ) -> AsyncGenerator[AgentEvent, None]:
```

`AgentEvent` 类型：
- `token` — 流式文本
- `tool_block` — 工具执行结果块（前端渲染卡片）
- `agent_delegate` — 委托给其他 Agent（`{target, instruction, resume_after}`）
- `agent_message` — Orchestrator 的转述文本（不带工具）
- `done` — Agent 完成
- `error` — Agent 失败

### Orchestrator 流程

```
用户消息
  │
  ▼
Orchestrator.reply_stream()
  ├─ 1. 意图分析（LLM: 该消息涉及哪些 Agent）
  ├─ 2. 决定 routing_plan: [{agent_label, instruction}]
  │
  ├─ 单 Agent → 静默，直接 delegate → 目标 Agent.reply_stream()
  │                                    → 合并事件流 → 前端只有目标 Agent 的 token
  │
  └─ 多 Agent → 出声解释 "这需要 X 和 Y 两方..."
              → 逐个 delegate:
                Agent1.reply_stream() → done
                Agent2.reply_stream() → done
              → Orchestrator done
```

### Agent 间互调 (agent_delegate)

```
Tutor 流中:
  token("链式法则是微积分中...")
  agent_delegate(target="coach", instruction="学生学导数，建议规划5道极限题", resume_after=false)
  
  → Orchestrator 收到 agent_delegate
    → 出声: "好的，Tutor 建议让 Coach 帮你规划练习..."
    → 启动 Coach.reply_stream()
    → Coach 回复完成 → Orchestrator done
```

### 完整对话流示例（用户问含学情 + 教学需求）

```
User: "最近导数学得怎么样？感觉不太扎实，能不能讲讲链式法则"

→ Orchestrator 路由: [secretary, tutor]
→ Orchestrator 出声: "让我先看看你的学习数据，再让 Tutor 针对性讲解。"

→ Secretary 流:
    token(agent_label="secretary", "根据最近3次练习，导数掌握度62%，\n链式法则准确率55%...")

→ Tutor 流:
    token(agent_label="tutor", "看到了，链式法则是你的薄弱项。\n先从基本概念来...")

conversation.path:
  [user_msg, orchestrator_msg, secretary_msg, tutor_msg]

---

### Agent 动态互调机制 — `tool_delegate`

Agent 间互调通过**共享工具 `tool_delegate`** 实现，不依赖 Agent 间的直接代码调用。

#### 7.1 数据结构

**ToolRepository 注册 `tool_delegate`**（共享工具，所有 Agent 可用）：

```python
TOOLS = [
    {
        "name": "tool_delegate",
        "description": "将当前对话委托给另一个 AI 助手。当需要其他助手的专长时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": ["tutor", "coach", "secretary"],
                    "description": "目标助手：tutor=教学助手, coach=学习教练, secretary=学习秘书",
                },
                "instruction": {
                    "type": "string",
                    "description": "给目标助手的完整指令，说明用户需求、当前进展、需要做什么",
                },
            },
            "required": ["target", "instruction"],
        },
    },
]
```

**`tool_delegate` 不返回 `AgentDelegateBlock` 新模型**，直接复用现有 `ResponseBlock`：

```python
# ResponseBlock 已支持任意 type + content dict
ResponseBlock(type="agent_delegate", content={
    "target": "tutor",
    "instruction": "用户想学导数，薄弱点在链式法则，请从基本概念讲起",
    "source_agent": "secretary",
})
```

无需新增模型，只需在 `_TOOL_TO_BLOCK_TYPE` 加入映射：

```python
_TOOL_TO_BLOCK_TYPE = {
    ...
    "tool_delegate": "agent_delegate",  # 新增
}
```

#### 7.2 流式数据全景

以下是 `tool_delegate` 从 LLM 输出到前端的**完整数据流**，每一层展示序列化前后的数据形态。

| 层 | 事件类型 | 数据结构 | 说明 |
|---|---------|---------|------|
| **LLM 输出** | `tool_calls` | `[{name: "tool_delegate", arguments: {target, instruction}}]` | LLM 决定委托 |
| **ReplyPipeline** | `ReplyEvent(type="tool_block")` | `{type: "agent_delegate", content: {target, instruction, source_agent}}` | 工具执行结果 |
| **AgentAdapter** | `AgentEvent(type="tool_block")` | 同上 block dict | 透传 |
| **Engine/WS** | `EngineEvent(type="tool_block")` | WS JSON: `{type: "tool_block", agent_label: "secretary", block: {...}}` | 透传到前端 |
| **Orchestrator** | 拦截 → 产出声 | `EngineEvent(type="agent_message")` | "让教学助手来讲解" |
| **Orchestrator** | 启动目标 Agent | 重新调 `target.reply_stream(instruction)` | 传入 `instruction` 作为新 user_text |
| **目标 Agent** | `EngineEvent(type="token")` | WS JSON: `{type: "token", agent_label: "tutor", content: "..."}` | 正常流式回复 |

#### 7.3 逐层数据示例

##### Step 1: LLM 原始输出（Agent A 的 Pipeline Stage 4）

LLM 的 `generate_stream` 返回 function-calling 格式：

```json
// LLM 流式探测返回
{
  "__tool_calls__": [
    {
      "id": "call_abc123",
      "function": {
        "name": "tool_delegate",
        "arguments": "{\"target\": \"tutor\", \"instruction\": \"用户想学习导数的链式法则。我已诊断：其链式法则正确率仅55%，薄弱点集中在复合函数分解。请针对性讲解链式法则的分解步骤，多用例题。\"}"
      }
    }
  ]
}
```

##### Step 2: Pipeline 执行工具 → `ResponseBlock`

`_parse_tool_calls_response` 解析 → `tool_executor.execute("tool_delegate", args)` 执行：

```python
# tool_executor 中
TOOL_HANDLERS = {
    ...
    "tool_delegate": _handle_tool_delegate,
}

async def _handle_tool_delegate(params: dict) -> ResponseBlock:
    """tool_delegate 处理器 — 只是包装参数为 ResponseBlock，不做任何实际工作"""
    return ResponseBlock(
        type="agent_delegate",
        content={
            "target": params["target"],
            "instruction": params["instruction"],
        },
    )
```

产出 `ResponseBlock`，序列化后：

```json
{
  "id": "block_xxx",
  "type": "agent_delegate",
  "content": {
    "target": "tutor",
    "instruction": "用户想学习导数的链式法则。我已诊断：其链式法则正确率仅55%..."
  },
  "status": "ready",
  "order": 0
}
```

##### Step 3: Pipeline 跳过 LLM 文本生成

```python
# Pipeline Stage 4 — 检测到 tool_delegate
if tool_name == "tool_delegate":
    # 跳过 Stage 5 LLM 流式生成
    extra_tool_context = ""    # 不注入上下文
    llm_probe_reply = ""       # 不产 LLM 文本
    # assistant_node 仍然创建（内容为空），用于对话连续性
    # 后续走到 Stage 7 done
```

##### Step 4: Pipeline → AgentAdapter → EngineEvent

```
ReplyEvent(type="tool_block", block=ResponseBlock) 
  → AgentEvent(type="tool_block", agent_label="secretary", block=ResponseBlock.model_dump())
    → EngineEvent(type="tool_block", agent_label="secretary", block=dict)
      → WS JSON:
        {
          "type": "tool_block",
          "agent_label": "secretary",
          "block": {
            "id": "block_xxx",
            "type": "agent_delegate",
            "content": {"target": "tutor", "instruction": "..."},
            "status": "ready"
          },
          "request_id": "req_001"
        }
```

##### Step 5: Orchestrator（在 Engine 层）拦截

```python
# conversation_engine.py process() 内部
async for event in orchestrator_events:
    # 拦截 agent_delegate block
    if (event.type == "tool_block" and event.block
            and event.block.get("type") == "agent_delegate"):

        target = event.block["content"]["target"]
        instruction = event.block["content"]["instruction"]

        # 5a. 产出一条 agent_message（Orchestrator 转述气泡）
        yield EngineEvent(
            type="agent_message",
            agent_label="orchestrator",
            message=f"好的，让{'教学助手' if target=='tutor' else '学习教练' if target=='coach' else '学习秘书'}来帮你。",
        )

        # 5b. 启动目标 Agent，传入 instruction 作为新 user_text
        #     以 save_user_msg=False 跳过保存合成用户消息
        target_agent = registry.get(target)
        async for next_event in target_agent.reply_stream(
            user_id=user_id,
            user_text=instruction,
            partition_id=partition_id,
            conversation_id=conversation_id,
        ):
            yield EngineEvent(
                type=next_event.type,
                agent_label=next_event.agent_label,
                content=next_event.content or "",
                block=next_event.block,
                message=next_event.message or "",
                data=next_event.data,
                done=next_event.done,
            )
        continue  # 跳过当前 Agent 后续事件

    yield event
```

##### Step 6: 前端收到的 WS 事件序列

```json
// 1. Secretary 产生的正常 token
{"type": "token", "agent_label": "secretary", "content": "根据诊断，你有3个薄弱点...", "request_id": "req_001"}

// 2. Secretary 产生的 delegate block（前端不渲染，仅日志）
{"type": "tool_block", "agent_label": "secretary", "block": {"type": "agent_delegate", "content": {...}}, "request_id": "req_001"}

// 3. Orchestrator 转述
{"type": "agent_message", "agent_label": "orchestrator", "content": "好的，让教学助手来帮你。", "request_id": "req_001"}

// 4. Tutor 正常流式回复
{"type": "token", "agent_label": "tutor", "content": "链式法则的公式是 dy/dx = dy/du · du/dx...", "request_id": "req_001"}
{"type": "token", "agent_label": "tutor", "content": "我们来看一个例子...", "request_id": "req_001"}

// 5. Tutor 完成
{"type": "done", "agent_label": "tutor", "done": true, "data": {...}, "request_id": "req_001"}
```

#### 7.4 前端渲染规则

| WS 事件 | 渲染方式 |
|---------|---------|
| `token(agent_label="secretary")` | Secretary 气泡，橙色头像 |
| `tool_block(type="agent_delegate")` | **不渲染**，仅前端日志可用 |
| `agent_message(agent_label="orchestrator")` | Orchestrator 气泡，紫色头像，文本居中/斜体样式 |
| `token(agent_label="tutor")` | Tutor 气泡，蓝色头像 |
| `done` | 停止流式指示器 |

#### 7.5 `conversation.path` 存储结构

**委托时不存合成用户消息**（Pipeline 参数 `save_user_msg=False`），`conv.path` 只保留真实节点：

```
conv.path = [
  user_msg_id,                          # 用户原始消息（只有这一条 role=user）
  secretary_msg_id,                     # Secretary 的 assistant 节点（内容为空）
  tutor_msg_id,                         # Tutor 的 assistant 节点（完整回复）
]
```

目标 Agent 的 Pipeline 以 `save_user_msg=False` 调用，跳过 Stage 2（不调 `tree_ops.add_message(role="user")`），直接从 Stage 3 开始。

Secretary 的 `assistant_node` 在 Secretary 的 Pipeline Stage 5 创建，因 `tool_delegate` 跳过 LLM 生成，其 `content_blocks` 仅含简短文本（如"已诊断，委托给 Tutor"）。Tutor 的 `assistant_node` 在 Tutor 自己的 Pipeline 中创建，包含完整回复。

#### 7.6 委托链案例（多层嵌套）

```
用户: "帮我分析学情，然后制定学习计划，最后讲讲薄弱点"

→ Orchestrator 路由: [secretary, tutor]

→ Secretary 流:
  token("分析你的学情：导数掌握度62%，薄弱点3个...")
  tool_delegate(target="tutor", instruction="用户薄弱点是链式法则，请讲解")

→ Orchestrator 拦截:
  agent_message("让教学助手来讲解薄弱点")

→ Tutor 流:
  token("链式法则：dy/dx = dy/du · du/dx ...")
  tool_delegate(target="coach", instruction="用户已学完链式法则，建议规划5道递进练习题")

→ Orchestrator 拦截:
  agent_message("让学习教练来安排练习计划")

→ Coach 流:
  token("为你规划了5道递进练习题...")

conv.path:
  [user_msg, secretary_msg, tutor_msg(空), coach_msg]
```

#### 7.7 实现清单

| # | 改动 | 文件 | 说明 |
|---|------|------|------|
| 1 | 注册 `tool_delegate` 共享工具 | `tool_executor.py` TOOL_DEFINITIONS | 加 tool 定义 + handler + FAST_TOOLS + block 映射 |
| 2 | 修复 register_raw_tools 参数存储 | `tool_repository.py` | action.params 嵌套，LLM schema 含完整参数 |
| 3 | Pipeline skip_llm + save_user_msg | `reply_pipeline.py` | `tool_delegate` 时跳过 Stage 5 LLM 生成；Stage 2 条件执行 |
| 4 | Engine 拦截 delegate | `conversation_engine.py` | 拦截 `tool_block(type=agent_delegate)` → 出声 + 调目标 Agent |
| 5 | AgentAdapter 接口 + 实现 | `types.py`, `tutor.py`, `coach.py`, `secretary_agent.py`, `orchestrator.py` | `save_user_msg` 参数透传 |
| 6 | 前端跳过渲染 | `ResponseBlockRenderer` | `default: return null` 自动跳过 `agent_delegate` |
| 7 | Agent 专属 tool_delegate 指引 | `prompts.py` | 各 Agent 的协作说明文本 |
| 8 | AgentPersona Provider | `context_pipeline.py` | 按 agent_label 注入指引到 system prompt |

#### 7.8 System Prompt 注入

通过 `ContextPipeline` 的 `AgentPersona` Provider 在每个 Agent 的 LLM probe 中注入 `tool_delegate` 指引。

**数据流**：

```
reply_pipeline.py Stage 4 LLM probe
  → build_llm_messages(agent_label=self.agent_label)
    → ContextPipeline.assemble()
      → TutorPersona (global SYSTEM_PROMPT)
      → AgentPersona (agent-specific delegate guide)
      → ConversationLocation
      → ...
```

**各 Agent 的指引文本**（见 `prompts.py`），以 Tutor 为例：

```
## 助手协作
系统中有 3 个 AI 助手协作服务学生：
- **coach（学习教练）**：制定学习计划、规划路径、追踪习惯、安排日程
- **secretary（学习秘书）**：分析学情、诊断薄弱点、复习提醒、学习报告

当用户的需求涉及上述助手的专长时，使用 tool_delegate 工具将对话委托给对应助手。
调用时在 instruction 中说明：用户需求、当前进展、需要目标助手做什么。
委托后，当前助手的回复将被中断，由目标助手继续输出。
```

**关键设计**：
- 指引仅在 **Stage 4 LLM probe** 注入（function-calling 阶段），Stage 5 文本生成不注入——因为 `tool_delegate` 是一个工具调用决策，不是对话内容
- `tool_dispatch.py` / `llm_core.py` 不传 `agent_label` → 默认空字符串 → `AgentPersona` 跳过 → 不影响现有调用方
```

---

## #4 ToolDetector — 工具预判策略模式 🔄

**重构文件**: `backend/app/services/llm/tool_executor.py` → 拆为 ToolDetector + ToolExecutor
**归属**: 各 Agent 内部调用

### 关键决策

- [x] 归属 → **Agent 内部组件**。每个 Agent 持有共享 ToolDetector 实例。工具检测是 Agent 的 `reply_stream()` 内部实现，Orchestrator 不需要知道
- [x] 3 个 Agent 共享同一套工具 → ToolDetector 是共享实例，不用按 Agent 分工具集

### ToolRepository — 统一工具聚合中心

**替换**: `backend/app/services/llm/tool_executor.py` + `backend/app/domain/secretary/tools/tool_registry.py`

```python
class ToolRepository:
    """所有 Agent 共享的工具注册 + 分类 + 意图检测统一中心"""
    
    tools: dict[str, ToolDefinition]
    categories: dict[str, list[str]]          # "practice" → ["tool_practice"]
    intent_patterns: dict[str, list[re.Pattern]]
    
    def discover(self, dirs: list[str]) -> int: ...
    def by_category(self, cat: str) -> list[ToolDefinition]: ...
    def to_llm_schema(self) -> list[dict]: ...
    def detect_intent(self, text: str, context: str = "") -> list[ToolIntent]: ...
```

### 预处理：多操作合并为单工具

每个后端模块可能提供多个细粒度操作。ToolRepository 在 `discover()` 后**自动合并**同类操作：

| 原始（N 个 tool） | 合并后（1 个 tool + action 参数） |
|---|---|
| `generate_practice`, `query_question_banks`, `create_question_bank` | `tool_practice(action: "generate" \| "query" \| "create", ...)` |
| `search_resources`, `view_study_plan`, `review_errors`, `open_calendar` | `tool_learning(action: "search" \| "plan" \| "errors" \| "calendar", ...)` |
| `generate_mindmap`, `generate_image`, `generate_document` | `tool_media(action: "mindmap" \| "image" \| "document", ...)` |

**合并规则**：同一 `*_tools.py` 文件的 `TOOLS` 列表自动合并为一个 tool，文件名去掉后缀作为 tool name。

**LLM 视角**：从 10+ 个独立工具缩减为 5 个语义清晰的工具（`tool_practice`, `tool_media`, `tool_search`, `tool_learning`, `tool_secretary`），每个通过 `action` 参数选择具体操作。LLM 选择工具更准，上下文更短。

### 关键决策

- [x] ToolRepository 是 DI 容器单例，注入所有 Agent
- [x] 两套旧系统合并（tool_executor.py + secretary/tools/）
- [x] 多操作预处理合并 → 一个模块 = 一个 tool + action 参数

---

## #5 ConversationEngine + ConnectionAdapter — 分离 I/O 与处理 🔄

**重构文件**: `backend/app/api/conversation/conversation_ws.py` + `conversation_routes.py` (HTTP 降级路径)
**新建**: `backend/app/domain/conversation/engine.py`

### 两层分离

```
┌─────────────────────────────────┐
│  ConnectionAdapter (thin I/O)    │  ← WS / HTTP，只做 accept/send/receive
│  conversation_ws.py (30 行)      │
│  conversation_routes.py (30 行)  │
└──────────────┬──────────────────┘
               │ 解耦
┌──────────────▼──────────────────┐
│  ConversationEngine (pure)       │  ← 不碰网络，只管消息处理
│  Orchestrator → Agent → ...     │
└─────────────────────────────────┘
```

### ConversationEngine 接口

```python
class ConversationEngine:
    def __init__(self, orchestrator: AgentAdapter, context_pipeline: ContextPipeline): ...

    async def process(
        self, user_id, text, partition_id, conversation_id="", pending_quote=None,
    ) -> AsyncGenerator[EngineEvent, None]:
        # 存用户消息 → Orchestrator 路由 → Agent 流 → done
```

**WS handler**（30 行）：accept → receive → `engine.process()` → send_json 转发  
**HTTP handler**（30 行）：收请求 → `engine.process()` → 收集事件 → 返回 JSON  
两者共用同一个 ConversationEngine 实例。

### TODO

- [ ] `active_streams` 管理迁移到 ConversationEngine 内部
- [ ] `_publish_reply_event` 作为 PostProcessor 处理
- [ ] 情绪检测（fire-and-forget）迁移到 ConversationEngine 的 PostProcessor 链

---

## #6 TreeStore — 聚合根 + 查询/变更分离 🔄

**替换文件**: `backend/app/services/knowledge/tree_ops.py` + 6 个 mixin 文件  
**新建**: `backend/app/domain/conversation/tree_store.py` (TreeQuery + TreeMutate + TreeStore)

### 查询/变更分离

```python
class TreeQuery:
    """只读操作 — 零副作用"""
    storage: DataStorage

    def get_node(self, user_id, node_id) -> TreeNode | None: ...
    def get_conversation(self, user_id, cid) -> Conversation | None: ...
    def get_ancestor_chain(self, user_id, cid) -> AncestorChain: ...   # PDTC 完整路径
    def list_messages(self, user_id, cid, offset=0, limit=50) -> list[TreeNode]: ...
    def list_path(self, user_id, node_id) -> PathSegment: ...
        """查询某个节点/对话所在的最新路径，返回 partition→domain→topic→conversation 全链路信息。
        前端侧边栏自动展开路径、面包屑导航等直接使用。"""
    def find_active_conversation(self, user_id, partition_id) -> Conversation | None: ...
    def list_children(self, user_id, parent_id, level) -> list: ...
    async def auto_resolve(self, ...) -> ResolveRoute: ...   # classifier 并入

class TreeMutate:
    """写操作 — 产出事件"""
    storage: DataStorage
    event_bus: EventBus

    def create_partition(self, ...) -> PartitionCreated: ...
    def add_message(self, user_id, cid, role, blocks, agent_label="") -> TreeNode: ...
    def move_subtree(self, ...) -> SubtreeMoved: ...
    def delete_conversation(self, ...) -> ConversationDeleted: ...

class TreeStore:
    """聚合根 — 组合而非继承"""
    def __init__(self, storage: DataStorage, event_bus: EventBus):
        self.query = TreeQuery(storage)
        self.mutate = TreeMutate(storage, event_bus)
```

### 存储适配器

```python
class DataStorage(Protocol):
    def load(self, user_id) -> UserData: ...
    def save(self, user_id, data) -> None: ...

class PgStorage(DataStorage): ...       # 生产
class JsonFileStorage(DataStorage): ...  # 开发
class InMemoryStorage(DataStorage): ...  # 测试
```

### SyncHook 事件驱动

Sync 不再被 Mixin 隐式调用。TreeMutate 产出领域事件，独立 SyncHook 订阅：

```
TreeMutate.create_partition() → emit PartitionCreated → SyncHook.on_partition_created()
TreeMutate.rename_partition()  → emit PartitionRenamed  → SyncHook.on_partition_renamed()
```

### 关键决策

- [x] 查询/变更分离 → TreeQuery 只读 + TreeMutate 读写
- [x] list_path → 查询节点所在完整 PDTC 路径，前端侧边栏自动展开
- [x] auto_resolve 并入 TreeQuery → 分类器不需要独立模块
- [x] 存储可注入 → DataStorage 接口。PG / JSON / InMemory 三个适配器
- [x] Sync 事件驱动 → 不再从 Mixin 隐式调用