"""知识图谱 API — 子域拆分：查询/CRUD/AI/对话关联

Prefix: /api/knowledge/graph

子模块：
- query.py — 查询：分区列表、推荐、图谱获取
- crud.py — CRUD：节点/边增删改
- ai.py — AI 生成、扩充、编辑
- conv.py — 会话关联、AI 对话编辑
"""
from __future__ import annotations

import json as _json
import logging
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.conversation import KnowledgeGraph, KGNode, KGEdge
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)

# 所有子模块共享同一个 prefix
router = APIRouter(prefix="/api/knowledge/graph", tags=["知识图谱"])


# ═══════════════════════════════════════════════════════════
# 请求模型（子模块共享）
# ═══════════════════════════════════════════════════════════

class NodeCreate(BaseModel):
    label: str
    description: str = ""
    priority: int = 5
    tags: list[str] = Field(default_factory=list)
    parent_node_id: str | None = None


class NodePatch(BaseModel):
    label: str | None = None
    description: str | None = None
    priority: int | None = None
    tags: list[str] | None = None


class EdgeCreateReq(BaseModel):
    from_id: str
    to_id: str
    relation: str = "prerequisite"
    label: str = ""


class AiExpandRequest(BaseModel):
    node_id: str
    depth: int = 2
    direction: str = "children"


class AiEditRequest(BaseModel):
    node_id: str
    instruction: str


class LinkConversationRequest(BaseModel):
    node_id: str
    conversation_id: str


class AiChatRequest(BaseModel):
    node_id: str
    message: str
    conversation_id: str | None = None


# ═══════════════════════════════════════════════════════════
# 辅助函数（子模块共享）
# ═══════════════════════════════════════════════════════════

def _load(user_id: str):
    return get_data_repo().load(user_id)


def _save(data, user_id: str):
    get_data_repo().save(user_id, data)


def _get_graph(partition_id: str, user_id: str):
    """获取知识图谱（只读，不创建）"""
    data = _load(user_id)
    return data.knowledge_graphs.get(partition_id)


def _get_descendant_ids(graph, node_id: str) -> set[str]:
    """计算某节点下所有子孙节点的 ID 集合（含自身）"""
    children = {e.to_id for e in graph.edges if e.from_id == node_id}
    if not children:
        return {node_id}
    descendants = set()
    stack = list(children)
    while stack:
        nid = stack.pop()
        if nid in descendants:
            continue
        descendants.add(nid)
        for e in graph.edges:
            if e.from_id == nid and e.to_id not in descendants:
                stack.append(e.to_id)
    return descendants | {node_id}


def _find_scope_violations(
    graph, target_node_ids: list[str], bound_node_id: str,
) -> list[str]:
    """检查目标节点是否在 bound 节点的作用域内，返回违规节点列表"""
    if not bound_node_id or bound_node_id not in graph.nodes:
        return []
    scope = _get_descendant_ids(graph, bound_node_id)
    return [nid for nid in target_node_ids if nid not in scope]


def _ensure_graph(partition_id: str, user_id: str):
    """获取或创建知识图谱（写入操作时使用）"""
    data = _load(user_id)
    graph = data.knowledge_graphs.get(partition_id)
    if not graph:
        partition = data.partitions.get(partition_id)
        if not partition:
            return None
        graph = KnowledgeGraph(
            partition_id=partition_id,
            name=f"{partition.name} 知识图谱",
        )
        data.knowledge_graphs[partition_id] = graph
        _save(data, user_id)
    return graph


def _get_tree_structure(partition_id: str, user_id: str) -> dict:
    """获取完整树形结构"""
    graph = _get_graph(partition_id, user_id)
    if not graph:
        return {"nodes": [], "edges": [], "partition_name": "", "partition_id": partition_id, "linked_conversations": {}}

    data = _load(user_id)
    partition = data.partitions.get(partition_id)

    nodes = [{
        "id": nid, "label": n.label, "description": n.description,
        "priority": n.priority, "tags": n.tags, "created_by": n.created_by,
        "version": getattr(n, "version", 1),
    } for nid, n in graph.nodes.items()]

    edges = [{
        "id": e.id, "from_id": e.from_id, "to_id": e.to_id,
        "relation": e.relation, "label": e.label,
    } for e in graph.edges]

    linked = {
        nid: list(getattr(n, "conversation_ids", None) or [])
        for nid, n in graph.nodes.items()
    }

    return {
        "nodes": nodes, "edges": edges,
        "partition_name": partition.name if partition else "",
        "partition_id": partition_id, "version": graph.version,
        "linked_conversations": linked,
    }


