"""
Trees API — 知识树壳（四实体解耦架构）

统一前缀: /api/trees

职责：
- 用户知识结构创作（knowledge_trees / tree_nodes / tree_edges）
- 树节点与认知节点关联（tree_node_cognitive_links）
- 认知数据只读投影（cognitive_node_projections）
- 视图状态保存

注意：本模块不直接修改认知状态；认知状态由认知 OS 内核维护。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.domain.auth.dependencies import current_user_id
from app.infrastructure.db.database import get_db
from app.services.knowledge_tree import kt_svc, tn_svc, te_svc, cl_svc
from app.schemas.knowledge_tree import KnowledgeTree, TreeNode, TreeEdge

# 跨壳材料聚合依赖
import app.services.reading.annotations as ann_svc
from app.services.practice.practice_session import list_sessions_by_node_ids
from app.services.practice.practice_error_book import get_errors_by_node_ids
from app.services.planning.items import list_plan_items_by_node_ids
from app.api.flashcard.service import get_flashcard_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trees", tags=["知识树壳"])


# ═══════════════════════════════════════════════════════════
# 请求 / 响应模型
# ═══════════════════════════════════════════════════════════

class CreateTreeRequest(BaseModel):
    title: str = "我的知识树"
    tree_type: str = "project"
    description: str = ""


class UpdateTreeRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    tree_type: str | None = None
    root_node_id: str | None = None
    default_view_mode: str | None = None
    default_layout: str | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None


class CreateNodeRequest(BaseModel):
    label: str
    parent_id: str | None = None
    node_type: str = "concept"
    order_index: int = 0
    color: str = ""
    emoji: str = ""
    position: dict[str, Any] = Field(default_factory=dict)
    brief: str = ""
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class UpdateNodeRequest(BaseModel):
    label: str | None = None
    node_type: str | None = None
    color: str | None = None
    emoji: str | None = None
    position: dict[str, Any] | None = None
    brief: str | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None
    status: str | None = None


class AddSourceRefRequest(BaseModel):
    module: str
    id: str
    sub_id: str | None = None


class MoveNodeRequest(BaseModel):
    new_parent_id: str | None = None
    new_position: dict[str, Any] | None = None
    new_order_index: int | None = None


class ReorderChildrenRequest(BaseModel):
    children_order: list[str]


class LinkCognitiveRequest(BaseModel):
    cognitive_node_id: str
    link_role: str = "primary"


class CreateEdgeRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: str = "parent_child"
    strength: float = 1.0
    is_user_confirmed: bool = True
    is_inferred: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class ImportContentRequest(BaseModel):
    source_module: str  # flashcard / reading / conversation / practice
    source_ref_id: str
    target_node_id: str | None = None
    auto_create_node: bool = False
    label: str | None = None  # 自动创建节点时的标签


class ViewportRequest(BaseModel):
    view_mode: str | None = None
    layout: str | None = None
    zoom: float | None = None
    pan_x: float | None = None
    pan_y: float | None = None
    filters: dict[str, Any] | None = None
    collapsed_node_ids: list[str] | None = None
    focused_node_id: str | None = None


class CognitiveNodeViewResponse(BaseModel):
    cognitive_node_id: str
    label: str
    level: str
    proficiency: float
    uncertainty: float
    urgency: float
    stagnation_days: int
    next_review_at: float | None
    next_action_type: str
    display_color: str
    display_size: float
    display_glow: bool


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════


def _tree_to_dict(tree: KnowledgeTree | None) -> dict[str, Any] | None:
    if tree is None:
        return None
    return tree.model_dump(mode="json")


def _node_to_dict(node: TreeNode | None) -> dict[str, Any] | None:
    if node is None:
        return None
    data = node.model_dump(mode="json")
    # children_ids 字段兼容设计文档
    data["children_ids"] = data.get("children_order", [])
    return data


def _edge_to_dict(edge: TreeEdge | None) -> dict[str, Any] | None:
    if edge is None:
        return None
    return edge.model_dump(mode="json")


def _get_viewport(user_id: str, tree_id: str) -> dict[str, Any]:
    """从 tree.meta 读取视图状态。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        return {}
    return (tree.meta or {}).get("viewport", {})


