"""
知识图谱 API — 唯一真相源

架构:
  UserData.knowledge_graphs[partition_id]  ← 唯一真相源
    ├─ KGNode (核心字段)        ← 节点定义
    ├─ KGEdge (核心字段)        ← 关系定义
    ├─ conversation_ids (附属)  ← 关联的对话会话
    ├─ mastery (附属)           ← BKT 实时计算(非持久化)
    └─ CognitiveNode (附属)     ← 同步到认知存储

API 路由: /api/knowledge/graph
"""
from __future__ import annotations

import json as _json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from shared.constants import DEFAULT_USER_ID
from app.domain.auth.dependencies import current_user_id
from app.schemas.conversation import KnowledgeGraph, KGNode, KGEdge
from app.services.common.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge/graph", tags=["知识图谱"])


# ═══════════════════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════════════════

class NodeCreate(BaseModel):
    label: str
    description: str = ""
    priority: int = 5
    tags: list[str] = Field(default_factory=list)
    parent_node_id: str | None = None  # 可选父节点

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
# 辅助函数
# ═══════════════════════════════════════════════════════════

def _load(user_id: str = DEFAULT_USER_ID):
    return storage.load(user_id)

def _save(data, user_id: str = DEFAULT_USER_ID):
    storage.save(user_id, data)

def _get_graph(partition_id: str, user_id: str = DEFAULT_USER_ID):
    """获取知识图谱（只读，不创建）"""
    data = _load(user_id)
    return data.knowledge_graphs.get(partition_id)


def _ensure_graph(partition_id: str, user_id: str = DEFAULT_USER_ID):
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

def _get_tree_structure(partition_id: str) -> dict:
    """获取完整树形结构"""
    graph = _get_graph(partition_id)
    if not graph:
        return {"nodes": [], "edges": [], "partition_name": "", "partition_id": partition_id, "linked_conversations": {}}

    data = _load()
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

def _sync_graph_to_cognitive(partition_id: str):
    """图谱节点 → CognitiveNode 同步（附属）"""
    try:
        from app.cognitive.storage import upsert_node, get_node
        from app.cognitive.models import CognitiveNode, MetaInfo

        data = _load()
        graph = data.knowledge_graphs.get(partition_id)
        if not graph:
            return
        for nid, node in graph.nodes.items():
            existing = get_node(nid, USER_ID)
            if existing:
                # 更新 label 和 meta（如果已有）
                if existing.label != node.label:
                    existing.label = node.label
                    upsert_node(existing, USER_ID)
                continue
            cog = CognitiveNode(
                id=nid, label=node.label, level="concept",
                parent=partition_id, path_id=f"{partition_id}.{nid[:8]}",
                node_type="auto_generated", is_visible=True,
                meta=MetaInfo(created_at=time.time()),
            )
            upsert_node(cog, USER_ID)
    except Exception:
        logger.debug("认知图谱同步跳过", exc_info=True)


def _delete_cognitive_node(node_id: str):
    """删除 CognitiveNode（附属清理）"""
    try:
        from app.cognitive.storage import delete_node
        delete_node(node_id, USER_ID)
    except Exception:
        logger.debug("认知节点删除跳过", exc_info=True)


# ═══════════════════════════════════════════════════════════
# 核心逻辑：AI 生成知识图谱
# ═══════════════════════════════════════════════════════════

async def generate_graph_logic(
    partition_id: str,
    data: Any = None,
    branch_name: str = "",
    depth: int = 3,
) -> dict:
    """AI 生成/更新知识图谱。可由 API 或异步 hook 调用。"""
    if data is None:
        data = _load()

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
        from app.services.llm.llm_service import llm_service

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
        _save(data)

        if not partition.domain_tags:
            partition.domain_tags = [partition.subject or partition.name]
            _save(data)

        _sync_graph_to_cognitive(partition_id)

        return {"ok": True, "total_nodes": len(nodes_dict), "total_edges": len(edges), "version": graph.version}

    except Exception as e:
        logger.error(f"AI 生成知识图谱失败: {e}")
        return {"ok": False, "error": str(e)}


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
                pname = data.partitions[pid].name if pid in data.partitions else pid
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


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/generate — AI 生成
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/generate")
async def generate_graph(partition_id: str, depth: int = 3):
    data = _load()
    if partition_id not in data.partitions:
        raise HTTPException(status_code=404, detail="分区不存在")
    result = await generate_graph_logic(partition_id=partition_id, data=data, depth=depth)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "生成失败"))
    return result


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/node — 添加节点
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/node")
async def add_node(partition_id: str, body: NodeCreate):
    data = _load()
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
    _save(data)
    _sync_graph_to_cognitive(partition_id)
    return {"ok": True, "node_id": node.id, "node": node.model_dump(mode="json")}


