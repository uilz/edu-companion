# AI Tool Architecture

AI tool system = how LLM invoke domain functions. 3 layers, 2 execution paths. All tools defined centrally, auto-discovered, executed via pipeline.

---

## 1. Architecture Overview

```
                    ┌──────────────────────────────────────┐
                    │     tool_registry.py (SSoT)          │
                    │  ALL_TOOL_INFO: dict[str, ToolInfo]  │
                    │  → get_all_tool_definitions()        │
                    │  → get_fast_tools() / get_slow_tools()│
                    └──────────────┬───────────────────────┘
                                   │ derived
                    ┌──────────────▼───────────────────────┐
                    │     tool_repository.py               │
                    │  ToolRepository (singleton)          │
                    │  ─ discover() scan *_tools.py        │
                    │  ─ merge tools → composite + action  │
                    │  ─ to_llm_schema() → OpenAI schema   │
                    │  ─ detect_intent() → regex matching  │
                    └──────┬──────────────────┬────────────┘
                           │                  │
              ┌────────────▼──┐     ┌─────────▼───────────┐
              │ ToolExecutor  │     │ ToolRegistry (Agent) │
              │ fast/slow     │     │ discover() + exec()  │
              │ TOOL_HANDLERS │     │ /api/secretary/agent │
              └────┬──────────┘     └─────────┬───────────┘
                   │                          │
                   ▼                          ▼
           ┌───────────────┐       ┌───────────────────┐
           │ knowledge_ops │       │ learning_tools.py │
           │ _tools.py     │       │ practice_tools.py │
           │ (8 handlers)  │       │ navigation_tools  │
           └───────────────┘       └───────────────────┘
```

### 1.1 Three Tool Layers

| Layer | File | Purpose |
|-------|------|---------|
| **SSoT** | `backend/app/infrastructure/llm/tool_registry.py` | Single Source of Truth — `ToolInfo` per tool: name, zh_name, icon, description, parameters, block_type, is_slow, is_inline |
| **Aggregation** | `backend/app/infrastructure/llm/tool_repository.py` | Auto-discover `*_tools.py`, merge → composite tools, generate LLM schemas, regex intent detection |
| **Execution** | `backend/app/infrastructure/llm/tool_executor.py` | `TOOL_HANDLERS` map, `ToolExecutor.execute()` → fast inline or slow placeholder |

### 1.2 Two Execution Paths

| Path | Entry | Used By |
|------|-------|---------|
| **Non-streaming** | `tool_dispatch.py` | Main chat — regex pre-detect + LLM function calling → `ToolExecutor.execute()` |
| **Streaming** | `reply_pipeline.py` → `llm_service.generate_stream_with_tools()` | SSE chat — emits `tool_calls` / `block_update` events |
| **Agent Chat** | `/api/secretary/agent/chat` SSE | Secretary page — `ToolRegistry.discover()` → `agent_generate_stream()` → `ToolRegistry.execute()` |

Both paths feed LLM `tools` param with schemas from `tool_repository.to_llm_schema()`.

---

## 2. Defining a New Tool

### 2.1 Register in SSoT: `backend/app/infrastructure/llm/tool_registry.py`

Add entry to `ALL_TOOL_INFO` dict:

```python
"tool_name": ToolInfo(
    name="tool_name",                    # unique, kebab-case
    zh_name="中文显示名",
    icon="🔧",                           # emoji display in frontend
    description="LLM function calling description — be precise, LLM reads this",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "what it does"},
            "param2": {"type": "integer", "description": "count", "default": 5},
        },
        "required": ["param1"],
    },
    block_type="video",                  # ResponseBlock.type or None
    is_slow=False,                       # True → background job, frontend polls
    is_inline=False,                     # True → handled in reply_pipeline directly
)
```

Key fields:
- **name** — must match key; kebab-case; LLM uses this for tool_calls
- **description** — LLM sees this; explain WHEN to call, not just what
- **parameters** — JSON Schema object; LLM parses params from user message
- **block_type** — maps to `ResponseBlock.type`; frontend renders accordingly
- **is_slow** — slow tools get placeholder `status="generating"`, processed by background job
- **is_inline** — inline tools skip `ToolExecutor`, handled directly in `reply_pipeline.py` (only `rename_conversation` currently)