def _save_viewport(user_id: str, tree_id: str, viewport: dict[str, Any]) -> dict[str, Any]:
    """保存视图状态到 tree.meta。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        return viewport
    meta = tree.meta or {}
    meta["viewport"] = viewport
    kt_svc.update_tree(user_id, tree_id, meta=meta)
    return viewport


def _compute_cognitive_view(cognitive_node_id: str) -> CognitiveNodeViewResponse | None:
    """从 cognitive_node_projections 构建认知节点视图。"""
    db = get_db()
    row = db.fetchone(
        """SELECT p.*, n.label, n.level
           FROM cognitive_node_projections p
           JOIN knowledge_nodes n ON n.id = p.node_id
           WHERE p.node_id = %s""",
        (cognitive_node_id,),
    )
    if not row:
        return None

    alpha = float(row.get("belief_alpha", 1.0))
    beta = float(row.get("belief_beta", 1.0))
    total = alpha + beta
    proficiency = alpha / total if total > 0 else 0.0
    # Beta 分布微分熵作为不确定性近似（使用 scipy.special.digamma，兼容 Python <3.12）
    import math
    from scipy.special import digamma
    uncertainty = 0.0
    if alpha > 0 and beta > 0 and total > 2:
        entropy = (
            math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(total)
            - (alpha - 1) * digamma(alpha)
            - (beta - 1) * digamma(beta)
            + (total - 2) * digamma(total)
        )
        max_entropy = math.log(total)
        uncertainty = max(0.0, min(1.0, entropy / max_entropy)) if max_entropy > 0 else 0.0

    urgency = float(row.get("sched_urgency", 0.0))
    next_review = row.get("sched_next_review")
    next_action = row.get("sched_next_action_type", "idle")
    stagnation_days = int(float(row.get("trend_stagnation_days", 0.0)))

    # 颜色映射：掌握度
    if proficiency < 0.30:
        display_color = "#ef4444"  # red-500
    elif proficiency < 0.55:
        display_color = "#f59e0b"  # amber-500
    elif proficiency < 0.80:
        display_color = "#84cc16"  # lime-500
    else:
        display_color = "#22c55e"  # green-500

    display_size = 1.0 + urgency * 0.5
    display_glow = uncertainty > 0.5

    return CognitiveNodeViewResponse(
        cognitive_node_id=cognitive_node_id,
        label=row.get("label", ""),
        level=row.get("level", "atom"),
        proficiency=round(proficiency, 3),
        uncertainty=round(uncertainty, 3),
        urgency=round(urgency, 3),
        stagnation_days=stagnation_days,
        next_review_at=float(next_review) if next_review else None,
        next_action_type=next_action,
        display_color=display_color,
        display_size=round(display_size, 2),
        display_glow=display_glow,
    )


# ═══════════════════════════════════════════════════════════
# Tree CRUD
# ═══════════════════════════════════════════════════════════


@router.post("")
async def create_tree(
    body: CreateTreeRequest,
    user_id: str = Depends(current_user_id),
):
    """创建知识树。"""
    tree = kt_svc.create_tree(
        user_id=user_id,
        title=body.title,
        tree_type=body.tree_type,
        description=body.description,
    )
    return {"tree": _tree_to_dict(tree)}


@router.get("")
async def list_trees(
    user_id: str = Depends(current_user_id),
    status: str | None = Query(None),
):
    """列出用户的知识树。"""
    trees = kt_svc.list_trees(user_id, status=status)
    return {"trees": [_tree_to_dict(t) for t in trees], "total": len(trees)}


@router.get("/{tree_id}")
async def get_tree(tree_id: str, user_id: str = Depends(current_user_id)):
    """获取知识树元数据。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")
    return {"tree": _tree_to_dict(tree)}


@router.patch("/{tree_id}")
async def update_tree(
    tree_id: str,
    body: UpdateTreeRequest,
    user_id: str = Depends(current_user_id),
):
    """更新知识树元数据。"""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    tree = kt_svc.update_tree(user_id, tree_id, **fields)
    if not tree:
        raise HTTPException(404, "知识树不存在")
    return {"tree": _tree_to_dict(tree)}


@router.delete("/{tree_id}")
async def delete_tree(tree_id: str, user_id: str = Depends(current_user_id)):
    """软删除知识树。"""
    ok = kt_svc.delete_tree(user_id, tree_id)
    if not ok:
        raise HTTPException(404, "知识树不存在")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# TreeNode CRUD
# ═══════════════════════════════════════════════════════════


