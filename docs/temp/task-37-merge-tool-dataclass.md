# Task #37 — 合并秘书 ToolDefinition 与 LLM ToolInfo dataclass

## 背景

当前项目里有两套独立的"工具定义"dataclass，互不兼容：

| 位置 | 类名 | 字段 |
|------|------|------|
| `app.infrastructure.llm.tool_registry.py` | `ToolInfo` | name, zh_name, icon, description, parameters, required, block_type, is_slow, is_inline, is_suspending |
| `app.domain.secretary.tools.base.py` | `ToolDefinition` | name, description, parameters, handler, route, require_confirmation |
| `app.domain.secretary.tools.base.py` | `ToolResult` | data, route_target, route_params, confirmation_text |

后果：
- 秘书 Agent 工具的元信息（中文名、图标、block_type）必须在多处重新声明
- 秘书 `ToolDefinition` 无法直接接入 LLM 工具注册表
- 两套 schema 互相转换易出错

## 方案

**方案 A（采用）**：让 `ToolDefinition` 继承 `ToolInfo`，把 `ToolResult` 合并进来。

```python
# app.infrastructure.llm.tool_registry.py
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
    """工具执行结果 — 统一所有工具的返回类型"""
    success: bool = True
    data: dict = field(default_factory=dict)
    error: str | None = None
    route_target: str | None = None       # 秘书 Agent 跳转目标
    route_params: dict | None = None      # 跳转参数
    confirmation_text: str = ""           # 用户确认提示


@dataclass
class ToolDefinition(ToolInfo):
    """统一工具定义 — 继承 ToolInfo 增加执行能力"""
    handler: Callable | None = None
    route: dict | None = None
    require_confirmation: bool = True
```

## 实施

### 文件改动

1. `backend/app/infrastructure/llm/tool_registry.py` — 新增 `ToolResult` 与 `ToolDefinition`（继承 `ToolInfo`）
2. `backend/app/domain/secretary/tools/base.py` — 改为 re-export，零业务改动
3. `backend/app/domain/secretary/tools/*.py` — 无需改动（字段名一致）
4. `backend/app/domain/secretary/tools/tool_registry.py` — 无需改动（API 一致）

### 兼容性

- `from app.domain.secretary.tools.base import ToolDefinition, ToolResult` 仍然可用（re-export）
- LLM 侧 `ToolRepository.discover()` 已能读取 secretary 工具的 `handler` / `parameters`
- `tool_repository.py` 中的 `ToolDefinition`（composite tool）命名冲突，保留以避免大改

## 验证

- 现有 `test_agent_tool_registry.py` 全部通过
- 现有 `test_agent_tools.py` 全部通过
- `ToolRepository.discover()` 仍能发现秘书工具
- 秘书 `ToolRegistry` 仍能注册/执行
- 启动时 `rebuild.sh` 无报错

## 风险

- `tool_repository.py` 自己的 `ToolDefinition`（composite）未重命名，与秘书 `ToolDefinition` 命名相同但含义不同
  - **缓解**：保留两个独立类（复合工具概念本质上不同），添加注释说明
  - **未来重构**：可把 `tool_repository.py.ToolDefinition` 重命名为 `CompositeTool`
