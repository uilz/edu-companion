"""
知识树操作工具 — 统一的 LLM Function Calling 格式 + 执行处理器

注册方式：
  1. TOOL_DEFINITIONS → register_raw_tools() → ToolRepository（LLM Schema）
  2. TOOL_HANDLERS → ToolExecutor（pipeline 执行）
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.schemas.conversation import ResponseBlock

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# LLM Function Calling 格式工具定义
# ═══════════════════════════════════════════════

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "knowledge_add_node",
            "description": "在当前知识树节点下添加一个新子节点",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string", "description": "父节点 ID"},
                    "label": {"type": "string", "description": "节点名称/标题"},
                    "brief": {"type": "string", "description": "节点简介说明"},
                    "level": {"type": "string", "enum": ["domain", "topic", "concept"], "description": "节点层级", "default": "concept"},
                },
                "required": ["parent_id", "label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_edit_node",
            "description": "编辑知识树节点的信息（名称、简介等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "要编辑的节点 ID"},
                    "label": {"type": "string", "description": "新的节点名称"},
                    "brief": {"type": "string", "description": "新的节点简介"},
                    "emoji": {"type": "string", "description": "节点 emoji 图标"},
                },
                "required": ["node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_expand_node",
            "description": "AI 自动为指定知识节点生成子节点，扩充知识树",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "要展开的节点 ID"},
                    "depth": {"type": "integer", "description": "展开深度（建议 2-3）", "default": 2},
                    "direction": {"type": "string", "enum": ["children", "parents", "both"], "description": "展开方向", "default": "children"},
                },
                "required": ["node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_delete_node",
            "description": "删除知识树中的指定节点",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "要删除的节点 ID"},
                },
                "required": ["node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_add_relation",
            "description": "在两个知识节点之间建立关联边",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_node_id": {"type": "string", "description": "源节点 ID"},
                    "to_node_id": {"type": "string", "description": "目标节点 ID"},
                    "relation_type": {"type": "string", "enum": ["related", "prerequisite", "extension"], "description": "关联类型", "default": "related"},
                },
                "required": ["from_node_id", "to_node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_get_node_context",
            "description": "查询知识树节点的上下文信息，包括父链（祖先路径）、子链（子树）、关联节点",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "节点 ID"},
                    "include_ancestors": {"type": "boolean", "description": "是否包含父链", "default": True},
                    "include_descendants": {"type": "boolean", "description": "是否包含子链", "default": True},
                    "include_relations": {"type": "boolean", "description": "是否包含关联节点", "default": True},
                    "max_depth": {"type": "integer", "description": "递归深度限制", "default": 3},
                },
                "required": ["node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search_nodes",
            "description": "在知识树中搜索节点，支持按名称/标签搜索，可限定搜索范围",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词（支持中文）"},
                    "scope_node_id": {"type": "string", "description": "限定在该节点及其子树下搜索，留空则搜索全部"},
                    "max_results": {"type": "integer", "description": "最大返回数量", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_recommend",
            "description": "获取知识树节点的学习推荐，如推荐展开子节点、跳转到关联节点等",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "当前节点 ID"},
                    "recommend_type": {"type": "string", "enum": ["expand", "deep_dive", "related"], "description": "推荐类型", "default": "expand"},
                },
                "required": ["node_id"],
            },
        },
    },
]

FAST_KNOWLEDGE_TOOLS: set[str] = {
    "knowledge_get_node_context",
    "knowledge_search_nodes",
    "knowledge_recommend",
    "knowledge_add_node",
    "knowledge_edit_node",
    "knowledge_delete_node",
    "knowledge_add_relation",
}

SLOW_KNOWLEDGE_TOOLS: set[str] = {
    "knowledge_expand_node",
}


# ═══════════════════════════════════════════════
# 工具执行处理器
# ═══════════════════════════════════════════════


async def _handle_add_node(params: dict) -> dict:
    """添加子节点"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    parent_id = params.get("parent_id", "")
    label = params.get("label", "")
    brief = params.get("brief", "")
    level = params.get("level", "concept")

    try:
        node = kn_svc.add_node(
            user_id=user_id,
            parent_id=parent_id,
            label=label,
            brief=brief,
            level=level,
        )
        return {"ok": True, "node_id": node.id, "label": node.label}
    except Exception as e:
        logger.exception("knowledge_add_node 失败")
        return {"ok": False, "error": str(e)}


async def _handle_edit_node(params: dict) -> dict:
    """编辑节点信息"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    node_id = params.get("node_id", "")

    updates = {}
    if params.get("label"):
        updates["label"] = params["label"]
    if params.get("brief"):
        updates["brief"] = params["brief"]
    if params.get("emoji"):
        updates["emoji"] = params["emoji"]

    try:
        kn_svc.update_node(user_id, node_id, **updates)
        return {"ok": True, "node_id": node_id, "updates": updates}
    except Exception as e:
        logger.exception("knowledge_edit_node 失败")
        return {"ok": False, "error": str(e)}


async def _handle_expand_node(params: dict) -> dict:
    """AI 展开节点"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    node_id = params.get("node_id", "")
    depth = params.get("depth", 2)
    direction = params.get("direction", "children")

    try:
        node = kn_svc.get_node(user_id, node_id)
        if not node:
            return {"ok": False, "error": "节点不存在"}

        from app.services.knowledge_tree.ai_expansion_service import expand_node as ai_expand
        result = await ai_expand(user_id, node_id, depth, direction)
        return {"ok": True, "node_id": node_id, "result": result}
    except Exception as e:
        logger.exception("knowledge_expand_node 失败")
        return {"ok": False, "error": str(e)}


