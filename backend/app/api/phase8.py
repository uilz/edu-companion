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
from pydantic import BaseModel

from app.shared.constants import DEFAULT_USER_ID
from app.cognitive.growth_engine import growth_engine
from app.cognitive.models import CognitiveNode
from app.cognitive.storage import (
    find_node_by_path, get_node, get_visible_children, get_suggested_count,
    get_nodes_by_level, list_all_nodes, delete_node,
    set_node_visible, upsert_node,
)
from app.cognitive.edge_storage import (
    get_edges_for_node, update_edge_status, delete_edge,
)
from app.cognitive.link_storage import (
    get_links_for_conversation, upsert_link, set_primary_link, remove_link,
    count_links_for_conversation,
)
from app.services.phase8_classifier import phase8_classifier
from app.services.adaptive_selector import adaptive_selector
from app.services.storage import storage
from app.services.tree_ops import TreeOpsService
from app.schemas.conversation import Partition, Domain, Topic

tree_ops = TreeOpsService()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2")

# ═══════════════════════════════════════════════
# 辅助：将 UserData 实体转为 graph node dict
# ═══════════════════════════════════════════════


def _entity_to_node(
    entity: Partition | Domain | Topic,
    level: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """将 Partition/Domain/Topic 转为 frontend graph node 格式"""
    label = (entity.emoji + " " + entity.name) if getattr(entity, "emoji", None) else entity.name
    # 从认知图谱查询对应节点的分析指标
    cog = get_node(entity.id, user_id)
    suggested = get_suggested_count(entity.id, user_id) if cog else 0
    return {
        "id": entity.id,
        "label": label,
        "level": level,
        "path_id": entity.name,
        "is_visible": True,
        "node_type": "explicit",
        "suggested_count": suggested,
        "created_at": getattr(entity, "created_at", 0),
    }


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
    count_links_for_conversation(conv_id)
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
    user_id: str = DEFAULT_USER_ID,
    parent_id: str | None = None,
    level: str | None = None,
) -> list[dict]:
    """获取可见子节点 — 唯一数据源: cognitive_nodes

    所有层级 (partition/domain/topic/concept/atom) 统一从 cognitive_nodes 读取。
    """
    def _to_dict(n: CognitiveNode) -> dict:
        return {
            "id": n.id,
            "label": n.label,
            "level": n.level,
            "path_id": n.path_id,
            "is_visible": n.is_visible,
            "node_type": n.node_type,
            "suggested_count": get_suggested_count(n.id, user_id),
            "created_at": n.meta.created_at,
        }

    # 1. 指定层级
    if level:
        children = [n for n in get_nodes_by_level(level, user_id) if n.is_visible]
        return [_to_dict(c) for c in children]

    # 2. 指定父节点
    if parent_id:
        children = get_visible_children(parent_id, user_id)
        return [_to_dict(c) for c in children]

    # 3. 无参数: 返回所有 partition
    partitions = [n for n in get_nodes_by_level("partition", user_id) if n.is_visible]
    return [_to_dict(p) for p in partitions]


