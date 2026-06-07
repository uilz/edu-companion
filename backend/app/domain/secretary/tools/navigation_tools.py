"""导航工具 — 页面跳转"""

from __future__ import annotations

from app.domain.secretary.tools.base import ToolDefinition, ToolResult


async def navigate_to_page_handler(params: dict[str, str]) -> ToolResult:
    """跳转到指定页面"""
    target = params.get("target", "/dashboard")
    return ToolResult(
        data={"page": target},
        route_target=target,
        confirmation_text=f"即将跳转到 {target}",
    )


async def navigate_to_dashboard_handler(params: dict[str, str]) -> ToolResult:
    """跳转到仪表盘"""
    return ToolResult(
        data={"page": "/dashboard"},
        route_target="/dashboard",
        confirmation_text="即将返回仪表盘",
    )


TOOLS = [
    ToolDefinition(
        name="navigate_to_page",
        description="跳转到指定页面，如知识树、练习、仪表盘等",
        parameters={
            "target": {
                "type": "string",
                "description": "目标页面路径，如 /knowledge-tree, /practice, /dashboard",
                "enum": [
                    "/dashboard",
                    "/knowledge-tree",
                    "/practice",
                    "/learn",
                    "/focus",
                    "/secretary",
                    "/secretary/settings",
                ],
            },
        },
        handler=navigate_to_page_handler,
        require_confirmation=True,
    ),
    ToolDefinition(
        name="navigate_to_dashboard",
        description="返回仪表盘首页",
        parameters={},
        handler=navigate_to_dashboard_handler,
        require_confirmation=False,
    ),
]