async def _handle_delete_node(params: dict) -> dict:
    """删除节点"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    node_id = params.get("node_id", "")

    try:
        kn_svc.delete_node(user_id, node_id)
        return {"ok": True, "node_id": node_id}
    except Exception as e:
        logger.exception("knowledge_delete_node 失败")
        return {"ok": False, "error": str(e)}


async def _handle_add_relation(params: dict) -> dict:
    """添加关联边"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    from_id = params.get("from_node_id", "")
    to_id = params.get("to_node_id", "")
    rel_type = params.get("relation_type", "related")

    try:
        kn_svc.add_relation(user_id, from_id, to_id, rel_type)
        return {"ok": True, "from": from_id, "to": to_id, "type": rel_type}
    except Exception as e:
        logger.exception("knowledge_add_relation 失败")
        return {"ok": False, "error": str(e)}


async def _handle_get_node_context(params: dict) -> dict:
    """查询节点上下文"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    node_id = params.get("node_id", "")
    include_ancestors = params.get("include_ancestors", True)
    include_descendants = params.get("include_descendants", True)
    include_relations = params.get("include_relations", True)
    max_depth = params.get("max_depth", 3)

    try:
        node = kn_svc.get_node(user_id, node_id)
        if not node:
            return {"ok": False, "error": "节点不存在"}

        result = {
            "node": {"id": node.id, "label": node.label, "level": node.level, "brief": node.brief},
        }

        if include_ancestors:
            ancestors = kn_svc.get_ancestors(user_id, node_id, max_depth)
            result["ancestors"] = [
                {"id": n.id, "label": n.label, "level": n.level}
                for n in ancestors
            ]

        if include_descendants:
            descendants = kn_svc.get_descendants(user_id, node_id, max_depth)
            result["descendants"] = [
                {"id": n.id, "label": n.label, "level": n.level}
                for n in descendants
            ]

        if include_relations:
            relations = kn_svc.get_relations(user_id, node_id)
            result["relations"] = [
                {"id": r.id, "from": r.from_node_id, "to": r.to_node_id, "type": r.relation_type}
                for r in relations
            ]

        return {"ok": True, "context": result}
    except Exception as e:
        logger.exception("knowledge_get_node_context 失败")
        return {"ok": False, "error": str(e)}


async def _handle_search_nodes(params: dict) -> dict:
    """搜索节点"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    query = params.get("query", "")
    scope_node_id = params.get("scope_node_id", "")
    max_results = params.get("max_results", 10)

    try:
        all_nodes = kn_svc.list_nodes(user_id)

        # 如果在限定范围内
        if scope_node_id:
            scope_ids = set()
            scope_ids.add(scope_node_id)
            descs = kn_svc.get_descendants(user_id, scope_node_id, 10)
            scope_ids.update(n.id for n in descs)
            candidates = [n for n in all_nodes if n.id in scope_ids]
        else:
            candidates = all_nodes

        # 模糊搜索
        query_lower = query.lower()
        matched = []
        for n in candidates:
            if query_lower in (n.label or "").lower() or query_lower in (n.brief or "").lower():
                matched.append({
                    "id": n.id, "label": n.label, "level": n.level,
                    "brief": n.brief, "emoji": n.emoji,
                })
                if len(matched) >= max_results:
                    break

        return {"ok": True, "query": query, "results": matched, "total": len(matched)}
    except Exception as e:
        logger.exception("knowledge_search_nodes 失败")
        return {"ok": False, "error": str(e)}


async def _handle_recommend(params: dict) -> dict:
    """获取学习推荐"""
    from app.services.knowledge_tree.knowledge_node_service import kn_svc
    user_id = params.get("user_id", "")
    node_id = params.get("node_id", "")
    rec_type = params.get("recommend_type", "expand")

    try:
        node = kn_svc.get_node(user_id, node_id)
        if not node:
            return {"ok": False, "error": "节点不存在"}

        if rec_type == "expand":
            children = kn_svc.get_children(user_id, node_id)
            if not children:
                return {"ok": True, "recommendation": {
                    "type": "expand",
                    "message": f"「{node.label}」没有子节点，建议 AI 展开",
                    "action": "ai_expand",
                }}
            return {"ok": True, "recommendation": {
                "type": "expand",
                "message": f"「{node.label}」有 {len(children)} 个子节点",
                "children": [{"id": c.id, "label": c.label} for c in children[:5]],
            }}

        elif rec_type == "deep_dive":
            return {"ok": True, "recommendation": {
                "type": "deep_dive",
                "message": f"建议深入学习「{node.label}」",
                "node_id": node_id,
                "node_label": node.label,
            }}

        elif rec_type == "related":
            relations = kn_svc.get_relations(user_id, node_id)
            return {"ok": True, "recommendation": {
                "type": "related",
                "message": f"「{node.label}」有 {len(relations)} 个关联节点",
                "relations": [{"id": r.id, "type": r.relation_type} for r in relations[:5]],
            }}

        return {"ok": True, "recommendation": {"type": rec_type}}
    except Exception as e:
        logger.exception("knowledge_recommend 失败")
        return {"ok": False, "error": str(e)}


# 处理器映射（pipeline 的 ToolExecutor 使用）
TOOL_HANDLERS: dict[str, callable] = {
    "knowledge_add_node": _handle_add_node,
    "knowledge_edit_node": _handle_edit_node,
    "knowledge_expand_node": _handle_expand_node,
    "knowledge_delete_node": _handle_delete_node,
    "knowledge_add_relation": _handle_add_relation,
    "knowledge_get_node_context": _handle_get_node_context,
    "knowledge_search_nodes": _handle_search_nodes,
    "knowledge_recommend": _handle_recommend,
}