Derived exports auto-generated:
- `get_all_tool_definitions()` → LLM schema list
- `get_fast_tools()` / `get_slow_tools()` → sets for `ToolExecutor`
- `get_tool_display_map()` → frontend display names

### 2.2 Add Handler in `tool_executor.py`

Add async handler fn, register in `TOOL_HANDLERS`:

```python
async def _handle_my_tool(params: dict) -> dict:
    """Short docstring — what this tool does"""
    # Parse params
    query = params.get("query", "")
    # Call domain service
    result = await some_service.some_method(query)
    # Return dict → wrapped in ResponseBlock
    return {"key": "value", "status": "ok"}

TOOL_HANDLERS = {
    ...,
    "my_tool": _handle_my_tool,
}
```

Handler contract:
- Input: `params: dict` — parsed from LLM function calling args (user_id auto-injected by `ToolExecutor.execute()`)
- Output: `dict` — wrapped into `ResponseBlock(content=result)`
- Exception: caller catches, sets `status="failed"`
- No side-channel I/O (files, network) unless necessary

### 2.3 (Optional) Knowledge Ops Tool — Dual Registration Required

Knowledge ops tools need registration in **two** places because they use a legacy dual-registration pattern:

**File 1: `backend/app/infrastructure/llm/tool_registry.py` (SSoT)**
- Add `ToolInfo` entry to `ALL_TOOL_INFO` (same as 2.1)

**File 2: `backend/app/infrastructure/llm/knowledge_ops_tools.py` (handlers + schema)**
- Add LLM schema entry to `TOOL_DEFINITIONS` list (raw LLM format)
- Add handler fn to `TOOL_HANDLERS` dict
- No need to touch `tool_executor.py` — handlers auto-merged via `TOOL_HANDLERS.update(KTOOL_HANDLERS)`

In `main.py`, both `TOOL_DEFINITIONS` (from tool_registry via tool_repository) and `KTOOL_DEFINITIONS` (from knowledge_ops_tools) are registered via `register_raw_tools()`. No main.py change needed for new tools — auto-picked up on restart.

### 2.4 (Optional) Agent Tool

Agent tools (secretary page) live in `backend/app/domain/secretary/tools/`. Since **Task #37**, agent `ToolDefinition` and LLM `ToolInfo` are **unified** into a single dataclass in `backend/app/infrastructure/llm/tool_registry.py` — the same class drives both LLM tool registry and Secretary Agent.

#### Dataclass hierarchy (single source of truth)

```python
# backend/app/infrastructure/llm/tool_registry.py

@dataclass
class ToolInfo:
    """LLM 工具元信息（轻量、无 handler）"""
    name: str
    zh_name: str = ""
    icon: str = "🔧"
    description: str = ""
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    required: list[str] = field(default_factory=list)
    block_type: str | None = None
    is_slow: bool = False
    is_inline: bool = False
    is_suspending: bool = False


@dataclass
class ToolResult:
    """工具执行结果 — 统一所有工具的返回类型

    - 普通 LLM 工具：填 data / success / error
    - 秘书 Agent 工具：再填 route_target / route_params / confirmation_text
    """
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    route_target: str | None = None       # 秘书 Agent 跳转目标页面
    route_params: dict[str, Any] | None = None
    confirmation_text: str = ""           # 用户确认提示


@dataclass
class ToolDefinition(ToolInfo):
    """统一工具定义 — 继承 ToolInfo 增加执行能力

    字段增量（相对 ToolInfo）：
      handler              — 异步执行函数
      route                — 静态路由描述（与 handler 返回的 route_target 二选一）
      require_confirmation — 前端是否需要确认弹窗
    """
    handler: Callable[[dict[str, Any]], Awaitable[ToolResult]] | None = None
    route: dict[str, Any] | None = None
    require_confirmation: bool = True
```

**Recommended import** (new code):
```python
from app.infrastructure.llm.tool_registry import ToolDefinition, ToolResult
```

**Backward-compat import** (still works via re-export):
```python
from app.domain.secretary.tools.base import ToolDefinition, ToolResult
```

#### Agent tool example

