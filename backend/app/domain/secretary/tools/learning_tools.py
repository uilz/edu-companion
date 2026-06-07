"""学习工具 — 资源搜索、计划、错题、日历"""

from __future__ import annotations

from app.domain.secretary.tools.base import ToolDefinition, ToolResult


async def search_resources_handler(params: dict[str, str]) -> ToolResult:
    """搜索学习资源"""
    keyword = params.get("keyword", "")
    return ToolResult(
        data={"keyword": keyword},
        route_target="/resources",
        route_params={"search": keyword},
        confirmation_text=f"即将搜索「{keyword}」相关学习资源",
    )


async def view_study_plan_handler(params: dict[str, str]) -> ToolResult:
    """查看学习计划"""
    return ToolResult(
        data={},
        route_target="/study",
        confirmation_text="即将打开学习计划页面",
    )


async def review_errors_handler(params: dict[str, str]) -> ToolResult:
    """复习错题"""
    subject = params.get("subject", "")
    if subject:
        return ToolResult(
            data={"subject": subject},
            route_target="/errors",
            route_params={"subject": subject},
            confirmation_text=f"即将复习「{subject}」错题",
        )
    return ToolResult(
        data={},
        route_target="/errors",
        confirmation_text="即将打开错题本",
    )


async def open_calendar_handler(params: dict[str, str]) -> ToolResult:
    """查看学习日历"""
    return ToolResult(
        data={},
        route_target="/calendar",
        confirmation_text="即将打开学习日历",
    )


TOOLS = [
    ToolDefinition(
        name="search_resources",
        description="搜索学习资源，如视频教程、文档、讲义等",
        parameters={
            "keyword": {
                "type": "string",
                "description": "搜索关键词，如「微积分视频」「线性代数讲义」",
            },
        },
        handler=search_resources_handler,
        route={"target": "/resources"},
        require_confirmation=False,
    ),
    ToolDefinition(
        name="view_study_plan",
        description="查看或创建学习计划，规划每日学习任务",
        parameters={},
        handler=view_study_plan_handler,
        route={"target": "/study"},
        require_confirmation=False,
    ),
    ToolDefinition(
        name="review_errors",
        description="查看和复习错题，巩固薄弱知识点",
        parameters={
            "subject": {
                "type": "string",
                "description": "科目名称，如「数学」「物理」，不填则查看全部错题",
            },
        },
        handler=review_errors_handler,
        route={"target": "/errors"},
        require_confirmation=False,
    ),
    ToolDefinition(
        name="open_calendar",
        description="查看学习日历，了解学习进度和日程安排",
        parameters={},
        handler=open_calendar_handler,
        route={"target": "/calendar"},
        require_confirmation=False,
    ),
]