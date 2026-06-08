"""
Phase 8 API 端点

前缀：/api/v2
功能：分类、图谱管理、会话关联、节点操作

依赖 app.cognitive.storage / app.services.classifier_service / app.cognitive.growth_engine
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.constants import DEFAULT_USER_ID
from app.cognitive.growth_engine import growth_engine
from app.cognitive.models import CognitiveNode
from app.cognitive import get_repo
from app.cognitive.edge_storage import (
    get_edges_for_node, update_edge_status, delete_edge,
)
from app.cognitive.link_storage import (
    get_links_for_conversation, upsert_link, set_primary_link, remove_link,
    count_links_for_conversation,
)
from app.services.conversation.message_repository import update_message_cognitive, get_message_conversation_id
from app.services.common.classifier_service import classifier_service
from app.services.analytics.adaptive_selector import adaptive_selector
from app.services.common import get_data_repo
from app.services.knowledge.tree_ops import TreeOpsService
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
    cog = get_repo().get_node(entity.id, user_id)
    suggested = get_repo().get_suggested_count(entity.id, user_id) if cog else 0
    children = get_repo().get_child_count(entity.id, user_id) if cog else 0
    return {
        "id": entity.id,
        "label": label,
        "level": level,
        "path_id": entity.name,
        "is_visible": True,
        "node_type": "explicit",
        "child_count": children,
        "suggested_count": suggested,
        "created_at": getattr(entity, "created_at", 0),
    }


# ═══════════════════════════════════════════════
# 分类
# ═══════════════════════════════════════════════


class ClassifyRequest(BaseModel):
    conversation_id: str = ""
    message: str = ""
    current_topic_id: str | None = None  # v6 Phase 5: 当前 topic 的 node id


@router.post("/classify")
def classify_message(req: ClassifyRequest) -> dict:
    """分类单条消息 — v6 Phase 5: 使用 embedding + 沉浸感知"""
    from shared.constants import DEFAULT_USER_ID
    user_id = DEFAULT_USER_ID
    text = req.message
    if not text:
        return {
            "mode": 3, "candidates": [], "should_switch": False,
            "immersion_depth": 0, "immersion_suppressed": False,
        }

    # 尝试计算 embedding
    query_embedding = None
    try:
        from app.services.llm.embedding_engine import compute_embedding
        query_embedding = compute_embedding(text)
    except Exception:
        logger.debug("Embedding 计算失败，降级到文本分类")

    if query_embedding:
        result = classifier_service.classify(
            user_id, query_embedding,
            current_topic_id=req.current_topic_id,
            text=text,  # 传递给对话树回退
        )
    else:
        result = classifier_service.classify_by_text(
            user_id, text,
            current_topic_id=req.current_topic_id,
        )

    return result


class CognitiveConfirmRequest(BaseModel):
    cognitive_node_ids: list[str]


@router.post("/messages/{message_id}/cognitive-confirm")
def confirm_message_cognitive(message_id: str, req: CognitiveConfirmRequest) -> dict:
    """用户确认消息的认知分类归属后回写 messages 表"""
    node_ids = req.cognitive_node_ids
    if not node_ids:
        update_message_cognitive(message_id, [])
        return {"status": "ok", "cognitive_node_ids": [], "nodes": []}

    # 解析节点名称
    nodes = []
    for nid in node_ids:
        node = get_repo().get_node(nid, DEFAULT_USER_ID)
        if node:
            nodes.append({
                "id": node.id,
                "label": node.label,
                "level": node.level,
                "path_id": node.path_id or "",
            })

    update_message_cognitive(message_id, node_ids)

    # v6 Phase 5: 沉浸深度更新 — 确认的 topic 增加沉浸计数
    try:
        topic_ids_for_immersion = [n["id"] for n in nodes if n.get("level") in ("topic", "domain", "partition")]
        for tid in topic_ids_for_immersion:
            classifier_service.increment_immersion(DEFAULT_USER_ID, tid)
    except Exception:
        logger.debug("沉浸深度更新失败", exc_info=True)

    # v6 Phase 4: 发布 message.classified 事件（同步写入 cognitive_events）
    try:
        from app.services.common.event_service import event_service
        conv_id = get_message_conversation_id(message_id)
        # 按 level 区分 topic/atom
        topic_ids = [n["id"] for n in nodes if n.get("level") in ("topic", "domain", "partition")]
        atom_ids = [n["id"] for n in nodes if n.get("level") == "atom"]
        event_service.emit_message_classified(
            user_id=DEFAULT_USER_ID,
            message_id=message_id,
            conversation_id=conv_id or "",
            topic_node_ids=topic_ids,
            atom_node_ids=atom_ids,
            mode="confirm",
        )
    except Exception:
        logger.debug("v6 事件发布失败", exc_info=True)

    return {
        "status": "ok",
        "cognitive_node_ids": node_ids,
        "nodes": nodes,
    }


# ═══════════════════════════════════════════════
# 图谱节点
# ═══════════════════════════════════════════════


@router.get("/graph/nodes")
def get_graph_nodes(
    user_id: str = DEFAULT_USER_ID,
    parent_id: str | None = None,
    level: str | None = None,
) -> list[dict]:
    """获取图谱节点 — 合并对话树实体 + 认知学习指标

    主数据源：对话树 (partitions/domains/topics)
    增强数据：cognitive_nodes（掌握度、趋势、子节点统计等）
    """
    data = get_data_repo().load(user_id)

    def _enrich(
        entity: Partition | Domain | Topic,
        level_name: str,
        parent: str | None,
    ) -> dict:
        cog = get_repo().get_node(entity.id, user_id)
        emoji = getattr(entity, "emoji", "") or (cog.emoji if cog else "")
        raw_label = getattr(entity, "name", "")
        label = f"{emoji} {raw_label}".strip() if emoji and not raw_label.startswith(emoji) else raw_label
        mastery = float(cog.belief.proficiency_mean) if cog and cog.belief else 0.0
        trend_dir = cog.trend.direction if cog and cog.trend else "stable"
        child_cnt = get_repo().get_child_count(entity.id, user_id) if cog else 0
        node_type = cog.node_type if cog else "explicit"
        path_id = cog.path_id if cog else entity.name
        brief = cog.brief if cog else ""
        return {
            "id": entity.id,
            "label": label,
            "level": level_name,
            "parent": parent,
            "is_visible": True,
            "emoji": emoji,
            "node_type": node_type,
            "mastery": mastery,
            "trend": {"direction": trend_dir},
            "child_count": child_cnt,
            "children": cog.children if cog else [],
            "path_id": path_id,
            "brief": brief,
        }

    result: list[dict] = []

    # 1. 指定层级
    if level:
        if level == "partition":
            for p in data.partitions.values():
                result.append(_enrich(p, "partition", None))
        elif level == "domain":
            for d in data.domains.values():
                pid = getattr(d, "partition_id", "")
                if pid and not getattr(data.partitions.get(pid), "is_temp", False):
                    result.append(_enrich(d, "domain", pid))
        elif level == "topic":
            for t in data.topics.values():
                did = getattr(t, "domain_id", "")
                if did:
                    d = data.domains.get(did)
                    p = data.partitions.get(getattr(d, "partition_id", "")) if d else None
                    if p and not getattr(p, "is_temp", False):
                        result.append(_enrich(t, "topic", did))
        return result

    # 2. 指定父节点
    if parent_id:
        for d in data.domains.values():
            if d.partition_id == parent_id:
                result.append(_enrich(d, "domain", d.partition_id))
        for t in data.topics.values():
            if t.domain_id == parent_id:
                result.append(_enrich(t, "topic", t.domain_id))
        return result

    # 3. 无参数 → 返回完整树（包含 temp 分区，让前端决定过滤）
    for p in data.partitions.values():
        result.append(_enrich(p, "partition", None))
    for d in data.domains.values():
        p = data.partitions.get(getattr(d, "partition_id", ""))
        if p:
            result.append(_enrich(d, "domain", d.partition_id))
    for t in data.topics.values():
        d = data.domains.get(getattr(t, "domain_id", ""))
        if d:
            result.append(_enrich(t, "topic", t.domain_id))

    return result


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
    data = get_data_repo().load(user_id)
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
    node = get_repo().get_node(node_id, user_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")
    if recursive:
        children = get_repo().get_visible_children(node_id, user_id)
        for child in children:
            remove_graph_node(child.id, recursive=True, user_id=user_id)
    get_repo().delete_node(node_id, user_id)
    return {"status": "ok", "deleted_id": node_id}


# ═══════════════════════════════════════════════
# Dashboard (Phase 12)
# ═══════════════════════════════════════════════


@router.get("/dashboard/overview", tags=["dashboard"])
def dashboard_overview(
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """学情仪表盘概览 — 掌握度 + 队列 + 趋势 + 错误 + XP"""
    from app.cognitive import get_repo

    all_nodes = get_repo().list_all_nodes(user_id)

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
# Phase 14: 创造扩展
# ═══════════════════════════════════════════════


# ── 智能创造扩展 ──


class ExpandRequest(BaseModel):
    skill_name: str
    explanation: str = ""


@router.post("/expand/knowledge", tags=["expand"])
async def expand_knowledge(req: ExpandRequest):
    """知识拓展：深入解释 + 前置 + 进阶 + 案例 + 误区 + 趣味"""
    from app.services.knowledge.knowledge_expander import knowledge_expander

    result = await knowledge_expander.expand_knowledge(req.skill_name, req.explanation)
    return result
