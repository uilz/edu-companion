"""ProjectionBuilder — 从事件回放重建派生状态投影"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.cognitive.operation_registry import get_registry
from app.infrastructure.db.cognitive_edge_repository import CognitiveEdgeRepository
from app.infrastructure.db.cognitive_entity_repository import CognitiveEntityRepository
from app.infrastructure.db.cognitive_event_repository import CognitiveEventRepository
from app.infrastructure.db.cognitive_projection_repository import CognitiveProjectionRepository

logger = logging.getLogger(__name__)


class ProjectionBuilder:
    """从 practice_events / cognitive_events 重建 cognitive_node_projections。

    生产环境：事件 handler 增量更新投影；
    修复/测试环境：调用 rebuild/rebuild_node 按时间顺序消费事件表重新生成。
    """

    def __init__(
        self,
        session: Session,
        event_repo: CognitiveEventRepository | None = None,
        projection_repo: CognitiveProjectionRepository | None = None,
        entity_repo: CognitiveEntityRepository | None = None,
        edge_repo: CognitiveEdgeRepository | None = None,
    ):
        self._session = session
        self._event_repo = event_repo or CognitiveEventRepository(session)
        self._projection_repo = projection_repo or CognitiveProjectionRepository(session)
        self._entity_repo = entity_repo or CognitiveEntityRepository(session)
        self._edge_repo = edge_repo or CognitiveEdgeRepository(session)
        self._registry = get_registry()

    def rebuild(self, user_id: str) -> None:
        """重建某用户的所有节点投影。"""
        logger.info("Rebuilding projections for user=%s", user_id)
        nodes = self._entity_repo.list_all(user_id)
        for node in nodes:
            self.rebuild_node(user_id, node.id)
        logger.info("Rebuilt %d projections for user=%s", len(nodes), user_id)

    def rebuild_node(self, user_id: str, node_id: str) -> None:
        """按时间顺序消费某节点的练习事件，重新生成投影。"""
        projection = self._projection_repo.reset_projection(user_id, node_id)
        events = self._event_repo.list_practice_events_for_node(
            user_id, node_id, limit=10000
        )
        # 按时间正序
        events.sort(key=lambda e: e.timestamp)

        for event in events:
            self.apply_practice_event(event, projection)

        # 最后再执行一次衰减到当前时间
        self._decay_to_now(projection)
        self._projection_repo.upsert(projection)

    def apply_practice_event(
        self,
        event,
        projection=None,
    ) -> None:
        """将单个 PracticeEvent 增量应用到投影（生产环境调用）。"""
        from app.infrastructure.db.models.cognitive import PracticeEventORM

        if not isinstance(event, PracticeEventORM):
            raise TypeError("event must be PracticeEventORM")

        if projection is None:
            projection = self._projection_repo.get_or_create(
                event.user_id, event.node_id
            )

        proj_dict = self._projection_to_dict(projection)

        # 1. BKT
        bkt_result = self._registry.execute(
            "bkt_update",
            bkt_state=proj_dict,
            success=event.success,
            difficulty=event.difficulty,
            weight=event.weight,
            now=event.timestamp,
        )
        self._apply_result(projection, bkt_result["bkt_after"])
        proficiency = bkt_result["bkt_after"]["bkt_proficiency"]

        # 2. Activation
        # 收集邻居激活（简化： prerequisite / associate 边）
        neighbor_edges = self._edge_repo.list_for_node(
            event.user_id, event.node_id
        )
        neighbor_ids = set()
        for e in neighbor_edges:
            if e.source_id == event.node_id:
                neighbor_ids.add(e.target_id)
            else:
                neighbor_ids.add(e.source_id)
        neighbor_projs = [
            self._projection_repo.get(nid)
            for nid in neighbor_ids
            if self._projection_repo.get(nid)
        ]
        act_result = self._registry.execute(
            "activation_update",
            activation_state=proj_dict,
            event_timestamp=event.timestamp,
            neighbor_activations=[
                p.act_base_level for p in neighbor_projs
            ],
            neighbor_strengths=[
                e.strength for e in neighbor_edges
                if e.source_id in neighbor_ids or e.target_id in neighbor_ids
            ],
            now=event.timestamp,
        )
        self._apply_result(projection, act_result["activation_after"])

        # 3. Trend
        trend_result = self._registry.execute(
            "update_trend",
            trend_state=proj_dict,
            new_proficiency=proficiency,
            now=event.timestamp,
            last_practiced=event.timestamp,
        )
        self._apply_result(projection, trend_result["trend_after"])

        # 4. Metacognition
        if event.confidence_before is not None:
            meta_result = self._registry.execute(
                "update_metacognition",
                metacognition_state=proj_dict,
                confidence_before=event.confidence_before,
                success=event.success,
                now=event.timestamp,
            )
            self._apply_result(projection, meta_result["metacognition_after"])

        # 5. Engagement
        eng_result = self._registry.execute(
            "update_engagement",
            engagement_state=proj_dict,
            success=event.success,
            difficulty=event.difficulty,
            time_spent=event.time_spent,
            now=event.timestamp,
        )
        self._apply_result(projection, eng_result["engagement_after"])

        # 6. Prediction（基于 prerequisite 前序节点）
        prereq_edges = self._edge_repo.list_incoming(
            event.user_id, event.node_id, edge_type="prerequisite"
        )
        prereq_projs = [
            self._projection_repo.get(e.source_id)
            for e in prereq_edges
            if self._projection_repo.get(e.source_id)
        ]
        pred_result = self._registry.execute(
            "update_prediction",
            prediction_state=proj_dict,
            observed_proficiency=proficiency,
            predecessor_proficiencies=[p.bkt_proficiency for p in prereq_projs],
            predecessor_strengths=[e.strength for e in prereq_edges],
        )
        self._apply_result(projection, pred_result["prediction_after"])

        # 7. ErrorCluster（答错时）
        if not event.success:
            error_type = "practice_error"
            if event.error_embedding:
                error_type = f"embedding_cluster_{hash(tuple(event.error_embedding)) % 1000}"
            self._projection_repo.bump_error_cluster(
                user_id=event.user_id,
                node_id=event.node_id,
                error_type=error_type,
                occurred_at=event.timestamp,
                metadata={"last_event_id": event.id},
            )

        # 8. Scheduling
        node_meta = self._entity_repo.get(event.user_id, event.node_id)
        _, successful_reviews = self._event_repo.count_practice_events_for_node(
            event.user_id, event.node_id
        )
        sched_result = self._registry.execute(
            "update_scheduling",
            scheduling_state=proj_dict,
            proficiency=proficiency,
            stability=trend_result["trend_after"].get("trend_stability", 0.5),
            stagnation_days=trend_result["trend_after"].get("trend_stagnation_days", 0.0),
            is_core=node_meta.is_core if node_meta else False,
            goal_distance=proj_dict.get("goal_distance", -1),
            last_practiced=event.timestamp,
            successful_reviews=successful_reviews,
            now=event.timestamp,
        )
        self._apply_result(projection, sched_result["scheduling_after"])

        # 9. DeepProcessing 检查
        dp_check = self._registry.execute(
            "check_deep_processing_trigger",
            proficiency=proficiency,
            error_flag=pred_result["prediction_after"].get("pred_error_flag", False),
            stagnation_days=trend_result["trend_after"].get("trend_stagnation_days", 0.0),
            next_action_type=sched_result["scheduling_after"].get(
                "sched_next_action_type", ""
            ),
        )
        if dp_check["triggered"]:
            node = self._entity_repo.get(event.user_id, event.node_id)
            label = node.label if node else event.node_id
            task = self._registry.execute(
                "generate_deep_processing_task",
                node_label=label,
                task_type="reflection",
                reason=",".join(dp_check["reasons"]),
            )
            self._projection_repo.create_deep_processing_task(
                user_id=event.user_id,
                node_id=event.node_id,
                task_type=task["task"]["task_type"],
                prompt=task["task"]["prompt"],
            )

        # 10. Composition：同 session 内共现且熟练的原子节点尝试形成组块
        self._update_composition(event, projection)

        self._projection_repo.upsert(projection)

    def _update_composition(self, event, projection) -> None:
        """检查当前事件是否与同 session 其他原子节点形成组块。"""
        if not event.session_id:
            return

        node_meta = self._entity_repo.get(event.user_id, event.node_id)
        if node_meta is None or node_meta.level != "atom":
            return

        session_events = self._event_repo.list_practice_events_for_session(
            event.session_id
        )
        other_node_ids = {
            e.node_id
            for e in session_events
            if e.node_id != event.node_id and e.timestamp < event.timestamp
        }
        if not other_node_ids:
            return

        for other_id in other_node_ids:
            other_meta = self._entity_repo.get(event.user_id, other_id)
            if other_meta is None or other_meta.level != "atom":
                continue
            other_proj = self._projection_repo.get(other_id)
            if other_proj is None:
                continue

            # 生成稳定的 chunk_id：两个节点 ID 排序后 hash
            chunk_id = self._make_pair_chunk_id(event.node_id, other_id)
            self._projection_repo.bump_co_occurrence(
                chunk_id, event.user_id, event.node_id
            )
            self._projection_repo.bump_co_occurrence(
                chunk_id, event.user_id, other_id
            )

            members = self._projection_repo.list_composition_members(chunk_id)
            member_projs = [
                self._projection_repo.get(m.node_id)
                for m in members
                if self._projection_repo.get(m.node_id)
            ]
            if len(member_projs) < 2:
                continue

            co_occurrence_count = min(m.co_occurrence_count for m in members)
            formation = self._registry.execute(
                "check_chunk_formation",
                co_occurrence_count=co_occurrence_count,
                member_proficiencies=[p.bkt_proficiency for p in member_projs],
                member_stabilities=[p.trend_stability for p in member_projs],
            )
            status = formation["chunking_status"]
            for m in members:
                member_proj = self._projection_repo.get(m.node_id)
                if member_proj is None:
                    continue
                member_proj.comp_chunk_id = chunk_id
                member_proj.comp_chunking_status = status
                self._projection_repo.upsert(member_proj)
            if event.node_id in {m.node_id for m in members}:
                projection.comp_chunk_id = chunk_id
                projection.comp_chunking_status = status

    @staticmethod
    def _make_pair_chunk_id(a: str, b: str) -> str:
        """为两个节点生成稳定的 chunk_id。"""
        from hashlib import sha256

        key = "|".join(sorted([a, b]))
        return "chunk_" + sha256(key.encode()).hexdigest()[:16]

    def _decay_to_now(self, projection) -> None:
        """将投影状态衰减到当前时间。"""
        import time

        now = time.time()
        proj_dict = self._projection_to_dict(projection)

        bkt_result = self._registry.execute("bkt_decay", bkt_state=proj_dict, now=now)
        self._apply_result(projection, bkt_result["bkt_after"])

        act_result = self._registry.execute(
            "activation_decay", activation_state=proj_dict, now=now
        )
        self._apply_result(projection, act_result["activation_after"])

    @staticmethod
    def _projection_to_dict(projection) -> dict:
        """将 ORM 投影对象转为 dict，供 operation 使用。"""
        return {
            c.name: getattr(projection, c.name)
            for c in projection.__table__.columns
        }

    @staticmethod
    def _apply_result(projection, result: dict) -> None:
        """将 operation 返回的字段写回 ORM 投影对象。"""
        for key, value in result.items():
            if key.startswith("_"):
                continue
            if hasattr(projection, key):
                setattr(projection, key, value)
