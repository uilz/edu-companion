"""知识树工具 — 搜索与导航"""

from __future__ import annotations

from app.domain.secretary.tools.base import ToolDefinition, ToolResult


async def search_knowledge_tree_handler(params: dict[str, str]) -> ToolResult:
    """在知识树中搜索节点"""
    query = params.get("query", "")
    return ToolResult(
        data={"query": query},
        route_target="/knowledge-tree",
        route_params={"search": query},
        confirmation_text=f"即将在知识树中搜索「{query}」",
    )


async def expand_knowledge_node_handler(params: dict[str, str]) -> ToolResult:
    """展开知识树中的指定节点"""
    node_id = params.get("node_id", "")
    return ToolResult(
        data={"node_id": node_id},
        route_target="/knowledge-tree",
        route_params={"node": node_id},
        confirmation_text=f"即将展开节点 {node_id}",
    )


TOOLS = [
    ToolDefinition(
        name="search_knowledge_tree",
        description="在知识树中搜索指定主题或概念",
        parameters={
            "query": {
                "type": "string",
                "description": "搜索关键词，如微积分、导数、极限等",
            },
        },
        handler=search_knowledge_tree_handler,
        require_confirmation=True,
    ),
    ToolDefinition(
        name="expand_knowledge_node",
        description="展开知识树中指定节点的详情",
        parameters={
            "node_id": {
                "type": "string",
                "description": "知识树节点 ID",
            },
        },
        handler=expand_knowledge_node_handler,
        require_confirmation=True,
    ),
]