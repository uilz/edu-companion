"""知识图谱 — CRUD 域：节点/边增删改"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from . import (
    _load, _save, _get_graph, _sync_graph_to_cognitive,
    _delete_cognitive_node, NodeCreate, NodePatch, EdgeCreateReq,
)
from app.schemas.conversation import KnowledgeGraph, KGNode, KGEdge
from app.domain.auth.dependencies import current_user_id

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/node — 添加节点
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/node")
async def add_node(partition_id: str, body: NodeCreate, user_id: str = Depends(current_user_id)):
    data = _load(user_id)
    if partition_id not in data.partitions:
        raise HTTPException(status_code=404, detail="分区不存在")

    graph = data.knowledge_graphs.get(partition_id)
    if not graph:
        graph = KnowledgeGraph(partition_id=partition_id, name=f"{data.partitions[partition_id].name} 知识图谱")
        data.knowledge_graphs[partition_id] = graph

    node = KGNode(
        label=body.label, description=body.description,
        priority=body.priority, tags=body.tags, created_by="user",
    )

    if body.parent_node_id and body.parent_node_id in graph.nodes:
        edge = KGEdge(from_id=body.parent_node_id, to_id=node.id, relation="prerequisite")
        graph.edges.append(edge)

    graph.nodes[node.id] = node
    graph.updated_at = time.time()
    graph.version += 1
    _save(data, user_id)
    _sync_graph_to_cognitive(partition_id, user_id)
    return {"ok": True, "node_id": node.id, "node": node.model_dump(mode="json")}


# ═══════════════════════════════════════════════════════════
# PATCH /{partition_id}/node/{node_id} — 编辑节点
# ═══════════════════════════════════════════════════════════

@router.patch("/{partition_id}/node/{node_id}")
async def update_node(partition_id: str, node_id: str, body: NodePatch, user_id: str = Depends(current_user_id)):
    data = _load(user_id)
    graph = data.knowledge_graphs.get(partition_id)
    if not graph or node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    node = graph.nodes[node_id]
    if body.label is not None:
        node.label = body.label
    if body.description is not None:
        node.description = body.description
    if body.priority is not None:
        node.priority = body.priority
    if body.tags is not None:
        node.tags = body.tags

    graph.updated_at = time.time()
    graph.version += 1
    _save(data, user_id)
    _sync_graph_to_cognitive(partition_id, user_id)
    return {"ok": True, "node": node.model_dump(mode="json")}


# ═══════════════════════════════════════════════════════════
# DELETE /{partition_id}/node/{node_id} — 删除节点
# ═══════════════════════════════════════════════════════════

@router.delete("/{partition_id}/node/{node_id}")
async def delete_node(partition_id: str, node_id: str, user_id: str = Depends(current_user_id)):
    data = _load(user_id)
    graph = data.knowledge_graphs.get(partition_id)
    if not graph or node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    del graph.nodes[node_id]
    graph.edges = [e for e in graph.edges if e.from_id != node_id and e.to_id != node_id]
    graph.updated_at = time.time()
    graph.version += 1
    _save(data, user_id)
    _delete_cognitive_node(node_id, user_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/edge — 添加边
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/edge")
async def add_edge(partition_id: str, body: EdgeCreateReq, user_id: str = Depends(current_user_id)):
    data = _load(user_id)
    graph = data.knowledge_graphs.get(partition_id)
    if not graph:
        raise HTTPException(status_code=404, detail="图谱不存在")
    if body.from_id not in graph.nodes:
        raise HTTPException(status_code=400, detail="起始节点不存在")
    if body.to_id not in graph.nodes:
        raise HTTPException(status_code=400, detail="目标节点不存在")

    edge = KGEdge(from_id=body.from_id, to_id=body.to_id, relation=body.relation, label=body.label)
    graph.edges.append(edge)
    graph.updated_at = time.time()
    graph.version += 1
    _save(data, user_id)
    return {"ok": True, "edge_id": edge.id}


# ═══════════════════════════════════════════════════════════
# DELETE /{partition_id}/edge/{edge_id} — 删除边
# ═══════════════════════════════════════════════════════════

@router.delete("/{partition_id}/edge/{edge_id}")
async def delete_edge(partition_id: str, edge_id: str, user_id: str = Depends(current_user_id)):
    data = _load(user_id)
    graph = data.knowledge_graphs.get(partition_id)
    if not graph:
        raise HTTPException(status_code=404, detail="图谱不存在")

    orig_len = len(graph.edges)
    graph.edges = [e for e in graph.edges if e.id != edge_id]
    if len(graph.edges) == orig_len:
        raise HTTPException(status_code=404, detail="边不存在")

    graph.updated_at = time.time()
    graph.version += 1
    _save(data, user_id)
    return {"ok": True}
