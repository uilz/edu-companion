"""认知事件处理器 — 基于事件溯源 + 物化投影的新架构

核心变更：
- practice_response 等事件先写入 practice_events / cognitive_events（真相源）；
- ProjectionBuilder 将事件增量应用到 cognitive_node_projections；
- 不再直接读写旧 CognitiveNode 大 JSONB 对象。

对外保持 submit_practice / submit_dialogue_context / submit_conversation_assessment
等便捷入口，但内部改为使用 SQLAlchemy Session 与新 repository。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.domain.cognitive import operations  # noqa: F401 触发 @register 注册
from app.domain.cognitive.operation_registry import get_registry
from app.infrastructure.db import (
    CognitiveEdgeRepository,
    CognitiveEntityRepository,
    CognitiveEventRepository,
    CognitiveProjectionRepository,
    ProjectionBuilder,
    get_db_session,
)
from app.infrastructure.db.models.cognitive import PracticeEventORM

logger = logging.getLogger(__name__)
_registry = get_registry()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class CognitiveEventRecord:
    """领域层事件记录，仅包含事件处理所需字段。"""

    def __init__(
        self,
        id: str = "",
        event_type: str = "",
        user_id: str = "",
        source_type: str = "",
        source_id: str = "",
        actor_type: str = "user",
        status: str = "pending",
        payload: dict | None = None,
    ):
        self.id = id
        self.event_type = event_type
        self.user_id = user_id
        self.source_type = source_type
        self.source_id = source_id
        self.actor_type = actor_type
        self.status = status
        self.payload = payload or {}


# ═══════════════════════════════════════════════════════════════
# CognitiveEventHandler
# ═══════════════════════════════════════════════════════════════


class CognitiveEventHandler:
    """新架构认知事件 handler：append-only 事件 + 增量投影更新。"""

    def __init__(self, session: Session):
        self._session = session
        self._event_repo = CognitiveEventRepository(session)
        self._projection_repo = CognitiveProjectionRepository(session)
        self._entity_repo = CognitiveEntityRepository(session)
        self._edge_repo = CognitiveEdgeRepository(session)
        self._builder = ProjectionBuilder(
            session,
            event_repo=self._event_repo,
            projection_repo=self._projection_repo,
            entity_repo=self._entity_repo,
            edge_repo=self._edge_repo,
        )

    # ── 事件处理入口 ──

    def process_event(self, event: CognitiveEventRecord) -> dict[str, Any]:
        handler = _HANDLERS.get(event.event_type)
        if handler is None:
            logger.warning("No handler for event type: %s", event.event_type)
            return {"status": "ignored", "event_type": event.event_type}
        try:
            return handler(self, event)
        except Exception as e:
            logger.error("Error processing %s: %s", event.event_type, e, exc_info=True)
            return {"status": "error", "event_type": event.event_type, "error": str(e)}

    # ── practice_response ──

    def handle_practice_response(
        self, event: CognitiveEventRecord
    ) -> dict[str, Any]:
        """处理练习事件：写入事件表并增量更新投影。"""
        now = time.time()
        payload = event.payload or {}
        user_id = event.user_id
        node_id = payload.get("node_id", "")
        success = payload.get("success", True)

        # 确保节点存在（自动创建原子节点）
        node = self._entity_repo.get(user_id, node_id)
        if node is None:
            node = self._entity_repo.upsert(
                self._make_atom_node(user_id, node_id)
            )

        # 幂等写入 practice_events
        practice_event = PracticeEventORM(
            user_id=user_id,
            node_id=node_id,
            session_id=payload.get("session_id", ""),
            question_id=payload.get("question_id", ""),
            actor_type=payload.get("actor_type", event.actor_type or "user"),
            source_type=event.source_type or payload.get("source_type", ""),
            source_id=event.source_id or payload.get("source_id", ""),
            timestamp=payload.get("timestamp", now),
            success=success,
            latency_ms=payload.get("latency_ms", 5000.0),
            weight=payload.get("weight", 1.0),
            difficulty=payload.get("difficulty"),
            guess=payload.get("guess"),
            slip=payload.get("slip"),
            confidence_before=payload.get("confidence_before"),
            confidence_after=payload.get("confidence_after"),
            hints_used=payload.get("hints_used", 0),
            time_spent=payload.get("time_spent", 0.0),
            error_embedding=payload.get("error_embedding"),
        )
        persisted = self._event_repo.append_practice_event(practice_event)

        # 增量更新投影
        self._builder.apply_practice_event(persisted)

        projection = self._projection_repo.get(node_id)
        proficiency = self._builder._belief_proficiency(projection)

        # 记录认知领域事件（用于审计与回放）
        self._event_repo.append_cognitive_event(
            user_id=user_id,
            event_type="cognitive_update",
            source_type="practice",
            source_id=persisted.id,
            node_id=node_id,
            actor_type=practice_event.actor_type,
            payload={
                "reason": f"practice_response on node {node_id}",
                "success": success,
                "proficiency_after": proficiency,
            },
        )

        return {
            "status": "ok",
            "event_type": "practice_response",
            "node_id": node_id,
            "proficiency_after": proficiency,
            "success": success,
        }

    # ── conversation_assessment ──

    def handle_conversation_assessment(
        self, event: CognitiveEventRecord
    ) -> dict[str, Any]:
        """对话评估：低权重更新 Beta 信念与趋势。"""
        now = time.time()
        payload = event.payload or {}
        user_id = event.user_id
        node_id = payload.get("node_id", "")
        assessment = payload.get("assessment", 0.5)
        success = assessment > 0.5

        node = self._entity_repo.get(user_id, node_id)
        if node is None:
            node = self._entity_repo.upsert(
                self._make_atom_node(user_id, node_id)
            )

        # 写入 practice_event（weight=0.3）
        practice_event = PracticeEventORM(
            user_id=user_id,
            node_id=node_id,
            session_id=payload.get("session_id", ""),
            actor_type=payload.get("actor_type", event.actor_type or "user"),
            source_type=event.source_type or payload.get("source_type", "conversation"),
            source_id=event.source_id or payload.get("source_id", ""),
            timestamp=payload.get("timestamp", now),
            success=success,
            weight=0.3,
        )
        persisted = self._event_repo.append_practice_event(practice_event)
        self._builder.apply_practice_event(persisted)

        projection = self._projection_repo.get(node_id)
        proficiency = self._builder._belief_proficiency(projection)

        return {
            "status": "ok",
            "event_type": "conversation_assessment",
            "node_id": node_id,
            "proficiency_after": proficiency,
            "assessment": assessment,
        }

    # ── node_created ──

    def handle_node_created(self, event: CognitiveEventRecord) -> dict[str, Any]:
        """节点创建：初始化投影。"""
        payload = event.payload or {}
        user_id = event.user_id
        node_id = payload.get("node_id", "")

        self._projection_repo.get_or_create(user_id, node_id)

        return {
            "status": "ok",
            "event_type": "node_created",
            "node_id": node_id,
        }

    # ── edge_created ──

    def handle_edge_created(self, event: CognitiveEventRecord) -> dict[str, Any]:
        """边创建：初始化边并触发目标对齐重算。"""
        payload = event.payload or {}
        user_id = event.user_id
        source_id = payload.get("source_id", "")
        target_id = payload.get("target_id", "")
        edge_type = payload.get("edge_type", "related_to")
        strength = payload.get("strength", 0.5)
        metadata = payload.get("edge_metadata", {})

        self._edge_repo.create_or_update(
            user_id=user_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            strength=strength,
            edge_metadata=metadata,
        )

        # 触发目标对齐重算：source 通过此边可达 target，双方均需重算
        self._recompute_goal_alignment(user_id, source_id)
        if target_id != source_id:
            self._recompute_goal_alignment(user_id, target_id)

        return {
            "status": "ok",
            "event_type": "edge_created",
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
        }

    # ── goal_changed ──

    def handle_goal_changed(self, event: CognitiveEventRecord) -> dict[str, Any]:
        """目标变更：重算受影响节点的目标对齐。"""
        payload = event.payload or {}
        user_id = event.user_id
        goal_node_ids = payload.get("goal_node_ids", [])

        # 简化：重算所有节点的目标对齐
        projections = self._projection_repo.list_by_user(user_id)
        for projection in projections:
            self._recompute_goal_alignment(user_id, projection.node_id, goal_node_ids)

        return {
            "status": "ok",
            "event_type": "goal_changed",
            "goals": goal_node_ids,
        }

    # ── daily_tick ──

    def handle_daily_tick(self, event: CognitiveEventRecord) -> dict[str, Any]:
        """每日心跳：Beta 信念时间衰减、Activation 衰减、scheduling 重算。"""
        now = time.time()
        user_id = event.user_id

        projections = self._projection_repo.list_by_user(user_id)
        for projection in projections:
            proj_dict = self._builder._projection_to_dict(projection)

            # Beta 信念时间衰减
            belief_result = _registry.execute(
                "belief_decay", belief_state=proj_dict, now=now
            )
            self._builder._apply_result(projection, belief_result["belief_after"])

            # Activation 衰减
            act_result = _registry.execute(
                "activation_decay", activation_state=proj_dict, now=now
            )
            self._builder._apply_result(projection, act_result["activation_after"])

            # 重算 scheduling（基于衰减后的信念）
            effective_belief = {
                "belief_alpha": projection.belief_alpha,
                "belief_beta": projection.belief_beta,
                "proficiency": self._builder._belief_proficiency(projection),
            }
            sched_result = _registry.execute(
                "update_scheduling",
                scheduling_state=proj_dict,
                belief_state=effective_belief,
                last_practiced=projection.belief_last_updated,
                stagnation_days=projection.trend_stagnation_days,
                goal_distance=projection.goal_distance,
                is_core=getattr(
                    self._entity_repo.get(user_id, projection.node_id), "is_core", False
                ),
                now=now,
            )
            self._builder._apply_result(
                projection, sched_result["scheduling_after"]
            )

        self._session.commit()

        return {
            "status": "ok",
            "event_type": "daily_tick",
            "processed_nodes": len(projections),
        }

    # ── information_gain_event ──

    def handle_information_gain_event(
        self, event: CognitiveEventRecord
    ) -> dict[str, Any]:
        """处理秘书系统评估的非练习信息增益事件。

        payload 需包含：
        - node_id: str
        - estimated_ig: float  （信息增益预估值，单位 nats）
        - confidence: float    （秘书对估计的置信度，默认 0.5）
        """
        payload = event.payload or {}
        user_id = event.user_id
        node_id = payload.get("node_id", "")
        estimated_ig = float(payload.get("estimated_ig", 0.0))
        confidence = _clamp(float(payload.get("confidence", 0.5)))

        if estimated_ig <= 0 or node_id == "":
            return {"status": "ignored", "event_type": "information_gain_event"}

        projection = self._projection_repo.get_or_create(user_id, node_id)
        proj_dict = self._builder._projection_to_dict(projection)

        alpha = max(0.1, float(proj_dict.get("belief_alpha", 1.0)))
        beta = max(0.1, float(proj_dict.get("belief_beta", 1.0)))
        total = alpha + beta

        # 将 estimated_ig 映射为等效精度增量，上限防止弱信号过度影响
        max_relative_increase = 0.1 * confidence
        relative_increase = min(max_relative_increase, max(0.0, estimated_ig) / 10.0)

        # 保持均值不变，提高精度（减少熵）
        p = alpha / total
        new_total = total * (1.0 + relative_increase)
        alpha_new = max(0.1, new_total * p)
        beta_new = max(0.1, new_total * (1.0 - p))

        total_ig = float(proj_dict.get("total_information_gain", 0.0))
        ig_contribution = estimated_ig * confidence

        self._builder._apply_result(
            projection,
            {
                "belief_alpha": round(alpha_new, 4),
                "belief_beta": round(beta_new, 4),
                "last_information_gain": round(ig_contribution, 6),
                "total_information_gain": round(total_ig + ig_contribution, 6),
            },
        )
        self._projection_repo.upsert(projection)

        return {
            "status": "ok",
            "event_type": "information_gain_event",
            "node_id": node_id,
            "alpha": round(alpha_new, 4),
            "beta": round(beta_new, 4),
            "information_gain": round(ig_contribution, 6),
        }

    # ── scheduling_adjustment ──

    def handle_scheduling_adjustment(
        self, event: CognitiveEventRecord
    ) -> dict[str, Any]:
        """处理秘书系统对复习调度的修正事件。

        payload 需包含：
        - node_id: str
        - adjustment_factor: float  （>1 延长间隔，<1 缩短间隔）
        """
        payload = event.payload or {}
        user_id = event.user_id
        node_id = payload.get("node_id", "")
        adjustment_factor = float(payload.get("adjustment_factor", 1.0))

        if node_id == "":
            return {"status": "ignored", "event_type": "scheduling_adjustment"}

        projection = self._projection_repo.get_or_create(user_id, node_id)
        proj_dict = self._builder._projection_to_dict(projection)

        sched_result = _registry.execute(
            "update_scheduling",
            scheduling_state=proj_dict,
            belief_state={
                "belief_alpha": projection.belief_alpha,
                "belief_beta": projection.belief_beta,
            },
            last_practiced=projection.belief_last_updated,
            stagnation_days=projection.trend_stagnation_days,
            goal_distance=projection.goal_distance,
            is_core=getattr(
                self._entity_repo.get(user_id, projection.node_id), "is_core", False
            ),
            adjustment_factor=adjustment_factor,
            now=time.time(),
        )
        self._builder._apply_result(projection, sched_result["scheduling_after"])
        self._projection_repo.upsert(projection)

        return {
            "status": "ok",
            "event_type": "scheduling_adjustment",
            "node_id": node_id,
            "adjustment_factor": adjustment_factor,
            "scheduling_after": sched_result["scheduling_after"],
        }

    # ── 内部辅助 ──

    def _make_atom_node(self, user_id: str, node_id: str):
        from app.infrastructure.db.models.cognitive import KnowledgeNodeORM

        return KnowledgeNodeORM(
            id=node_id,
            user_id=user_id,
            label=node_id.split(".")[-1] if "." in node_id else node_id,
            level="atom",
            node_type="auto_generated",
            is_visible=False,
        )

    def _recompute_goal_alignment(
        self,
        user_id: str,
        node_id: str,
        goal_node_ids: list[str] | None = None,
    ) -> None:
        """基于边 BFS 重算某节点到目标的对齐。"""
        if goal_node_ids is None:
            # 默认所有 level=topic 且 is_core 的节点为目标
            goals = [
                n.id
                for n in self._entity_repo.list_by_level(user_id, "topic")
                if n.is_core
            ]
        else:
            goals = goal_node_ids

        if not goals:
            return

        edges = self._edge_repo.list_all(user_id)
        edge_pairs = [(e.source_id, e.target_id) for e in edges]

        path_result = _registry.execute(
            "shortest_path_to_goals",
            start_node=node_id,
            goal_nodes=goals,
            edges=edge_pairs,
        )
        distances = path_result.get("distances", {})
        if not distances:
            return

        alignment_result = _registry.execute(
            "update_goal_alignment",
            goal_alignment_state=self._builder._projection_to_dict(
                self._projection_repo.get_or_create(user_id, node_id)
            ),
            goal_distances=distances,
        )
        self._builder._apply_result(
            self._projection_repo.get_or_create(user_id, node_id),
            alignment_result["goal_alignment_after"],
        )


# ═══════════════════════════════════════════════════════════════
# Handler 注册
# ═══════════════════════════════════════════════════════════════

_HANDLERS: dict[str, callable] = {}


def _register(event_type: str):
    def wrapper(fn):
        _HANDLERS[event_type] = fn
        return fn
    return wrapper


@_register("practice_response")
def _handle_practice_response(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_practice_response(event)


@_register("conversation_assessment")
def _handle_conversation_assessment(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_conversation_assessment(event)


@_register("node_created")
def _handle_node_created(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_node_created(event)


@_register("edge_created")
def _handle_edge_created(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_edge_created(event)


@_register("goal_changed")
def _handle_goal_changed(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_goal_changed(event)


@_register("daily_tick")
def _handle_daily_tick(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_daily_tick(event)


@_register("information_gain_event")
def _handle_information_gain_event(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_information_gain_event(event)


@_register("scheduling_adjustment")
def _handle_scheduling_adjustment(handler: CognitiveEventHandler, event: CognitiveEventRecord):
    return handler.handle_scheduling_adjustment(event)


# ═══════════════════════════════════════════════════════════════
# 便捷 API：对外保持旧入口
# ═══════════════════════════════════════════════════════════════


def submit_practice(
    user_id: str,
    node_id: str,
    success: bool,
    latency_ms: float = 5000.0,
    consecutive: bool = False,
    confidence: float = 0.5,
    confidence_before: int | None = None,
    session_id: str = "",
    question_id: str = "",
    difficulty: float | None = None,
    time_spent: float = 0.0,
) -> dict[str, Any]:
    """便捷方法：创建并处理 practice_response 事件。"""
    evt = CognitiveEventRecord(
        event_type="practice_response",
        user_id=user_id,
        source_type="practice",
        source_id="",
        payload={
            "node_id": node_id,
            "success": success,
            "latency_ms": latency_ms,
            "consecutive": consecutive,
            "confidence": confidence,
            "confidence_before": confidence_before,
            "session_id": session_id,
            "question_id": question_id,
            "difficulty": difficulty,
            "time_spent": time_spent,
        },
    )
    with get_db_session() as session:
        handler = CognitiveEventHandler(session)
        return handler.process_event(evt)


def submit_conversation_assessment(
    user_id: str,
    node_id: str,
    assessment: float = 0.5,
    session_id: str = "",
) -> dict[str, Any]:
    """便捷方法：创建并处理 conversation_assessment 事件。"""
    evt = CognitiveEventRecord(
        event_type="conversation_assessment",
        user_id=user_id,
        source_type="conversation",
        source_id="",
        payload={
            "node_id": node_id,
            "assessment": assessment,
            "session_id": session_id,
        },
    )
    with get_db_session() as session:
        handler = CognitiveEventHandler(session)
        return handler.process_event(evt)


def submit_node_created(
    user_id: str,
    node_id: str,
    label: str = "",
    level: str = "atom",
) -> dict[str, Any]:
    """便捷方法：创建节点并初始化投影。"""
    evt = CognitiveEventRecord(
        event_type="node_created",
        user_id=user_id,
        source_type="system",
        source_id="",
        payload={"node_id": node_id, "label": label, "level": level},
    )
    with get_db_session() as session:
        handler = CognitiveEventHandler(session)
        return handler.process_event(evt)


def submit_edge_created(
    user_id: str,
    source_id: str,
    target_id: str,
    edge_type: str = "related_to",
    strength: float = 0.5,
) -> dict[str, Any]:
    """便捷方法：创建边。"""
    evt = CognitiveEventRecord(
        event_type="edge_created",
        user_id=user_id,
        source_type="system",
        source_id="",
        payload={
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "strength": strength,
        },
    )
    with get_db_session() as session:
        handler = CognitiveEventHandler(session)
        return handler.process_event(evt)


def submit_daily_tick(user_id: str) -> dict[str, Any]:
    """便捷方法：触发每日心跳。"""
    evt = CognitiveEventRecord(
        event_type="daily_tick",
        user_id=user_id,
        source_type="system",
        source_id="",
        payload={},
    )
    with get_db_session() as session:
        handler = CognitiveEventHandler(session)
        return handler.process_event(evt)


# 兼容旧对话上下文入口（当前版本暂不做更新，因为对话上下文 link 表逻辑保留）
def submit_dialogue_context(
    user_id: str,
    node_id: str,
    session_id: str,
    context_type: str = "lower",
    branch_id: str = "",
    version: int = 0,
    relevance_score: float = 0.5,
    summary_text: str = "",
) -> dict[str, Any]:
    """对话上下文更新暂不经过 cognitive_events，直接返回成功（由 conversation_node_links 维护）。"""
    return {
        "status": "ok",
        "event_type": "dialogue_context_update",
        "node_id": node_id,
        "context_type": context_type,
        "relevance_score": relevance_score,
        "note": "dialogue_context is maintained by conversation_node_links",
    }
