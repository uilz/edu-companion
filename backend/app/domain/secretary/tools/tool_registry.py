""""Agent 工具注册表 — 自动发现 + 注册 + 执行"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any

from .base import ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表 — 全局单例"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def discover(self, tools_dir: str) -> int:
        """自动发现 tools/ 目录下所有 *_tools.py 并注册"""
        base = Path(tools_dir)
        count = 0
        for py_file in sorted(base.glob("*_tools.py")):
            module_name = py_file.stem
            spec = importlib.util.spec_from_file_location(
                f"agent_tools.{module_name}", str(py_file)
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            tools = getattr(module, "TOOLS", [])
            for tool in tools:
                self.register(tool)
                count += 1
        return count

    def register(self, tool: ToolDefinition) -> None:
        """注册一个工具"""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> ToolDefinition | None:
        """获取指定工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """列出所有已注册工具名称"""
        return list(self._tools.keys())

    async def execute(self, name: str, params: dict[str, Any]) -> ToolResult:
        """执行指定工具"""
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Tool not found: {name}")
        return await tool.handler(params)

    def get_schema(self) -> list[dict[str, Any]]:
        """导出 LLM 用的 Function Calling schema 列表"""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            })
        return schemas