```python
# backend/app/domain/secretary/tools/my_feature_tools.py
from app.infrastructure.llm.tool_registry import ToolDefinition, ToolResult
# or: from app.domain.secretary.tools.base import ToolDefinition, ToolResult  # 后向兼容


async def _handler(params: dict) -> ToolResult:
    return ToolResult(
        data={"key": "value"},
        route_target="/some-page",
        route_params={"param": params.get("x", "")},
        confirmation_text="确认跳转到目标页？",
    )


TOOLS = [
    ToolDefinition(
        name="my_tool",
        zh_name="我的工具",               # 来自 ToolInfo
        icon="✨",                        # 来自 ToolInfo
        description="LLM description",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "string", "description": "输入"},
            },
        },
        handler=_handler,                 # 来自 ToolDefinition
        require_confirmation=True,        # 来自 ToolDefinition
    ),
]
```

Agent tools auto-discovered by **two paths**:
- `ToolRegistry.discover()` in `backend/app/domain/secretary/tools/tool_registry.py` → Secretary Agent `/api/secretary/agent/chat`
- `ToolRepository.discover()` in `backend/app/infrastructure/llm/tool_repository.py` → LLM tool schema, regex intent detection

### 2.5 (Optional) Composite Tool Registration

`ToolRepository.discover()` auto-merges `*_tools.py` with multiple `TOOLS` entries → single composite with `action` param. If tool doesn't follow `*_tools.py` pattern, register manually in `backend/app/main.py`:

```python
repo = get_tool_repository()
repo.register_raw_tools(MY_TOOL_DEFINITIONS)
```

---

## 3. Complete Tool Lifecycle

### 3.1 Execution Flow (non-streaming path)

The non-streaming path in `tool_dispatch.py` has **two branches**:

```
User Message → generate_reply_with_tools()

  Branch A — Regex pre-detect matched:
    get_tool_repository().detect_intent(text, context)
      → _build_tool_params() → tool_executor.execute() → ResponseBlock
      → _summarize_tool_result() → _build_tool_context()
      → LLM generate(context includes tool results) → text block + tool blocks
      → Slow tools get background job submitted

  Branch B — No regex match:
    get_tool_repository().to_llm_schema() → LLM generate(tools=schemas)
      ↓
    ├─ LLM returns tool_calls:
    │     → execute each: tool_executor.execute(name, args)
    │     → add tool results as role:"tool" messages
    │     → _build_tool_context() → 2nd LLM call with results
    │     → text block + tool blocks
    │     → Slow tools get background job submitted
    │
    └─ LLM returns pure text:
          → text ResponseBlock only

ToolExecutor.execute(name, params, user_id):
  → if name in FAST_TOOLS: _execute_inline() → await handler(params) → ResponseBlock(status="ready")
  → if name in SLOW_TOOLS: _create_placeholder() → ResponseBlock(status="generating")
                              → background job → frontend polls for completion
```

The streaming path (`reply_pipeline.py` → `llm_service.generate_stream_with_tools()`) follows a similar pattern but emits SSE events: `tool_calls` → `block_update` for real-time UI updates as tools execute.

### 3.2 Frontend Rendering

Each `block_type` maps to a React component in `frontend/src/components/conversation/blocks/`:
- `video` → `VideoBlock.tsx`
- `practice` → `PracticeBlock.tsx`
- `image` → `ImageBlock.tsx`
- etc.

Display names/icons in `frontend/src/lib/tool-registry.ts`:
```typescript
export const TOOL_REGISTRY: Record<string, { zh: string; icon: string }> = {
  search_media: { zh: "搜索学习资源", icon: "🔍" },
  ...
}
```

Must sync SSoT names with frontend registry.

---

## 4. Standard Process: New Tool

### Step 1 — Requirement Clarification

Before coding, clarify:
- What domain function executed?
- What params LLM needs to extract from user message?
- What response type returned? (text block / video / practice / image / mindmap / document / question)
- Fast or slow? (fast = synchronous within HTTP req; slow = background job + polling)
- Conversation tool or agent-only tool?

### Step 2 — Register in SSoT

