"""知识图谱 — AI 域：生成 / 扩充 / 编辑"""
from __future__ import annotations

import json as _json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from . import (
    _load, _save, _get_graph, _sync_graph_to_cognitive,
    generate_graph_logic, AiExpandRequest, AiEditRequest,
)
from app.schemas.conversation import KGNode, KGEdge
from app.domain.auth.dependencies import current_user_id

router = APIRouter()

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/generate — AI 生成
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/generate")
async def generate_graph(partition_id: str, depth: int = 3, user_id: str = Depends(current_user_id)):
    data = _load(user_id)
    if partition_id not in data.partitions:
        raise HTTPException(status_code=404, detail="分区不存在")
    result = await generate_graph_logic(partition_id=partition_id, user_id=user_id, data=data, depth=depth)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "生成失败"))
    return result


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/ai-expand — AI 扩充节点
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/ai-expand")
async def ai_expand_nodes(partition_id: str, body: AiExpandRequest, user_id: str = Depends(current_user_id)):
    graph = _get_graph(partition_id, user_id)
    if not graph:
        raise HTTPException(status_code=404, detail="分区不存在")
    if body.node_id not in graph.nodes:
        raise HTTPException(status_code=400, detail="节点不存在")

    target_node = graph.nodes[body.node_id]
    existing_nodes = {nid: n.label for nid, n in graph.nodes.items()}

    direction_text = {
        "children": "子节点（更深入的知识点）",
        "parents": "父节点（前置知识）",
        "both": "子节点和父节点",
    }.get(body.direction, "子节点")

    try:
        from app.services.llm.llm_service import llm_service

        prompt = f"""你是知识图谱扩充专家。当前知识树中节点「{target_node.label}」需要扩充{direction_text}。

现有节点: {_json.dumps(existing_nodes, ensure_ascii=False)}
目标节点描述: {target_node.description or '无'}
生成深度: {body.depth} 层

请为新节点生成:
1. 每个节点包含: id(英文slug), label(中文名), description(一句话描述), priority(1-10)
2. 边表示依赖关系: from_id是前置知识, to_id是后置知识
3. 不要重复已有节点
4. 输出严格JSON格式

输出格式:
{{
  "nodes": [
    {{"id": "new_slug", "label": "中文名", "description": "一句话", "priority": 5}}
  ],
  "edges": [
    {{"from_id": "existing_or_new", "to_id": "existing_or_new", "relation": "prerequisite"}}
  ]
}}"""

        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"为节点「{target_node.label}」扩充{direction_text}，{body.depth}层深度"},
            ],
            temperature=0.3, max_tokens=8192,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = _json.loads(raw)

        added_nodes = []
        added_edges = []

        for n in result.get("nodes", []):
            nid = n.get("id", "")
            if nid in graph.nodes:
                continue
            node = KGNode(
                id=nid, label=n.get("label", nid),
                description=n.get("description", ""),
                priority=n.get("priority", 5), created_by="ai",
            )
            graph.nodes[node.id] = node
            added_nodes.append({"id": node.id, "label": node.label})

        for e in result.get("edges", []):
            from_id = e.get("from_id", "")
            to_id = e.get("to_id", "")
            if from_id not in graph.nodes or to_id not in graph.nodes:
                continue
            edge = KGEdge(from_id=from_id, to_id=to_id, relation=e.get("relation", "prerequisite"))
            graph.edges.append(edge)
            added_edges.append({"from_id": from_id, "to_id": to_id})

        graph.updated_at = time.time()
        graph.version += 1
        data = _load(user_id)
        data.knowledge_graphs[partition_id] = graph
        _save(data, user_id)
        _sync_graph_to_cognitive(partition_id, user_id)

        return {
            "ok": True, "added_nodes": added_nodes, "added_edges": added_edges,
            "total_nodes": len(graph.nodes), "total_edges": len(graph.edges),
        }

    except Exception as e:
        logger.error(f"AI 扩充节点失败: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/ai-edit — AI 编辑节点
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/ai-edit")
async def ai_edit_node(partition_id: str, body: AiEditRequest, user_id: str = Depends(current_user_id)):
    graph = _get_graph(partition_id, user_id)
    if not graph or body.node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    node = graph.nodes[body.node_id]

    try:
        from app.services.llm.llm_service import llm_service

        prompt = f"""你是知识图谱编辑专家。根据用户指令修改节点信息。

当前节点:
- 名称: {node.label}
- 描述: {node.description or '无'}
- 优先级: {node.priority}
- 标签: {', '.join(node.tags) if node.tags else '无'}

用户指令: {body.instruction}

请输出修改后的节点信息，严格JSON格式:
{{
  "label": "新名称（如不需要改则保持原样）",
  "description": "新描述",
  "priority": 5,
  "tags": ["标签1", "标签2"]
}}"""

        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": "你是知识图谱编辑专家，根据用户指令精确修改节点信息。只输出JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3, max_tokens=2048,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = _json.loads(raw)

        if result.get("label"):
            node.label = result["label"]
        if result.get("description"):
            node.description = result["description"]
        if result.get("priority") is not None:
            node.priority = result["priority"]
        if result.get("tags") is not None:
            node.tags = result["tags"]

        graph.updated_at = time.time()
        graph.version += 1
        data = _load(user_id)
        data.knowledge_graphs[partition_id] = graph
        _save(data, user_id)
        _sync_graph_to_cognitive(partition_id, user_id)

        return {"ok": True, "node": node.model_dump(mode="json")}

    except Exception as e:
        logger.error(f"AI 编辑节点失败: {e}")
        return {"ok": False, "error": str(e)}
