"""练习工具 — 开始练习与测验"""

from __future__ import annotations

from app.domain.secretary.tools.base import ToolDefinition, ToolResult


async def start_practice_handler(params: dict[str, str]) -> ToolResult:
    """开始练习"""
    subject = params.get("subject", "")
    count = int(params.get("count", 10))
    return ToolResult(
        data={"subject": subject, "count": count},
        route_target="/practice",
        route_params={"subject": subject, "count": str(count)},
        confirmation_text=f"即将开始 {subject} 练习，共 {count} 题",
    )


async def start_quiz_handler(params: dict[str, str]) -> ToolResult:
    """开始测验"""
    topic = params.get("topic", "")
    return ToolResult(
        data={"topic": topic},
        route_target="/practice",
        route_params={"topic": topic, "mode": "quiz"},
        confirmation_text=f"即将开始「{topic}」测验",
    )


TOOLS = [
    ToolDefinition(
        name="start_practice",
        description="开始指定科目的练习",
        parameters={
            "subject": {
                "type": "string",
                "description": "练习科目，如微积分、线性代数、概率论等",
            },
            "count": {
                "type": "integer",
                "description": "练习题数量，默认 10",
            },
        },
        handler=start_practice_handler,
        require_confirmation=True,
        route={"target": "/practice"},
    ),
    ToolDefinition(
        name="start_quiz",
        description="开始指定主题的测验",
        parameters={
            "topic": {
                "type": "string",
                "description": "测验主题，如极限、导数、积分等",
            },
        },
        handler=start_quiz_handler,
        require_confirmation=True,
        route={"target": "/practice", "params": {"mode": "quiz"}},
    ),
]