"""
Phase 8 API 端点

前缀：/api/v2
功能：分类、图谱管理、会话关联、节点操作

依赖 app.cognitive.storage / app.services.phase8_classifier / app.cognitive.growth_engine
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from app.cognitive.growth_engine import growth_engine
from app.cognitive.models import CognitiveNode
from app.cognitive.storage import (
    find_node_by_path, get_node, get_visible_children, get_suggested_count,
    get_nodes_by_level, list_all_nodes,
    set_node_visible, upsert_node, vector_search,
)
from app.cognitive.edge_storage import (
    get_edge, get_edges_for_node, update_edge_status, delete_edge, upsert_edge,
)
from app.cognitive.link_storage import (
    get_links_for_conversation, upsert_link, set_primary_link, remove_link,
    count_links_for_conversation,
)
from app.services.phase8_classifier import phase8_classifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2")


# ═══════════════════════════════════════════════
# 分类
# ═══════════════════════════════════════════════


@router.post("/classify")
def classify_message(
    user_id: str,
    text: str,
    embedding: list[float] | None = None,
    current_topic_id: str | None = None,
) -> dict:
    """分类单条消息，返回模式 + 候选路径"""
    if not embedding:
        return {"mode": 3, "candidates": [], "should_switch": False}
    return phase8_classifier.classify(
        user_id, embedding, current_topic_id=current_topic_id,
    )


@router.post("/classify/select")
def classify_select(
    user_id: str,
    conversation_id: str,
    node_ids: list[str],
    new_session: bool = False,
) -> dict:
    """用户确认归属（支持多选 + 新会话选项）"""
    for i, nid in enumerate(node_ids):
        upsert_link(
            conversation_id=conversation_id,
            node_id=nid,
            is_primary=(i == 0),
            added_by="user_selection",
        )
        set_node_visible(nid, user_id)
    return {"status": "ok", "links_created": len(node_ids)}


@router.post("/classify/custom")
def classify_custom(
    user_id: str,
    conversation_id: str,
    path_labels: dict[str, str],
) -> dict:
    """用户自定义路径（LLM 补全 hierarchy 后创建）"""
    # path_labels 格式: {"大学物理": "partition", "电磁学": "domain", "静电场": "topic"}
    path_id = ".".join(path_labels.keys())
    # 创建 path_id，最后的节点设为 visible
    created = growth_engine.ensure_ancestors(user_id, path_id, "topic", path_labels)
    if not created:
        last_node = find_node_by_path(path_id, user_id)
        if last_node:
            created = [last_node.id]
    if created:
        last_id = created[-1]
        set_node_visible(last_id, user_id)
        upsert_link(conversation_id, last_id, is_primary=True, added_by="user_custom")
        return {"status": "ok", "node_id": last_id, "path_id": path_id}
    return {"status": "error", "message": "创建失败"}


# ═══════════════════════════════════════════════
# 临时会话
# ═══════════════════════════════════════════════


@router.put("/conversations/{conv_id}/save")
def save_temporary_conversation(
    user_id: str,
    conv_id: str,
    path_labels: dict[str, str] | None = None,
) -> dict:
    """保存临时会话为常规会话，触发 LLM hierarchy 生成"""
    from app.services.storage import storage
    data = storage.load(user_id)
    conv = data.conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv.is_temporary = False
    storage.save(user_id, data)

    if path_labels:
        path_id = ".".join(path_labels.keys())
        created = growth_engine.ensure_ancestors(
            user_id, path_id, "topic", path_labels,
        )
        if created:
            last_id = created[-1]
            set_node_visible(last_id, user_id)
            upsert_link(conv_id, last_id, is_primary=True, added_by="user_save")
            return {"status": "ok", "node_id": last_id, "path_id": path_id}

    return {"status": "ok", "temporary": False}


# ═══════════════════════════════════════════════
# 会话-节点关联
# ═══════════════════════════════════════════════


@router.get("/conversations/{conv_id}/links")
def get_conversation_links(conv_id: str) -> list[dict]:
    """获取会话的所有关联 topic"""
    return get_links_for_conversation(conv_id)


@router.post("/conversations/{conv_id}/links")
def add_conversation_link(
    conv_id: str,
    user_id: str,
    node_id: str,
    is_primary: bool = False,
) -> dict:
    """添加辅助归属"""
    result = upsert_link(conv_id, node_id, is_primary=is_primary, added_by="user_add")
    set_node_visible(node_id, user_id)
    return result


@router.patch("/conversations/{conv_id}/links/{link_id}")
def update_conversation_link(
    conv_id: str,
    link_id: str,
    is_primary: bool = False,
) -> dict:
    """修改关联（设为主归属）"""
    if is_primary:
        set_primary_link(conv_id, link_id)
    return {"status": "ok"}


@router.delete("/conversations/{conv_id}/links/{link_id}")
def delete_conversation_link(
    conv_id: str,
    link_id: str,
) -> dict:
    """移除关联（最后一条 link 将删除会话）"""
    count_before = count_links_for_conversation(conv_id)
    remove_link(link_id)
    count_after = count_links_for_conversation(conv_id)
    if count_after == 0:
        # 最后一条 link 被删除，标记会话删除
        from app.services.storage import storage
        data = storage.load_from_conv_id(conv_id)
        if data:
            conv = data.conversations.get(conv_id)
            if conv:
                conv.is_active = False
                storage.save(data.user_id, data)
        return {"status": "ok", "conversation_deleted": True}
    return {"status": "ok", "conversation_deleted": False}


# ═══════════════════════════════════════════════
# 图谱节点
# ═══════════════════════════════════════════════


@router.get("/graph/nodes")
def get_graph_nodes(
    user_id: str = "default_user",
    parent_id: str | None = None,
    level: str | None = None,
) -> list[dict]:
    """获取可见子节点（含 suggested_count）

    参数：
        parent_id: 指定父节点下钻
        level: 按层级过滤（如 topic、domain、partition）
    """
    if level:
        children = [n for n in get_nodes_by_level(level, user_id) if n.is_visible]
    elif parent_id:
        children = get_visible_children(parent_id, user_id)
    else:
        children = [n for n in get_nodes_by_level("partition", user_id) if n.is_visible]
    result = []
    for c in children:
        suggested = get_suggested_count(c.id, user_id)
        entry = {
            "id": c.id,
            "label": c.label,
            "level": c.level,
            "path_id": c.path_id,
            "is_visible": c.is_visible,
            "node_type": c.node_type,
            "suggested_count": suggested,
            "created_at": c.meta.created_at,
        }
        result.append(entry)
    return result


@router.get("/graph/search")
def graph_search(
    q: str = Query(..., min_length=1),
    user_id: str = "default_user",
) -> list[dict]:
    """全局搜索节点"""
    from app.cognitive.storage import search_nodes
    results = search_nodes(q, user_id, limit=20)
    return [{
        "id": n.id,
        "label": n.label,
        "level": n.level,
        "path_id": n.path_id,
        "is_visible": n.is_visible,
        "node_type": n.node_type,
    } for n in results]


@router.post("/graph/nodes/{node_id}/expand")
def expand_node(
    user_id: str,
    node_id: str,
    label: str,
) -> dict:
    """在节点下创建子节点"""
    parent = get_node(node_id, user_id)
    if not parent:
        raise HTTPException(404, "Parent node not found")
    level_order = ["partition", "domain", "topic", "concept", "atom"]
    try:
        idx = level_order.index(parent.level)
        child_level = level_order[idx + 1]
    except (ValueError, IndexError):
        raise HTTPException(400, "Cannot create child under atom-level node")

    new_path = f"{parent.path_id}.{label}" if parent.path_id else label
    child = CognitiveNode(
        id=str(uuid4()),
        label=label,
        path_id=new_path,
        level=child_level,
        parent=node_id,
        node_type="user_created",
        is_visible=True,
    )
    upsert_node(child, user_id)
    # 波纹关联
    growth_engine.ripple_cross_domain(user_id, child.id)
    return {"id": child.id, "label": label, "level": child_level, "path_id": new_path}


# ═══════════════════════════════════════════════
# 图谱边
# ═══════════════════════════════════════════════


@router.get("/graph/edges")
def get_graph_edges(
    node_id: str,
    user_id: str = "default_user",
) -> list[dict]:
    """获取某节点的所有边"""
    edges = get_edges_for_node(node_id, user_id)
    return [{
        "id": e.id,
        "source_node_id": e.source_node_id,
        "target_node_id": e.target_node_id,
        "edge_type": e.edge_type,
        "trust_score": e.get_current_trust(),
        "edge_status": e.edge_status,
        "strength": e.strength,
    } for e in edges]


@router.post("/graph/edges/{edge_id}/accept")
def accept_edge(edge_id: str) -> dict:
    """确认建议边 → 设为 auto_active"""
    update_edge_status(edge_id, "auto_active")
    return {"status": "ok"}


@router.post("/graph/edges/{edge_id}/reject")
def reject_edge(edge_id: str) -> dict:
    """拒绝边 → 设为 user_rejected"""
    update_edge_status(edge_id, "user_rejected")
    return {"status": "ok"}


@router.delete("/graph/edges/{edge_id}")
def remove_edge(edge_id: str) -> dict:
    """删除边"""
    delete_edge(edge_id)
    return {"status": "ok"}


# ═══════════════════════════════════════════════
# 图谱导出
# ═══════════════════════════════════════════════


@router.get("/graph/export")
def export_graph(
    user_id: str = "default_user",
) -> dict[str, Any]:
    """导出用户全量图谱"""
    nodes = list_all_nodes(user_id)
    return {
        "nodes": [{
            "id": n.id,
            "label": n.label,
            "level": n.level,
            "path_id": n.path_id,
            "parent": n.parent,
            "is_visible": n.is_visible,
            "node_type": n.node_type,
            "proficiency": n.proficiency,
        } for n in nodes],
    }