@router.post("/{tree_id}/nodes")
async def create_node(
    tree_id: str,
    body: CreateNodeRequest,
    user_id: str = Depends(current_user_id),
):
    """在知识树下创建节点。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")

    node = tn_svc.create_node(
        user_id=user_id,
        tree_id=tree_id,
        label=body.label,
        parent_id=body.parent_id,
        node_type=body.node_type,
        order_index=body.order_index,
        color=body.color,
        emoji=body.emoji,
        position=body.position,
        brief=body.brief,
        tags=body.tags,
    )
    if tree.root_node_id is None:
        kt_svc.set_root_node(user_id, tree_id, node.id)
    return {"node": _node_to_dict(node)}


@router.get("/{tree_id}/nodes")
async def list_nodes(
    tree_id: str,
    user_id: str = Depends(current_user_id),
    include_cognitive_view: bool = Query(False),
):
    """获取知识树的所有节点。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")

    nodes = tn_svc.list_nodes(user_id, tree_id)
    node_dicts = []
    links_by_node: dict[str, list[str]] = {}
    for node in nodes:
        if include_cognitive_view:
            links = cl_svc.list_links_by_tree_node(user_id, node.id)
            cognitive_ids = [l.cognitive_node_id for l in links]
            links_by_node[node.id] = cognitive_ids

    for node in nodes:
        data = _node_to_dict(node)
        if include_cognitive_view:
            cognitive_ids = links_by_node.get(node.id, [])
            data["linked_cognitive_node_ids"] = cognitive_ids
            # 取第一个关联的认知节点作为主认知视图
            if cognitive_ids:
                data["cognitive_view"] = _compute_cognitive_view(cognitive_ids[0])
            else:
                data["cognitive_view"] = None
        node_dicts.append(data)

    return {"nodes": node_dicts, "total": len(node_dicts)}


@router.get("/{tree_id}/nodes/{node_id}")
async def get_node(
    tree_id: str,
    node_id: str,
    user_id: str = Depends(current_user_id),
    include_cognitive_view: bool = Query(False),
):
    """获取单个树节点。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    data = _node_to_dict(node)
    if include_cognitive_view:
        links = cl_svc.list_links_by_tree_node(user_id, node_id)
        cognitive_ids = [l.cognitive_node_id for l in links]
        data["linked_cognitive_node_ids"] = cognitive_ids
        data["cognitive_view"] = _compute_cognitive_view(cognitive_ids[0]) if cognitive_ids else None
    return {"node": data}


@router.patch("/{tree_id}/nodes/{node_id}")
async def update_node(
    tree_id: str,
    node_id: str,
    body: UpdateNodeRequest,
    user_id: str = Depends(current_user_id),
):
    """更新树节点。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = tn_svc.update_node(user_id, node_id, **fields)
    if not updated:
        raise HTTPException(404, "节点不存在")
    return {"node": _node_to_dict(updated)}


@router.post("/{tree_id}/nodes/{node_id}/source-refs")
async def add_source_ref(
    tree_id: str,
    node_id: str,
    body: AddSourceRefRequest,
    user_id: str = Depends(current_user_id),
):
    """为树节点追加跨壳材料 source_ref（去重）。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    try:
        updated = tn_svc.add_source_ref(user_id, node_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not updated:
        raise HTTPException(404, "节点不存在")
    return {"node": _node_to_dict(updated)}


@router.post("/{tree_id}/nodes/{node_id}/move")
async def move_node(
    tree_id: str,
    node_id: str,
    body: MoveNodeRequest,
    user_id: str = Depends(current_user_id),
):
    """移动树节点。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    moved = tn_svc.move_node(
        user_id=user_id,
        node_id=node_id,
        new_parent_id=body.new_parent_id,
        new_position=body.new_position,
        new_order_index=body.new_order_index,
    )
    if not moved:
        raise HTTPException(404, "节点不存在")
    return {"node": _node_to_dict(moved)}


@router.post("/{tree_id}/nodes/{node_id}/reorder")
async def reorder_node_children(
    tree_id: str,
    node_id: str,
    body: ReorderChildrenRequest,
    user_id: str = Depends(current_user_id),
):
    """重新排序子节点。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    ok = tn_svc.reorder_children(user_id, node_id, body.children_order)
    if not ok:
        raise HTTPException(400, "重新排序失败")
    return {"ok": True}


@router.delete("/{tree_id}/nodes/{node_id}")
async def delete_node(
    tree_id: str,
    node_id: str,
    user_id: str = Depends(current_user_id),
):
    """软删除树节点。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    ok = tn_svc.delete_node(user_id, node_id)
    return {"ok": ok}


# ═══════════════════════════════════════════════════════════
# Cognitive Link
# ═══════════════════════════════════════════════════════════