Edit `backend/app/infrastructure/llm/tool_registry.py`:
- Add `ToolInfo` entry to `ALL_TOOL_INFO`
- Set correct `block_type`, `is_slow`, `is_inline`

### Step 3 — Implement Handler (choose path based on tool type)

Handler location depends on tool type:

| Tool Type | Handler File | How |
|-----------|-------------|-----|
| **Conversation tool** (search_media, generate_practice, ...) | `backend/app/infrastructure/llm/tool_executor.py` | Add async handler fn, register in `TOOL_HANDLERS` dict |
| **Knowledge ops tool** (knowledge_add_node, ...) | `backend/app/infrastructure/llm/knowledge_ops_tools.py` | Add handler fn, register in `TOOL_HANDLERS` dict. Also add LLM schema to `TOOL_DEFINITIONS` list in same file |
| **Agent tool** (secretary-only) | `backend/app/domain/secretary/tools/my_tool.py` (new file) | Create `*_tools.py` with `TOOLS` list, each item a `ToolDefinition` with handler |

### Step 4 — Update Frontend Registry

Edit `frontend/src/lib/tool-registry.ts`:
- Add entry matching `ALL_TOOL_INFO[name]`
- If new `block_type`, add React component in `frontend/src/components/conversation/blocks/`

### Step 5 — Restart & Test

```bash
bash rebuild.sh
```

Test with conversation triggering the tool.

---

## 5. Key Constraints

| Constraint | Rule |
|-----------|------|
| **SSoT** | `tool_registry.py` in `ALL_TOOL_INFO` is the name/description/params source. Knowledge ops tools ALSO define schema in `knowledge_ops_tools.py` (dual registration). All other tool types must NOT duplicate SSoT. |
| **Handler signature** | `async def handler(params: dict) -> dict` — no framework coupling |
| **LLM description** | Explain WHEN to invoke, not just what. "Generate practice questions when user asks for exercise on a topic" not "Practice question generator" |
| **Parameter schema** | JSON Schema only. `enum` for bounded choices, `description` for each param. |
| **Fast vs Slow** | Fast = response within same HTTP request (< 5s). Slow = background job + frontend polling (`status="generating"`) |
| **Inline** | Only for tools that modify conversation state mid-stream (`rename_conversation`). Avoid adding new inline tools. |
| **Error handling** | Handler catches expected errors, returns `{"error": ..., "fallback": True}` dict. Unexpected exceptions → `status="failed"` ResponseBlock. |
| **Frontend sync** | Every tool in `ALL_TOOL_INFO` must have matching entry in `frontend/src/lib/tool-registry.ts`. |

---

## 6. File Index

| File | Role |
|------|------|
| `backend/app/infrastructure/llm/tool_registry.py` | **SSoT** — `ToolInfo` (LLM 元信息) + `ToolResult` (执行结果) + `ToolDefinition` (继承 ToolInfo 加 handler/route/require_confirmation) |
| `backend/app/infrastructure/llm/tool_repository.py` | Aggregation + merge + LLM schema + intent detection |
| `backend/app/infrastructure/llm/tool_executor.py` | Fast/slow execution with handlers |
| `backend/app/infrastructure/llm/tool_dispatch.py` | Dispatch orchestrator (regex + LLM function calling) |
| `backend/app/infrastructure/llm/knowledge_ops_tools.py` | Knowledge tree tool definitions + 8 handlers |
| `backend/app/domain/secretary/tools/base.py` | 后向兼容 re-export (Task #37 后仅 re-export `tool_registry` 中的类) |
| `backend/app/domain/secretary/tools/tool_registry.py` | Secretary Agent `ToolRegistry` — auto-discovery + execution |
| `backend/app/domain/secretary/tools/*_tools.py` | Agent tool definitions (practice, learning, knowledge_tree, navigation) |
| `backend/app/domain/secretary/agent_llm.py` | Agent LLM streaming with tool schema |
| `backend/app/domain/conversation/reply_pipeline.py` | Streaming pipeline — inline tool handling |
| `backend/app/main.py` (startup) | `ToolRepository.discover()` + `register_raw_tools()` |
| `frontend/src/lib/tool-registry.ts` | Frontend display names/icons |
| `backend/tests/test_agent_tool_registry.py` | Tests |