def _sync_graph_to_cognitive(partition_id: str, user_id: str):
    """图谱节点 → CognitiveNode 同步（附属）"""
    try:
        from app.domain.cognitive import get_repo
        from app.domain.cognitive.models import CognitiveNode, MetaInfo
        from app.services.common.event_service import EventService

        data = _load(user_id)
        graph = data.knowledge_graphs.get(partition_id)
        if not graph:
            return
        for nid, node in graph.nodes.items():
            existing = get_repo().get_node(nid, user_id)
            if existing:
                if existing.label != node.label:
                    existing.label = node.label
                    get_repo().upsert_node(existing, user_id)
                continue
            cog = CognitiveNode(
                id=nid, label=node.label, level="concept",
                parent=partition_id, path_id=f"{partition_id}.{nid[:8]}",
                node_type="auto_generated", is_visible=True,
                meta=MetaInfo(created_at=time.time()),
            )
            get_repo().upsert_node(cog, user_id)
            EventService.emit_node_created(
                user_id=user_id,
                node_id=nid,
                parent_id=partition_id,
                level="concept",
                created_by="system",
            )
    except Exception:
        logger.debug("认知图谱同步跳过", exc_info=True)


def _delete_cognitive_node(node_id: str, user_id: str):
    """删除 CognitiveNode（附属清理）"""
    try:
        from app.domain.cognitive import get_repo
        get_repo().delete_node(node_id, user_id)
    except Exception:
        logger.debug("认知节点删除跳过", exc_info=True)


# ═══════════════════════════════════════════════════════════
# 核心逻辑：AI 生成知识图谱
# ═══════════════════════════════════════════════════════════

async def generate_graph_logic(
    partition_id: str,
    user_id: str,
    data: Any = None,
    branch_name: str = "",
    depth: int = 3,
) -> dict:
    """AI 生成/更新知识图谱。可由 API 或异步 hook 调用。"""
    if data is None:
        data = _load(user_id)

    partition = data.partitions.get(partition_id)
    if not partition:
        return {"ok": False, "error": "分区不存在"}

    context_parts = [f"领域: {partition.name}"]
    if partition.subject:
        context_parts.append(f"学科: {partition.subject}")
    if partition.domain_tags:
        context_parts.append(f"标签: {', '.join(partition.domain_tags)}")

    partition_domain_ids = {d.id for d in data.domains.values() if d.partition_id == partition_id}
    partition_topic_ids = {t.id for t in data.topics.values() if t.domain_id in partition_domain_ids}
    branches = [b for b in data.conversations.values() if b.topic_id in partition_topic_ids and b.name]
    if branches:
        context_parts.append(f"细化方向: {', '.join(b.name for b in branches[:5])}")
    if branch_name:
        context_parts.append(f"新分支: {branch_name}")

    existing = data.knowledge_graphs.get(partition_id)
    if existing and existing.nodes:
        context_parts.append(f"现有知识点: {', '.join(n.label for n in list(existing.nodes.values())[:20])}")

    domain_context = "\n".join(context_parts)

    try:
        from app.infrastructure.llm.llm_service import llm_service

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
        _save(data, user_id)

        if not partition.domain_tags:
            partition.domain_tags = [partition.subject or partition.name]
            _save(data, user_id)

        _sync_graph_to_cognitive(partition_id, user_id)

        return {"ok": True, "total_nodes": len(nodes_dict), "total_edges": len(edges), "version": graph.version}

    except Exception as e:
        logger.error(f"AI 生成知识图谱失败: {e}")
        return {"ok": False, "error": str(e)}


# ── 导入子路由（必须在共享定义之后）──

from .query import router as query_router
from .crud import router as crud_router
from .ai import router as ai_router
from .conv import router as conv_router

router.include_router(query_router)
router.include_router(crud_router)
router.include_router(ai_router)
router.include_router(conv_router)


__all__ = [
    "generate_graph_logic",
    "router",
]