@router.post("/{tree_id}/nodes/{node_id}/link-cognitive")
async def link_cognitive_node(
    tree_id: str,
    node_id: str,
    body: LinkCognitiveRequest,
    user_id: str = Depends(current_user_id),
):
    """将树节点关联到认知节点。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    link = cl_svc.create_link(
        user_id=user_id,
        tree_id=tree_id,
        tree_node_id=node_id,
        cognitive_node_id=body.cognitive_node_id,
        link_role=body.link_role,
    )
    if not link:
        raise HTTPException(400, "关联失败（可能已存在）")
    return {"link": link.model_dump(mode="json")}


@router.delete("/{tree_id}/nodes/{node_id}/link-cognitive/{cognitive_node_id}")
async def unlink_cognitive_node(
    tree_id: str,
    node_id: str,
    cognitive_node_id: str,
    user_id: str = Depends(current_user_id),
):
    """解除树节点与认知节点的关联。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")
    ok = cl_svc.delete_link_by_nodes(user_id, node_id, cognitive_node_id)
    if not ok:
        raise HTTPException(404, "关联不存在")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# TreeEdge CRUD
# ═══════════════════════════════════════════════════════════


@router.post("/{tree_id}/edges")
async def create_edge(
    tree_id: str,
    body: CreateEdgeRequest,
    user_id: str = Depends(current_user_id),
):
    """创建知识树边。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")
    edge = te_svc.create_edge(
        user_id=user_id,
        tree_id=tree_id,
        source_node_id=body.source_node_id,
        target_node_id=body.target_node_id,
        edge_type=body.edge_type,
        strength=body.strength,
        is_user_confirmed=body.is_user_confirmed,
        is_inferred=body.is_inferred,
        meta=body.meta,
    )
    if not edge:
        raise HTTPException(400, "创建边失败（可能违反唯一约束）")
    return {"edge": _edge_to_dict(edge)}


@router.get("/{tree_id}/edges")
async def list_edges(
    tree_id: str,
    user_id: str = Depends(current_user_id),
):
    """获取知识树的所有边。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")
    edges = te_svc.list_edges(user_id, tree_id)
    return {"edges": [_edge_to_dict(e) for e in edges], "total": len(edges)}


@router.delete("/{tree_id}/edges/{edge_id}")
async def delete_edge(
    tree_id: str,
    edge_id: str,
    user_id: str = Depends(current_user_id),
):
    """删除知识树边。"""
    edge = te_svc.get_edge(user_id, edge_id)
    if not edge or edge.tree_id != tree_id:
        raise HTTPException(404, "边不存在")
    ok = te_svc.delete_edge(user_id, edge_id)
    return {"ok": ok}


# ═══════════════════════════════════════════════════════════
# 内容导入
# ═══════════════════════════════════════════════════════════


@router.post("/{tree_id}/import")
async def import_content(
    tree_id: str,
    body: ImportContentRequest,
    user_id: str = Depends(current_user_id),
):
    """从其他壳导入内容到知识树。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")

    target_node_id = body.target_node_id
    if body.auto_create_node and not target_node_id:
        label = body.label or f"来自 {body.source_module}"
        node = tn_svc.create_node(user_id, tree_id, label, node_type="material")
        target_node_id = node.id

    if not target_node_id:
        raise HTTPException(400, "需要 target_node_id 或 auto_create_node=true")

    # 发布 TreeContentImported 事件，由对应壳消费并补充 source_refs
    from app.infrastructure.event_bus_utils import publish_event_safe
    from shared.events import TreeContentImported, SourceRef
    source_ref = SourceRef(
        module=body.source_module,
        id=body.source_ref_id,
        sub_id=target_node_id,
    )
    publish_event_safe(TreeContentImported(
        user_id=user_id,
        source_module="knowledge_tree",
        tree_id=tree_id,
        target_node_id=target_node_id,
        content_source_module=body.source_module,
        source_ref_id=body.source_ref_id,
        source_ref=source_ref.__dict__,
        auto_create_node=body.auto_create_node,
    ))

    return {"ok": True, "target_node_id": target_node_id}


# ═══════════════════════════════════════════════════════════
# Viewport 视图状态
# ═══════════════════════════════════════════════════════════


@router.get("/{tree_id}/viewport")
async def get_viewport(tree_id: str, user_id: str = Depends(current_user_id)):
    """获取用户的视图状态。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")
    viewport = _get_viewport(user_id, tree_id)
    return {"viewport": viewport}