# ═══════════════════════════════════════════════════════════
# PATCH /{partition_id}/node/{node_id} — 编辑节点
# ═══════════════════════════════════════════════════════════

@router.patch("/{partition_id}/node/{node_id}")
async def update_node(partition_id: str, node_id: str, body: NodePatch):
    data = _load()
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
    _save(data)
    _sync_graph_to_cognitive(partition_id)
    return {"ok": True, "node": node.model_dump(mode="json")}


# ═══════════════════════════════════════════════════════════
# DELETE /{partition_id}/node/{node_id} — 删除节点
# ═══════════════════════════════════════════════════════════

@router.delete("/{partition_id}/node/{node_id}")
async def delete_node(partition_id: str, node_id: str):
    data = _load()
    graph = data.knowledge_graphs.get(partition_id)
    if not graph or node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    del graph.nodes[node_id]
    graph.edges = [e for e in graph.edges if e.from_id != node_id and e.to_id != node_id]
    graph.updated_at = time.time()
    graph.version += 1
    _save(data)
    _delete_cognitive_node(node_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/edge — 添加边
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/edge")
async def add_edge(partition_id: str, body: EdgeCreateReq):
    data = _load()
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
    _save(data)
    return {"ok": True, "edge_id": edge.id}


# ═══════════════════════════════════════════════════════════
# DELETE /{partition_id}/edge/{edge_id} — 删除边
# ═══════════════════════════════════════════════════════════

@router.delete("/{partition_id}/edge/{edge_id}")
async def delete_edge(partition_id: str, edge_id: str):
    data = _load()
    graph = data.knowledge_graphs.get(partition_id)
    if not graph:
        raise HTTPException(status_code=404, detail="图谱不存在")

    orig_len = len(graph.edges)
    graph.edges = [e for e in graph.edges if e.id != edge_id]
    if len(graph.edges) == orig_len:
        raise HTTPException(status_code=404, detail="边不存在")

    graph.updated_at = time.time()
    graph.version += 1
    _save(data)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/ai-expand — AI 扩充节点
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/ai-expand")
async def ai_expand_nodes(partition_id: str, body: AiExpandRequest):
    graph = _get_graph(partition_id)
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
        data = _load()
        data.knowledge_graphs[partition_id] = graph
        _save(data)
        _sync_graph_to_cognitive(partition_id)

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
async def ai_edit_node(partition_id: str, body: AiEditRequest):
    graph = _get_graph(partition_id)
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
        data = _load()
        data.knowledge_graphs[partition_id] = graph
        _save(data)
        _sync_graph_to_cognitive(partition_id)

        return {"ok": True, "node": node.model_dump(mode="json")}

    except Exception as e:
        logger.error(f"AI 编辑节点失败: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/link-conversation — 关联会话到节点
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/link-conversation")
async def link_conversation(partition_id: str, body: LinkConversationRequest):
    graph = _get_graph(partition_id)
    if not graph or body.node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    data = _load()
    if body.conversation_id not in data.conversations:
        raise HTTPException(status_code=404, detail="会话不存在")

    node = graph.nodes[body.node_id]
    conv_ids = list(getattr(node, "conversation_ids", None) or [])
    if body.conversation_id not in conv_ids:
        conv_ids.append(body.conversation_id)
    node.conversation_ids = conv_ids

    graph.updated_at = time.time()
    graph.version += 1
    data.knowledge_graphs[partition_id] = graph
    _save(data)
    return {"ok": True, "conversation_ids": conv_ids}


# ═══════════════════════════════════════════════════════════
# DELETE /{partition_id}/link-conversation/{node_id}/{conversation_id} — 取消关联
# ═══════════════════════════════════════════════════════════

@router.delete("/{partition_id}/link-conversation/{node_id}/{conversation_id}")
async def unlink_conversation(partition_id: str, node_id: str, conversation_id: str):
    graph = _get_graph(partition_id)
    if not graph or node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    node = graph.nodes[node_id]
    conv_ids = list(getattr(node, "conversation_ids", None) or [])
    if conversation_id in conv_ids:
        conv_ids.remove(conversation_id)
    node.conversation_ids = conv_ids

    graph.updated_at = time.time()
    graph.version += 1
    data = _load()
    data.knowledge_graphs[partition_id] = graph
    _save(data)
    return {"ok": True, "conversation_ids": conv_ids}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/ai-chat — AI 对话帮助编辑知识树
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/ai-chat")
async def ai_chat(partition_id: str, body: AiChatRequest):
    """与 AI 对话，帮助编辑/操作知识树。会话存储在学习空间对话系统中。"""
    from app.services.knowledge.tree_ops import tree_ops

    graph = _get_graph(partition_id)
    if not graph:
        raise HTTPException(status_code=404, detail="分区不存在")

    data = _load()
    partition = data.partitions.get(partition_id)

    conversation_id = body.conversation_id
    if not conversation_id:
        if body.node_id in graph.nodes:
            node = graph.nodes[body.node_id]
            conv_ids = getattr(node, "conversation_ids", None) or []
            if conv_ids:
                conversation_id = conv_ids[0]

        if not conversation_id:
            domain_ids = [d.id for d in data.domains.values() if d.partition_id == partition_id]
            topic_ids = [t.id for t in data.topics.values() if t.domain_id in domain_ids]
            if not topic_ids:
                raise HTTPException(status_code=400, detail="该分区下没有专题，请先在对话系统中创建专题")

            conversation = tree_ops.create_conversation(
                USER_ID, topic_ids[0],
                f"知识树: {graph.nodes[body.node_id].label if body.node_id in graph.nodes else '新节点'}",
            )
            conversation_id = conversation.id

            if body.node_id in graph.nodes:
                node = graph.nodes[body.node_id]
                node.conversation_ids = [conversation_id]
                data.knowledge_graphs[partition_id] = graph
                _save(data)

    nodes_context = _json.dumps({
        nid: {"label": n.label, "description": n.description} for nid, n in graph.nodes.items()
    }, ensure_ascii=False)

    target_node_info = ""
    if body.node_id in graph.nodes:
        n = graph.nodes[body.node_id]
        target_node_info = f"\n当前操作节点: {n.label} - {n.description or '无描述'}"

    try:
        from app.services.llm.llm_service import llm_service

        system_prompt = f"""你是知识树编辑助手。用户正在构建知识树，你需要帮助用户编辑、扩充、整理知识树。

知识树信息:
- 分区: {partition.name if partition else '未知'}
- 所有节点: {nodes_context}
{target_node_info}

你可以执行以下操作:
1. 建议添加新节点（给出节点名称和描述）
2. 建议编辑现有节点
3. 建议节点间的依赖关系
4. 分析知识树的结构完整性

请在回复中给出具体建议，如果需要操作节点，请用以下格式:
[ACTION:add_node] 节点名: 描述
[ACTION:edit_node:node_id] 修改: 新的描述
[ACTION:add_edge] from_node_id -> to_node_id

如果用户意图创建不在当前知识树下的节点（其他学科/领域），请提醒用户切换到对应分区的会话。"""

        response = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": body.message},
            ],
            temperature=0.7, max_tokens=4096,
        )

        tree_ops.add_message(
            USER_ID, partition_id, "user",
            [{"type": "text", "content": body.message}],
            text_summary=body.message[:100],
            conversation_id=conversation_id,
        )
        tree_ops.add_message(
            USER_ID, partition_id, "assistant",
            [{"type": "text", "content": response}],
            text_summary=response[:100],
            conversation_id=conversation_id,
        )

        return {"ok": True, "response": response, "conversation_id": conversation_id, "node_id": body.node_id}

    except Exception as e:
        logger.error(f"AI 对话失败: {e}")
        return {"ok": False, "error": str(e)}