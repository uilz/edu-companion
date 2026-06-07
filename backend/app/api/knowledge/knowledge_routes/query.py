"""知识图谱 — 查询域：分区列表 / 推荐 / 图谱获取"""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    _load, _get_graph, _get_tree_structure,
)
from app.services.common.storage import storage

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# GET /partitions — 分区列表
# ═══════════════════════════════════════════════════════════

@router.get("/partitions")
async def list_partitions():
    data = _load()
    partitions = []
    for pid, p in data.partitions.items():
        g = data.knowledge_graphs.get(pid)
        partitions.append({
            "id": pid, "name": p.name, "subject": p.subject, "emoji": p.emoji,
            "has_graph": g is not None,
            "node_count": len(g.nodes) if g else 0,
            "edge_count": len(g.edges) if g else 0,
        })
    return {"ok": True, "partitions": partitions}


# ═══════════════════════════════════════════════════════════
# GET /recommendation — 知识树 ↔ 对话系统推荐
# (必须在 /{partition_id} 之前注册，避免 "recommendation" 被当作 partition_id)
# ═══════════════════════════════════════════════════════════

@router.get("/recommendation")
async def get_recommendation(partition_id: str | None = None, source: str = "tree"):
    """
    source=tree: 知识树探索完毕后推荐去对话系统
    source=conversation: 对话系统产生新节点后推荐去知识树
    """
    data = _load()

    if source == "tree":
        if not partition_id:
            return {"ok": True, "recommendations": []}

        graph = data.knowledge_graphs.get(partition_id)
        if not graph or not graph.nodes:
            return {"ok": True, "recommendations": [{
                "type": "generate_tree",
                "message": "该分区还没有知识树，请先生成知识树",
                "action": "generate",
                "partition_id": partition_id,
            }]}

        leaf_nodes = []
        child_ids = set(e.from_id for e in graph.edges)
        for nid in graph.nodes:
            if nid not in child_ids:
                leaf_nodes.append(nid)

        explored = 0
        unexplored = []
        for nid in leaf_nodes:
            node = graph.nodes[nid]
            conv_ids = getattr(node, "conversation_ids", None) or []
            if conv_ids:
                explored += 1
            else:
                unexplored.append({"id": nid, "label": node.label})

        recommendations = []
        if explored == len(leaf_nodes) and len(leaf_nodes) > 0:
            recommendations.append({
                "type": "tree_complete",
                "message": "知识树已探索完毕！建议去对话系统深入学习",
                "action": "go_conversation",
                "partition_id": partition_id,
            })
        elif unexplored:
            recommendations.append({
                "type": "unexplored_nodes",
                "message": f"还有 {len(unexplored)} 个节点未探索",
                "action": "explore",
                "unexplored": unexplored[:5],
            })

        return {"ok": True, "recommendations": recommendations}

    elif source == "conversation":
        recommendations = []
        for pid, graph in data.knowledge_graphs.items():
            if not graph.nodes:
                continue
            nodes_without_conv = []
            for nid, node in graph.nodes.items():
                conv_ids = getattr(node, "conversation_ids", None) or []
                if not conv_ids:
                    nodes_without_conv.append({"id": nid, "label": node.label})

            if nodes_without_conv:
                if pid not in data.partitions:
                    continue  # 分区已删除，知识图谱残留，跳过
                pname = data.partitions[pid].name
                recommendations.append({
                    "type": "pending_nodes",
                    "message": f"分区「{pname}」有 {len(nodes_without_conv)} 个节点待整理",
                    "action": "go_tree", "partition_id": pid,
                    "nodes": nodes_without_conv[:5],
                })

        return {"ok": True, "recommendations": recommendations[:3]}

    return {"ok": True, "recommendations": []}


# ═══════════════════════════════════════════════════════════
# GET /{partition_id} — 获取知识树
# ═══════════════════════════════════════════════════════════

@router.get("/{partition_id}")
async def get_graph(partition_id: str):
    result = _get_tree_structure(partition_id)
    return {"ok": True, **result}
