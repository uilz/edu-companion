"""
分区级动态知识图谱 API

端点:
  GET    /{partition_id}              — 获取分区的知识图谱
  POST   /{partition_id}/generate     — AI 生成/更新图谱（异步）
  PUT    /{partition_id}/nodes        — 添加/修改/删除节点
  PUT    /{partition_id}/edges        — 添加/修改/删除边
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.conversation import KGEdge, KGNode, KnowledgeGraph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge/graph", tags=["知识图谱"])

# ── Helper: 获取 UserData ──

def _get_user_data():
    from app.services.storage import storage
    data = storage.load("default_user")
    return data

def _save_user_data(data):
    from app.services.storage import storage
    storage.save("default_user", data)


# ═══════════════════════════════════════════════════════════
# GET /{partition_id}
# ═══════════════════════════════════════════════════════════

@router.get("/{partition_id}")
async def get_graph(partition_id: str):
    """获取指定分区的知识图谱。不存在则返回空。"""
    data = _get_user_data()

    if partition_id not in data.partitions:
        raise HTTPException(status_code=404, detail="分区不存在")

    graph = data.knowledge_graphs.get(partition_id)
    if graph is None:
        return {
            "partition_id": partition_id,
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
            "generated": False,
        }

    # 同步 BKT 掌握度
    from app.core.knowledge_trace import bkt_engine
    for node_id, node in graph.nodes.items():
        try:
            state = bkt_engine.load_or_create("default_user", node_id)
            node.mastery = round(state.p_known * 100, 1)
            node.mastery_level = bkt_engine.get_mastery_level(state)
        except Exception:
            pass

    return {
        "partition_id": partition_id,
        "graph_id": graph.id,
        "name": graph.name,
        "nodes": list(graph.nodes.values()),
        "edges": graph.edges,
        "total_nodes": len(graph.nodes),
        "total_edges": len(graph.edges),
        "generated": True,
        "version": graph.version,
    }


# ═══════════════════════════════════════════════════════════
# 核心逻辑（API + 异步 hook 共用）
# ═══════════════════════════════════════════════════════════

async def generate_graph_logic(
    user_id: str = "default_user",
    partition_id: str = "",
    data: Any = None,
    branch_name: str = "",
    depth: int = 3,
) -> dict:
    """
    AI 生成/更新知识图谱。可由 API 或异步 hook 调用。
    返回 {"ok": bool, ...}
    """
    if data is None:
        data = _get_user_data()

    partition = data.partitions.get(partition_id)
    if not partition:
        return {"ok": False, "error": "分区不存在"}

    # 收集上下文
    context_parts = [f"领域: {partition.name}"]
    if partition.subject:
        context_parts.append(f"学科: {partition.subject}")
    if partition.domain_tags:
        context_parts.append(f"标签: {', '.join(partition.domain_tags)}")

    # 从分支名收集细化方向
    branches = [b for b in data.conversations.values() if b.partition_id == partition_id and b.name]
    if branches:
        branch_names = [b.name for b in branches[:5]]
        context_parts.append(f"细化方向: {', '.join(branch_names)}")
    if branch_name and branch_name not in (context_parts[-1] if context_parts else ""):
        context_parts.append(f"新分支: {branch_name}")

    existing = data.knowledge_graphs.get(partition_id)
    if existing and existing.nodes:
        existing_labels = [n.label for n in existing.nodes.values()]
        context_parts.append(f"现有知识点: {', '.join(existing_labels[:20])}")

    domain_context = "\n".join(context_parts)
    logger.info(f"知识图谱生成: partition={partition_id}, depth={depth}, branch={branch_name}")

    try:
        from app.services.llm_service import llm_service

        system_prompt = f"""你是知识图谱生成专家。根据用户的学习领域生成结构化的知识图谱。

{domain_context}

要求:
1. 生成 {depth} 层深度的知识点，从基础到高级
2. 每个节点包含: id(label英文slug), label(中文名), description(一句话描述), priority(1-10学习优先级)
3. 边表示前置依赖: from是前置知识, to是后置知识, relation为prerequisite
4. 如果已有知识点，在此基础上增量添加新节点
5. 输出严格JSON格式，不要任何额外文字，不要```json```包裹

