""""Agent 工具系统 — 基类定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolResult:
    """工具执行结果"""
    data: dict[str, Any] = field(default_factory=dict)
    route_target: str | None = None
    route_params: dict[str, str] | None = None
    confirmation_text: str = ""


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[ToolResult]]
    route: dict[str, Any] | None = None
    require_confirmation: bool = True