@router.put("/{tree_id}/viewport")
async def update_viewport(
    tree_id: str,
    body: ViewportRequest,
    user_id: str = Depends(current_user_id),
):
    """保存用户的视图状态。"""
    tree = kt_svc.get_tree(user_id, tree_id)
    if not tree:
        raise HTTPException(404, "知识树不存在")

    current = _get_viewport(user_id, tree_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = {**current, **updates, "updated_at": time.time()}
    _save_viewport(user_id, tree_id, updated)

    # 发布 TreeViewChanged 事件
    from app.infrastructure.event_bus_utils import publish_event_safe
    from shared.events import TreeViewChanged
    publish_event_safe(TreeViewChanged(
        user_id=user_id,
        source_module="knowledge_tree",
        tree_id=tree_id,
        view_mode=updated.get("view_mode", tree.default_view_mode),
        layout=updated.get("layout", tree.default_layout),
        filters=updated.get("filters", {}),
        zoom=updated.get("zoom", 1.0),
        pan_x=updated.get("pan_x", 0.0),
        pan_y=updated.get("pan_y", 0.0),
    ))

    return {"viewport": updated}


# ═══════════════════════════════════════════════════════════
# 节点材料聚合（简化占位 —— 后续由各壳查询接口填充）
# ═══════════════════════════════════════════════════════════


@router.get("/{tree_id}/nodes/{node_id}/materials")
async def get_node_materials(
    tree_id: str,
    node_id: str,
    user_id: str = Depends(current_user_id),
):
    """获取树节点关联的认知节点及跨壳材料聚合。"""
    node = tn_svc.get_node(user_id, node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(404, "节点不存在")

    links = cl_svc.list_links_by_tree_node(user_id, node_id)
    cognitive_ids = [l.cognitive_node_id for l in links]

    # 认知节点视图
    cognitive_views = [
        view for cid in cognitive_ids
        if (view := _compute_cognitive_view(cid)) is not None
    ]

    # 跨壳材料并发聚合（每模块上限 20 条）
    def _load_flashcards():
        svc = get_flashcard_service(event_bus=None)
        return svc.list_cards(
            user_id=user_id,
            node_ids=cognitive_ids,
            limit=20,
        ).get("cards", [])

    def _load_reading_annotations():
        return ann_svc.list_annotations(
            user_id=user_id,
            linked_node_ids=cognitive_ids,
            limit=20,
        )

    def _load_reading_notes():
        svc = get_flashcard_service(event_bus=None)
        return svc.list_cards(
            user_id=user_id,
            source="reading_note",
            node_ids=cognitive_ids,
            limit=20,
        ).get("cards", [])

    def _load_practice_sessions():
        return list_sessions_by_node_ids(user_id, cognitive_ids, limit=20)

    def _load_practice_errors():
        return get_errors_by_node_ids(user_id, cognitive_ids, limit=20)

    def _load_planning():
        return list_plan_items_by_node_ids(user_id, cognitive_ids, limit=20)

    # 使用 asyncio.gather 并发执行同步 IO（DB 查询）
    (
        flashcards,
        reading_annotations,
        reading_notes,
        practice_sessions,
        practice_errors,
        plan_items,
    ) = await asyncio.gather(
        asyncio.to_thread(_load_flashcards),
        asyncio.to_thread(_load_reading_annotations),
        asyncio.to_thread(_load_reading_notes),
        asyncio.to_thread(_load_practice_sessions),
        asyncio.to_thread(_load_practice_errors),
        asyncio.to_thread(_load_planning),
    )

    materials = {
        "cognitive_nodes": cognitive_views,
        "source_refs": node.source_refs or [],
        "flashcards": flashcards,
        "reading": {
            "annotations": reading_annotations,
            "notes": reading_notes,
        },
        "practice": {
            "sessions": practice_sessions,
            "errors": practice_errors,
        },
        "planning": plan_items,
    }
    return {"materials": materials}


# ═══════════════════════════════════════════════════════════
# 认知节点查询（用于关联搜索）
# ═══════════════════════════════════════════════════════════


@router.get("/cognitive-nodes/search")
async def search_cognitive_nodes(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(current_user_id),
):
    """搜索认知节点，用于树节点关联。"""
    db = get_db()
    rows = db.fetchall(
        """SELECT id, label, level
           FROM knowledge_nodes
           WHERE user_id = %s AND label ILIKE %s AND status != 'deleted'
           ORDER BY label
           LIMIT %s""",
        (user_id, f"%{q}%", limit),
    )
    return {
        "nodes": [
            {"cognitive_node_id": r["id"], "label": r["label"], "level": r["level"]}
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/cognitive-nodes/{cognitive_node_id}/projection")
async def get_cognitive_node_projection(
    cognitive_node_id: str,
    user_id: str = Depends(current_user_id),
):
    """获取认知节点投影详情。"""
    view = _compute_cognitive_view(cognitive_node_id)
    if not view:
        raise HTTPException(404, "认知节点不存在或无投影")
    return {"cognitive_view": view.model_dump()}
