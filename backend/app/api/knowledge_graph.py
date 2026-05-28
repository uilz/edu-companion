"""
知识图谱 API — 仅保留 AI 生成端点
"""
from __future__ import annotations

import json as _json
import logging
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.shared.constants import DEFAULT_USER_ID
from app.schemas.conversation import KnowledgeGraph, KGNode, KGEdge

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge/graph", tags=["知识图谱"])


def _get_user_data():
    from app.services.storage import storage
    return storage.load(DEFAULT_USER_ID)


def _save_user_data(data):
    from app.services.storage import storage
    storage.save(DEFAULT_USER_ID, data)


def _classify_mastery_cognitive(proficiency: float) -> str:
    if proficiency >= 0.85:
        return "精通"
    elif proficiency >= 0.6:
        return "掌握"
    elif proficiency >= 0.3:
        return "学习中"
    return "未接触"


def _sync_graph_to_cognitive(partition_id: str):
    """图谱节点 → CognitiveNode 同步"""
    from app.cognitive.storage import upsert_node, get_node
    from app.cognitive.models import CognitiveNode, MetaInfo

    data = _get_user_data()
    graph = data.knowledge_graphs.get(partition_id)
    if not graph:
        return

    for nid, node in graph.nodes.items():
        existing = get_node(nid, DEFAULT_USER_ID)
        if existing:
            continue
        cog = CognitiveNode(
            id=nid,
            label=node.label,
            level="concept",
            parent=partition_id,
            path_id=f"{partition_id}.{nid[:8]}",
            node_type="auto_generated",
            is_visible=True,
            meta=MetaInfo(created_at=time.time()),
        )
        upsert_node(cog, DEFAULT_USER_ID)


# ═══════════════════════════════════════════════════════════
# 核心逻辑（API + 异步 hook 共用）
# ═══════════════════════════════════════════════════════════

async def generate_graph_logic(
    user_id: str = DEFAULT_USER_ID,
    partition_id: str = "",
    data: Any = None,
    branch_name: str = "",
    depth: int = 3,
) -> dict:
    """AI 生成/更新知识图谱。可由 API 或异步 hook 调用。"""
    if data is None:
        data = _get_user_data()

    partition = data.partitions.get(partition_id)
    if not partition:
        return {"ok": False, "error": "分区不存在"}

    context_parts = [f"领域: {partition.name}"]
    if partition.subject:
        context_parts.append(f"学科: {partition.subject}")
    if partition.domain_tags:
        context_parts.append(f"标签: {', '.join(partition.domain_tags)}")

    branches = [b for b in data.conversations.values() if b.partition_id == partition_id and b.name]
    if branches:
        context_parts.append(f"细化方向: {', '.join(b.name for b in branches[:5])}")
    if branch_name:
        context_parts.append(f"新分支: {branch_name}")

    existing = data.knowledge_graphs.get(partition_id)
    if existing and existing.nodes:
        context_parts.append(f"现有知识点: {', '.join(n.label for n in list(existing.nodes.values())[:20])}")

    domain_context = "\n".join(context_parts)

    try:
        from app.services.llm_service import llm_service

        system_prompt = f"""你是知识图谱生成专家。根据用户的学习领域生成结构化的知识图谱。

{domain_context}

要求:
1. 生成 {depth} 层深度的知识点，从基础到高级
2. 每个节点包含: id(label英文slug), label(中文名), description(一句话描述), priority(1-10学习优先级)
3. 边表示前置依赖: from是前置知识, to是后置知识, relation为prerequisite
4. 如果已有知识点，在此基础上增量添加新节点
5. 输出严格JSON格式，不要任何额外文字

输出格式:
{{
  "nodes": [
    {{"id": "topic_slug", "label": "中文名", "description": "一句话", "priority": 5}}
  ],
  "edges": [
    {{"from_id": "topic_a", "to_id": "topic_b", "relation": "prerequisite"}}
  ]
}}"""

        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"为'{partition.name}'生成{depth}层知识图谱"},
            ],
            temperature=0.3,
            max_tokens=16384,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = _json.loads(raw)

        nodes_dict = {}
        for n in result.get("nodes", []):
            node = KGNode(
                id=n.get("id", ""), label=n.get("label", ""),
                description=n.get("description", ""), priority=n.get("priority", 5),
                created_by="ai",
            )
            nodes_dict[node.id] = node

        edges = [KGEdge(
            from_id=e.get("from_id", ""), to_id=e.get("to_id", ""),
            relation=e.get("relation", "prerequisite"),
        ) for e in result.get("edges", [])]

        if existing:
            user_nodes = {nid: n for nid, n in existing.nodes.items() if n.created_by == "user"}
            nodes_dict.update(user_nodes)
            existing.nodes = nodes_dict
            existing.edges = edges
            existing.version += 1
            graph = existing
        else:
            graph = KnowledgeGraph(
                partition_id=partition_id, name=f"{partition.name} 知识图谱",
                nodes=nodes_dict, edges=edges, generated_by="ai",
            )

        data.knowledge_graphs[partition_id] = graph
        _save_user_data(data)

        if not partition.domain_tags:
            partition.domain_tags = [partition.subject or partition.name]
            _save_user_data(data)

        try:
            _sync_graph_to_cognitive(partition_id)
        except Exception:
            pass

        return {"ok": True, "total_nodes": len(nodes_dict), "total_edges": len(edges), "version": graph.version}

    except Exception as e:
        logger.error(f"AI 生成知识图谱失败: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/generate
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/generate")
async def generate_graph(partition_id: str, depth: int = 3):
    """AI 生成知识图谱。depth: 生成深度 1-5，默认3层。"""
    data = _get_user_data()
    if partition_id not in data.partitions:
        raise HTTPException(status_code=404, detail="分区不存在")

    result = await generate_graph_logic(partition_id=partition_id, data=data, depth=depth)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "生成失败"))
    return result