@router.get("/graph/search")
def graph_search(
    q: str = Query(..., min_length=1),
    user_id: str = DEFAULT_USER_ID,
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


class CreateNodeRequest(BaseModel):
    level: str
    name: str
    parent_id: str | None = None
    emoji: str = ""
    user_id: str = DEFAULT_USER_ID


@router.post("/graph/nodes")
def create_graph_node(req: CreateNodeRequest) -> dict:
    """创建 partition/domain/topic（统一入口）

    内部调 tree_ops，自动同步到对话树 + 认知图谱
    """
    level, name = req.level, req.name
    if level not in ("partition", "domain", "topic"):
        raise HTTPException(400, f"Unsupported level: {level}")
    try:
        if level == "partition":
            entity = tree_ops.create_partition(req.user_id, name, subject=name, emoji=req.emoji)
        elif level == "domain":
            if not req.parent_id:
                raise HTTPException(400, "parent_id required for domain")
            entity = tree_ops.create_domain(req.user_id, req.parent_id, name, req.emoji)
        else:  # topic
            if not req.parent_id:
                raise HTTPException(400, "parent_id required for topic")
            entity = tree_ops.create_topic(req.user_id, req.parent_id, name, req.emoji)
        return {"node": _entity_to_node(entity, level, req.user_id), "id": entity.id}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to create {level}")
        raise HTTPException(500, "Internal server error")


class RenameNodeRequest(BaseModel):
    name: str
    user_id: str = DEFAULT_USER_ID


@router.patch("/graph/nodes/{node_id}")
def rename_graph_node(
    node_id: str,
    req: RenameNodeRequest,
) -> dict:
    """重命名 partition/domain/topic（统一入口）

    内部调 tree_ops，自动同步到认知图谱 label
    """
    data = storage.load(req.user_id)
    if node_id in data.partitions:
        entity = tree_ops.rename_partition(req.user_id, node_id, req.name)
        return {"node": _entity_to_node(entity, "partition", req.user_id)}
    elif node_id in data.domains:
        entity = tree_ops.rename_domain(req.user_id, node_id, req.name)
        return {"node": _entity_to_node(entity, "domain", req.user_id)}
    elif node_id in data.topics:
        entity = tree_ops.rename_topic(req.user_id, node_id, req.name)
        return {"node": _entity_to_node(entity, "topic", req.user_id)}
    raise HTTPException(404, f"Node {node_id} not found")


@router.delete("/graph/nodes/{node_id}")
def remove_graph_node(
    node_id: str,
    recursive: bool = False,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """删除图谱节点（统一入口）

    partition/domain/topic → 走 tree_ops（同步删对话树 + 认知图谱）
    concept/atom → 仅删认知图谱
    """
    data = storage.load(user_id)
    # 判断层级：partition > domain > topic > cognitive-only
    if node_id in data.partitions:
        tree_ops.delete_partition(user_id, node_id)
        return {"status": "ok", "deleted_id": node_id, "level": "partition"}
    elif node_id in data.domains:
        tree_ops.delete_domain(user_id, node_id)
        return {"status": "ok", "deleted_id": node_id, "level": "domain"}
    elif node_id in data.topics:
        tree_ops.delete_topic(user_id, node_id)
        return {"status": "ok", "deleted_id": node_id, "level": "topic"}

    # concept/atom → 仅认知图谱
    node = get_node(node_id, user_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")
    if recursive:
        children = get_visible_children(node_id, user_id)
        for child in children:
            remove_graph_node(child.id, recursive=True, user_id=user_id)
    delete_node(node_id, user_id)
    return {"status": "ok", "deleted_id": node_id}


# ═══════════════════════════════════════════════
# 图谱边
# ═══════════════════════════════════════════════


@router.get("/graph/edges")
def get_graph_edges(
    node_id: str,
    user_id: str = DEFAULT_USER_ID,
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
    user_id: str = DEFAULT_USER_ID,
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


# ═══════════════════════════════════════════════
# Practice Queue (Phase 10)
# ═══════════════════════════════════════════════


class QueueRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    count: int = 8
    mode: str = "balanced"
    partition_id: str | None = None


class SchedulingUpdateRequest(BaseModel):
    node_id: str
    user_id: str = DEFAULT_USER_ID
    is_correct: bool = True
    hints_used: int = 0


@router.post("/practice/queue", tags=["practice"])
def practice_queue(req: QueueRequest) -> list[dict]:
    """获取自适应练习队列"""
    results = adaptive_selector.get_queue(
        user_id=req.user_id,
        count=req.count,
        mode=req.mode,
        partition_id=req.partition_id,
    )
    return [
        {
            "node_id": r.node_id,
            "label": r.label,
            "level": r.level,
            "proficiency_mean": r.proficiency_mean,
            "urgency": r.urgency,
            "next_review": r.next_review,
            "interval_days": r.interval_days,
            "ease_factor": r.ease_factor,
            "stagnation_days": r.stagnation_days,
            "direction": r.direction,
            "action_type": r.action_type,
            "reason": r.reason,
        }
        for r in results
    ]


@router.patch("/practice/scheduling", tags=["practice"])
def update_scheduling(req: SchedulingUpdateRequest) -> dict:
    """手动更新某个知识点的间隔重复调度参数"""
    from app.cognitive.storage import get_node, upsert_node

    node = get_node(req.node_id, req.user_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    from app.services.spaced_repetition import spaced_repetition
    result = spaced_repetition.update_node_scheduling(
        node, req.is_correct, hints_used=req.hints_used,
    )
    upsert_node(node, req.user_id)

    return {
        "node_id": req.node_id,
        "label": node.label,
        **result,
        "proficiency_mean": node.belief.proficiency_mean if node.belief else 0.5,
    }


# ═══════════════════════════════════════════════
# Dashboard (Phase 12)
# ═══════════════════════════════════════════════


@router.get("/dashboard/overview", tags=["dashboard"])
def dashboard_overview(
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """学情仪表盘概览 — 掌握度 + 队列 + 趋势 + 错误 + XP"""
    from app.cognitive.storage import list_all_nodes

    all_nodes = list_all_nodes(user_id)

    # 1. 掌握度热力图
    partition_means: dict[str, float] = {}
    for n in all_nodes:
        if n.level == "partition" and n.belief:
            partition_means[n.label] = round(n.belief.proficiency_mean, 2)

    # 2. 练习队列
    results = adaptive_selector.get_queue(
        user_id, count=8,
    )
    queue = [
        {
            "node_id": r.node_id,
            "label": r.label,
            "level": r.level,
            "urgency": r.urgency,
            "proficiency_mean": r.proficiency_mean,
            "direction": r.direction,
            "stagnation_days": r.stagnation_days,
            "action_type": r.action_type,
            "reason": r.reason,
        }
        for r in results
    ]

    # 3. 趋势分类
    trends: dict[str, list[dict]] = {"improving": [], "declining": [], "stagnating": []}
    for n in all_nodes:
        if n.level not in ("atom", "concept"):
            continue
        if n.belief and n.belief.proficiency_mean >= 0.85:
            continue
        cat = n.trend.direction if n.trend and n.trend.direction in trends else "stagnating"
        trends[cat].append({
            "label": n.label,
            "proficiency_mean": round(n.belief.proficiency_mean, 2) if n.belief else 0.5,
            "stagnation_days": round(n.trend.stagnation_days, 1) if n.trend else 0,
            "direction": n.trend.direction if n.trend else "unknown",
        })

    # 4. 错误聚类
    errors = {}
    for n in all_nodes:
        for ec in n.error_clusters:
            errors[n.label] = errors.get(n.label, 0) + ec.count

    # 5. XP / Streak
    total_xp = sum(n.engagement.xp for n in all_nodes)
    max_streak = max((n.engagement.streak_current for n in all_nodes), default=0)

    import time
    today_start = time.time() - (time.time() % 86400)
    today_total = sum(
        1 for n in all_nodes
        for evt in n.practice_events
        if evt.timestamp >= today_start
    )
    today_correct = sum(
        1 for n in all_nodes
        for evt in n.practice_events
        if evt.timestamp >= today_start and evt.success
    )

    return {
        "mastery": partition_means,
        "queue": queue,
        "trends": trends,
        "errors": errors,
        "engagement": {
            "xp": total_xp,
            "streak": max_streak,
            "today_accuracy": round(today_correct / today_total, 2) if today_total > 0 else 0.0,
            "today_practiced": today_total,
        },
    }


# ═══════════════════════════════════════════════
# Explain / Multimedia 讲解 (Phase 13)
# ═══════════════════════════════════════════════


class ExplainForErrorRequest(BaseModel):
    skill_id: str = ""
    error_type: str = "conceptual"
    user_id: str = DEFAULT_USER_ID


class ExplainTTSRequest(BaseModel):
    skill_id: str = ""
    skill_name: str = ""
    explanation: str = ""
    user_id: str = DEFAULT_USER_ID


@router.post("/explain/for-error", tags=["explain"])
def explain_for_error(req: ExplainForErrorRequest) -> dict:
    """答错 → 搜索 B站/知乎/Youtube 讲解视频"""
    from app.services.media_search import media_search

    try:
        import asyncio
        results = asyncio.run(media_search.recommend_for_error(
            req.skill_id, req.error_type,
        ))
        return {"skill_id": req.skill_id, "error_type": req.error_type, "results": results}
    except Exception as e:
        logger.warning("Explain search failed: %s", e)
        return {"skill_id": req.skill_id, "error_type": req.error_type, "results": {}, "error": str(e)}


@router.post("/explain/tts", tags=["explain"])
async def explain_tts(req: ExplainTTSRequest) -> dict:
    """知识点文本 → TTS 语音讲解"""
    from infra.tts_client import EdgeTTSClient

    try:
        tts = EdgeTTSClient()
        result = await tts.synthesize_knowledge(
            skill_id=req.skill_id,
            skill_name=req.skill_name,
            explanation=req.explanation,
        )
        return {"skill_id": req.skill_id, **result}
    except Exception as e:
        logger.error("TTS explain failed: %s", e)
        return {"skill_id": req.skill_id, "error": str(e)}


@router.post("/explain/card", tags=["explain"])
def explain_card(
    skill_id: str = "",
    skill_name: str = "",
    explanation: str = "",
    formula: str = "",
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """知识点 → 结构化图文卡片"""
    label = skill_name or skill_id.split(".")[-1] if "." in skill_id else skill_id
    return {
        "skill_id": skill_id,
        "skill_name": label,
        "explanation": explanation,
        "formula": formula,
        "has_formula": bool(formula),
        "media_urls": [],
    }


# ═══════════════════════════════════════════════
# Phase 14: 心理陪伴 + 创造扩展
# ═══════════════════════════════════════════════


# ── 情绪分析 ──


class EmotionAnalyzeRequest(BaseModel):
    text: str
    user_id: str = DEFAULT_USER_ID


@router.post("/emotion/analyze", tags=["emotion"])
async def analyze_emotion(req: EmotionAnalyzeRequest):
    """分析一句话的情绪"""
    from app.services.emotion_analyzer import emotion_analyzer

    record = await emotion_analyzer.classify(req.text, req.user_id)
    return {"category": record.category, "intensity": record.intensity, "summary": record.summary}


@router.get("/emotion/trend/{user_id}", tags=["emotion"])
async def emotion_trend(user_id: str = DEFAULT_USER_ID, window_hours: int = 72):
    """情绪趋势分析"""
    from app.services.emotion_analyzer import emotion_analyzer

    trend = await emotion_analyzer.analyze_trend(user_id, window_hours=window_hours)
    return trend.to_dict()


# ── 智能创造扩展 ──


class ExpandRequest(BaseModel):
    skill_name: str
    explanation: str = ""


@router.post("/expand/knowledge", tags=["expand"])
async def expand_knowledge(req: ExpandRequest):
    """知识拓展：深入解释 + 前置 + 进阶 + 案例 + 误区 + 趣味"""
    from app.services.knowledge_expander import knowledge_expander

    result = await knowledge_expander.expand_knowledge(req.skill_name, req.explanation)
    return result


class VariantRequest(BaseModel):
    question_text: str
    correct_answer: str


@router.post("/expand/variant", tags=["expand"])
async def generate_variant(req: VariantRequest):
    """变式题生成"""
    from app.services.knowledge_expander import knowledge_expander

    result = await knowledge_expander.generate_variant(req.question_text, req.correct_answer)
    return result


class DiscoverRequest(BaseModel):
    skills: list[dict[str, str]]


@router.post("/expand/discover", tags=["expand"])
async def discover_relations(req: DiscoverRequest):
    """知识点关联发现"""
    from app.services.knowledge_expander import knowledge_expander

    discoveries = await knowledge_expander.discover_relations(req.skills)
    return {"discoveries": discoveries}


# ═══════════════════════════════════════════════
# Phase 15: 多模态输入 + 视觉理解
# ═══════════════════════════════════════════════


from fastapi import UploadFile, File as FastAPIFile


@router.post("/vision/ocr", tags=["vision"])
async def vision_ocr(file: UploadFile = FastAPIFile(...)):
    """OCR 识别图片文字"""
    from app.services.vision_service import vision_service

    data = await file.read()
    path = vision_service.save_upload(data, file.filename or "image.png")
    try:
        result = vision_service.ocr(path)
        return result
    finally:
        import os
        try:
            os.remove(path)
        except Exception:
            pass


@router.post("/vision/understand-problem", tags=["vision"])
async def vision_understand_problem(file: UploadFile = FastAPIFile(...)):
    """理解图片中的题目"""
    from app.services.vision_service import vision_service

    data = await file.read()
    path = vision_service.save_upload(data, file.filename or "image.png")
    try:
        result = vision_service.understand_problem(path)
        return result
    finally:
        import os
        try:
            os.remove(path)
        except Exception:
            pass


@router.post("/vision/analyze", tags=["vision"])
async def vision_analyze(file: UploadFile = FastAPIFile(...)):
    """通用图片分析"""
    from app.services.vision_service import vision_service

    data = await file.read()
    path = vision_service.save_upload(data, file.filename or "image.png")
    try:
        result = vision_service.analyze_image(path)
        return result
    finally:
        import os
        try:
            os.remove(path)
        except Exception:
            pass


@router.post("/vision/chat-image", tags=["vision"])
async def vision_chat_image(file: UploadFile = FastAPIFile(...)):
    """对话中发送图片 → 理解内容 + 生成回复"""
    from app.services.vision_service import vision_service

    data = await file.read()
    path = vision_service.save_upload(data, file.filename or "image.png")
    try:
        # 先理解图片
        ocr_result = vision_service.ocr(path)
        problem = vision_service.understand_problem(path)

        # 整合结果
        text = ocr_result.get("text", "")
        subject = problem.get("subject", "")
        q_type = problem.get("question_type", "")
        approach = problem.get("approach", "")
        key_points = problem.get("key_points", [])
        difficulty = problem.get("difficulty", "")

        return {
            "ocr_text": text,
            "subject": subject,
            "question_type": q_type,
            "key_points": key_points,
            "approach": approach,
            "difficulty": difficulty,
            "has_formula": ocr_result.get("has_formula", False),
        }
    finally:
        import os
        try:
            os.remove(path)
        except Exception:
            pass
