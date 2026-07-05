"""Agent 工具系统 — 基类定义（re-export 统一实现）

为保持向后兼容，所有秘书工具仍可从本模块导入 `ToolDefinition`、`ToolResult`。
实际定义在 `app.infrastructure.llm.tool_registry`（单一来源，Task #37 合并）。

统一后的 dataclass：

  ToolDefinition (继承 ToolInfo)
    ├─ 来自 ToolInfo：name / zh_name / icon / description /
    │                 parameters / required / block_type /
    │                 is_slow / is_inline / is_suspending
    └─ 来自秘书原 ToolDefinition：handler / route / require_confirmation

  ToolResult
    success / data / error / route_target / route_params / confirmation_text

新代码建议直接 `from app.infrastructure.llm.tool_registry import ToolDefinition, ToolResult`。
"""

from __future__ import annotations

from app.infrastructure.llm.tool_registry import ToolDefinition, ToolResult

__all__ = ["ToolDefinition", "ToolResult"]