输出格式:
{{
  "nodes": [
    {{"id": "topic_slug", "label": "中文名", "description": "一句话", "priority": 5}},
    ...
  ],
  "edges": [
    {{"from_id": "topic_a", "to_id": "topic_b", "relation": "prerequisite"}},
    ...
  ]
}}"""

        import json as _json
        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"为'{partition.name}'生成{depth}层知识图谱"},
            ],
            temperature=0.3,
            max_tokens=16384,  # 推理模型需要更多（thinking 消耗部分）
        )

        # 清理可能的前后缀
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        try:
            result = _json.loads(raw)
        except _json.JSONDecodeError as je:
            logger.error(f"LLM 返回非JSON: {raw[:200]}")
            return {
                "ok": False,
                "error": f"AI 返回了无效JSON（模型可能推理溢出）。请重试。\n原始输出: {raw[:300]}",
            }

        nodes_dict = {}
        for n in result.get("nodes", []):
            node = KGNode(
                id=n.get("id", ""),
                label=n.get("label", ""),
                description=n.get("description", ""),
                priority=n.get("priority", 5),
                created_by="ai",
            )
            nodes_dict[node.id] = node

        edges = []
        for e in result.get("edges", []):
            edges.append(KGEdge(
                from_id=e.get("from_id", ""),
                to_id=e.get("to_id", ""),
                relation=e.get("relation", "prerequisite"),
            ))

        # 合并保留用户节点
        if existing:
            user_nodes = {nid: n for nid, n in existing.nodes.items() if n.created_by == "user"}
            nodes_dict.update(user_nodes)
            existing.nodes = nodes_dict
            existing.edges = edges
            existing.version += 1
            graph = existing
        else:
            graph = KnowledgeGraph(
                partition_id=partition_id,
                name=f"{partition.name} 知识图谱",
                nodes=nodes_dict,
                edges=edges,
                generated_by="ai",
            )

        data.knowledge_graphs[partition_id] = graph
        _save_user_data(data)

        if not partition.domain_tags:
            partition.domain_tags = [partition.subject or partition.name]
            _save_user_data(data)

        logger.info(f"知识图谱生成完成: {len(nodes_dict)}节点, {len(edges)}边")
        return {"ok": True, "total_nodes": len(nodes_dict), "total_edges": len(edges), "version": graph.version}

    except Exception as e:
        logger.error(f"AI 生成知识图谱失败: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/generate
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/generate")
async def generate_graph(partition_id: str, depth: int = 3):
    """
    AI 生成知识图谱。

    depth: 生成深度 1-5，默认3层（概念→子概念→子子概念）
    """
    data = _get_user_data()

    if partition_id not in data.partitions:
        raise HTTPException(status_code=404, detail="分区不存在")

    result = await generate_graph_logic(
        partition_id=partition_id,
        data=data,
        depth=depth,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "生成失败"))

    return result


# ═══════════════════════════════════════════════════════════
# PUT /{partition_id}/nodes
# ═══════════════════════════════════════════════════════════

@router.put("/{partition_id}/nodes")
async def update_nodes(partition_id: str, payload: dict[str, Any]):
    """
    添加/修改/删除节点。

    Body:
      action: "add" | "update" | "delete"
      node: { id?, label, description?, priority?, tags? }
    """
    data = _get_user_data()
    graph = data.knowledge_graphs.get(partition_id)
    if graph is None:
        graph = KnowledgeGraph(partition_id=partition_id, name="")
        data.knowledge_graphs[partition_id] = graph

    action = payload.get("action", "add")
    node_data = payload.get("node", {})

    if action == "add":
        node = KGNode(
            label=node_data.get("label", ""),
            description=node_data.get("description", ""),
            priority=node_data.get("priority", 5),
            created_by="user",
        )
        graph.nodes[node.id] = node
    elif action == "update":
        node_id = node_data.get("id", "")
        if node_id in graph.nodes:
            existing = graph.nodes[node_id]
            if "label" in node_data:
                existing.label = node_data["label"]
            if "description" in node_data:
                existing.description = node_data["description"]
            if "priority" in node_data:
                existing.priority = node_data["priority"]
    elif action == "delete":
        node_id = node_data.get("id", "")
        graph.nodes.pop(node_id, None)
        graph.edges = [e for e in graph.edges if e.from_id != node_id and e.to_id != node_id]

    graph.version += 1
    _save_user_data(data)

    return {
        "ok": True,
        "total_nodes": len(graph.nodes),
        "total_edges": len(graph.edges),
        "version": graph.version,
    }


# ═══════════════════════════════════════════════════════════
# PUT /{partition_id}/edges
# ═══════════════════════════════════════════════════════════

@router.put("/{partition_id}/edges")
async def update_edges(partition_id: str, payload: dict[str, Any]):
    """
    添加/删除边。

    Body:
      action: "add" | "delete"
      edge: { from_id, to_id, relation?, label? }
    """
    data = _get_user_data()
    graph = data.knowledge_graphs.get(partition_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="图谱不存在，请先生成")

    action = payload.get("action", "add")
    edge_data = payload.get("edge", {})

    if action == "add":
        edge = KGEdge(
            from_id=edge_data.get("from_id", ""),
            to_id=edge_data.get("to_id", ""),
            relation=edge_data.get("relation", "prerequisite"),
            label=edge_data.get("label", ""),
        )
        graph.edges.append(edge)
    elif action == "delete":
        from_id = edge_data.get("from_id", "")
        to_id = edge_data.get("to_id", "")
        graph.edges = [e for e in graph.edges if not (e.from_id == from_id and e.to_id == to_id)]

    graph.version += 1
    _save_user_data(data)

    return {
        "ok": True,
        "total_edges": len(graph.edges),
        "version": graph.version,
    }
