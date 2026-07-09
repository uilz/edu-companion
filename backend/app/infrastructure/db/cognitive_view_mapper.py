"""CognitiveNode 视图映射器 — 将新架构 ORM 记录组装为旧 Pydantic CognitiveNode。

该模块是 Task #7 迁移的核心适配层：业务代码继续消费 CognitiveNode DTO，但底层数据来源
切换为 knowledge_nodes + cognitive_node_projections + 事件子表。
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.domain.cognitive.models import (
    Activation,
    Associate,
    Belief,
    CognitiveLoad,
    CognitiveNode,
    Composition,
    DeepLink,
    DeepProcessing,
    Diagnostic,
    Engagement,
    ErrorCluster,
    GoalAlignment,
    Metacognition,
    PracticeEvent,
    PracticeSummary,
    Prediction,
    Prerequisite,
    Scheduling,
    Trend,
    Unlock,
)
from app.infrastructure.db.cognitive_edge_repository import CognitiveEdgeRepository
from app.infrastructure.db.cognitive_event_repository import CognitiveEventRepository
from app.infrastructure.db.cognitive_projection_repository import CognitiveProjectionRepository
from app.infrastructure.db.models.cognitive import (
    CognitiveNodeDeepProcessingORM,
    CognitiveNodeErrorClusterORM,
    CognitiveNodeProjectionORM,
    KnowledgeNodeORM,
    PracticeEventORM,
)


SECONDS_PER_DAY = 86400.0


def build_cognitive_node(
    session: Session,
    entity: KnowledgeNodeORM,
    projection: CognitiveNodeProjectionORM | None = None,
) -> CognitiveNode:
    """将 KnowledgeNodeORM + 投影/事件子表组装为 CognitiveNode 视图。"""
    if projection is None:
        projection = CognitiveProjectionRepository(session).get_or_create(
            entity.user_id, entity.id
        )

    event_repo = CognitiveEventRepository(session)
    edge_repo = CognitiveEdgeRepository(session)

    practice_events = event_repo.list_practice_events_for_node(
        entity.user_id, entity.id, limit=1000
    )

    return CognitiveNode(
        id=entity.id,
        label=entity.label,
        level=entity.level,
        parent=entity.parent_id,
        children=[c.id for c in (entity.children or []) if c.id != entity.id],
        is_core=entity.is_core,
        brief=entity.brief or "",
        prerequisites=_build_prerequisites(edge_repo, entity.user_id, entity.id),
        unlocks=_build_unlocks(edge_repo, entity.user_id, entity.id),
        associates=_build_associates(edge_repo, entity.user_id, entity.id),
        activation=_build_activation(projection),
        belief=_build_belief(projection),
        prediction=_build_prediction(projection),
        cognitive_load=_build_cognitive_load(projection),
        practice_events=_build_practice_events(practice_events),
        practice_summary=_build_practice_summary(practice_events),
        trend=_build_trend(projection, practice_events),
        error_clusters=_build_error_clusters(session, entity.user_id, entity.id),
        scheduling=_build_scheduling(projection),
        goal_alignment=_build_goal_alignment(projection),
        diagnostic=Diagnostic(),
        deep_processing=_build_deep_processing(session, entity.user_id, entity.id),
        deep_links=[],  # 当前边统一由 knowledge_edges 维护，旧 deep_links 字段留空
        dialogue_contexts=[],
        metacognition=_build_metacognition(projection),
        engagement=_build_engagement(projection),
        composition=_build_composition(projection),
        path_id=entity.path_id or "",
        node_type=entity.node_type or "explicit",
        is_visible=entity.is_visible,
        subsystems={},
        embedding=entity.embedding,
        is_active=entity.is_active,
        emoji=entity.emoji or "",
        color=entity.color or "",
        sort_order=entity.sort_order or 0,
        tags=list(entity.tags or []),
        created_by=entity.created_by or "user",
    )


def _build_prerequisites(edge_repo, user_id: str, node_id: str) -> list[Prerequisite]:
    """构建前置知识点列表（指向当前节点的 prerequisite 边）。"""
    edges = edge_repo.list_incoming(user_id, node_id, edge_type="prerequisite")
    return [
        Prerequisite(
            id=e.source_id,
            type=e.edge_metadata.get("type", "strict"),
            auto_required=e.edge_metadata.get("auto_required", False),
        )
        for e in edges
    ]


def _build_unlocks(edge_repo, user_id: str, node_id: str) -> list[Unlock]:
    """构建解锁门列表（当前节点指向他人的 unlock 边）。"""
    edges = edge_repo.list_outgoing(user_id, node_id, edge_type="unlock")
    return [
        Unlock(
            id=e.target_id,
            gate=None,
        )
        for e in edges
    ]


def _build_associates(edge_repo, user_id: str, node_id: str) -> list[Associate]:
    """构建关联知识点列表（associate / analogy 边）。"""
    edges = edge_repo.list_for_node(user_id, node_id)
    return [
        Associate(
            id=e.source_id if e.source_id != node_id else e.target_id,
            strength=e.strength,
            label=e.edge_metadata.get("label", ""),
            domain=e.edge_metadata.get("domain", ""),
            type=e.edge_metadata.get("type", "analogy"),
            plasticity=e.edge_metadata.get("plasticity", {"hebbian": 0.01, "anti_hebbian": 0.005}),
        )
        for e in edges
        if e.edge_type in ("associate", "analogy", "contrast")
    ]


def _build_activation(proj: CognitiveNodeProjectionORM) -> Activation:
    return Activation(
        base_level=proj.act_base_level,
        retrieval_prob=proj.act_retrieval_prob,
        latency_ms=proj.act_latency_ms,
        spread_from_network=proj.act_spread,
    )


def _build_belief(proj: CognitiveNodeProjectionORM) -> Belief:
    """用 Beta 投影构造兼容旧接口的 Belief。"""
    alpha = max(0.1, proj.belief_alpha)
    beta_val = max(0.1, proj.belief_beta)
    mean = alpha / (alpha + beta_val)
    precision = alpha + beta_val
    return Belief(
        alpha=round(alpha, 3),
        beta=round(beta_val, 3),
        proficiency_mean=round(mean, 4),
        proficiency_precision=round(precision, 3),
        peak_proficiency=round(mean, 4),
        last_updated=proj.belief_last_updated or time.time(),
    )


def _build_prediction(proj: CognitiveNodeProjectionORM) -> Prediction:
    return Prediction(
        top_down_mean=proj.pred_top_down_mean,
        prediction_error=proj.pred_prediction_error,
        error_flag=proj.pred_error_flag,
    )


def _build_cognitive_load(proj: CognitiveNodeProjectionORM) -> CognitiveLoad:
    return CognitiveLoad(
        intrinsic=proj.load_intrinsic,
        dynamic=proj.load_dynamic,
    )


def _build_practice_events(events: list[PracticeEventORM]) -> list[PracticeEvent]:
    return [
        PracticeEvent(
            timestamp=e.timestamp,
            success=e.success,
            latency_ms=e.latency_ms,
            weight=e.weight,
            error_embedding=None,
        )
        for e in events
    ]


def _build_practice_summary(events: list[PracticeEventORM]) -> PracticeSummary:
    total = len(events)
    correct = sum(1 for e in events if e.success)
    total_time = sum(e.latency_ms for e in events) / 1000.0
    last_ts = max((e.timestamp for e in events), default=None) if events else None

    now = time.time()
    cutoff_7d = now - 7 * SECONDS_PER_DAY
    recent_events = [e for e in events if e.timestamp >= cutoff_7d]
    recent_total = len(recent_events)
    recent_correct = sum(1 for e in recent_events if e.success)
    recent_time = sum(e.latency_ms for e in recent_events) / 1000.0

    return PracticeSummary(
        total_attempts=total,
        correct_attempts=correct,
        total_time_spent=total_time,
        recent_success_rate_7d=(recent_correct / recent_total if recent_total > 0 else 0.0),
        mean_latency_7d=(recent_time / recent_total if recent_total > 0 else 0.0),
        last_practiced=last_ts,
    )


def _build_trend(
    proj: CognitiveNodeProjectionORM, events: list[PracticeEventORM]
) -> Trend:
    """构建 Trend 视图；recent_proficiencies 取最近 20 次事件的 success 近似。"""
    recent = [1.0 if e.success else 0.0 for e in events[-20:]]
    return Trend(
        recent_proficiencies=recent,
        velocity_ewma=proj.trend_velocity,
        stagnation_days=proj.trend_stagnation_days,
        volatility_std=proj.trend_volatility,
        direction=proj.trend_direction or "plateau",
    )


def _build_error_clusters(
    session: Session, user_id: str, node_id: str
) -> list[ErrorCluster]:
    clusters = CognitiveProjectionRepository(session).list_error_clusters_for_node(
        user_id, node_id
    )
    return [
        ErrorCluster(
            cluster_id=c.id,
            count=c.frequency,
            last_seen=c.last_occurred,
            embedding=[],
        )
        for c in clusters
    ]


def _build_scheduling(proj: CognitiveNodeProjectionORM) -> Scheduling:
    return Scheduling(
        urgency=proj.sched_urgency,
        next_review=proj.sched_next_review,
        interleaving_group=proj.sched_interleaving_group or "default",
        next_action_type=proj.sched_next_action_type or "none",
    )


def _build_goal_alignment(proj: CognitiveNodeProjectionORM) -> GoalAlignment:
    return GoalAlignment(
        toward_goal="",
        distance=float(proj.goal_distance),
        on_critical_path=proj.goal_on_critical_path,
    )


def _build_metacognition(proj: CognitiveNodeProjectionORM) -> Metacognition:
    return Metacognition(
        self_assessment=proj.meta_self_assessment,
        calibration_error=proj.meta_calibration_error,
        direction=proj.meta_direction or "accurate",
    )


def _build_engagement(proj: CognitiveNodeProjectionORM) -> Engagement:
    return Engagement(
        xp=float(proj.eng_xp),
        streak_current=proj.eng_streak_current,
        streak_longest=proj.eng_streak_longest,
        effort_estimate=proj.eng_flow_score,
    )


def _build_composition(proj: CognitiveNodeProjectionORM) -> Composition:
    return Composition(
        chunk_id=proj.comp_chunk_id or None,
        chunking_status=proj.comp_chunking_status or "none",
    )


def _build_deep_processing(session: Session, user_id: str, node_id: str) -> DeepProcessing:
    tasks = CognitiveProjectionRepository(session).list_deep_processing_for_node(
        user_id, node_id
    )
    instances: list[dict[str, Any]] = []
    for t in tasks:
        instances.append(
            {
                "task_id": t.id,
                "task_type": t.task_type,
                "prompt": t.prompt,
                "status": t.status,
                "result": t.result or {},
                "created_at": t.created_at.timestamp() if t.created_at else 0.0,
                "completed_at": t.completed_at.timestamp() if t.completed_at else None,
            }
        )
    return DeepProcessing(task_instances=instances)
