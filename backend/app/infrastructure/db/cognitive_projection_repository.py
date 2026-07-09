"""CognitiveNodeProjection 与各子表 Repository（派生状态层）"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.db.models.cognitive import (
    CognitiveNodeCompositionMemberORM,
    CognitiveNodeDeepProcessingORM,
    CognitiveNodeErrorClusterORM,
    CognitiveNodeProjectionORM,
)


class CognitiveProjectionRepository:
    """操作派生状态投影表与子表；所有数据均可从事件回放重建。"""

    def __init__(self, session: Session):
        self._session = session

    # ═══════════════════════════════════════════════════════════════
    # 主投影
    # ═══════════════════════════════════════════════════════════════

    def get(self, node_id: str) -> Optional[CognitiveNodeProjectionORM]:
        return (
            self._session.query(CognitiveNodeProjectionORM)
            .filter_by(node_id=node_id)
            .first()
        )

    def get_or_create(
        self, user_id: str, node_id: str
    ) -> CognitiveNodeProjectionORM:
        projection = self.get(node_id)
        if projection is None:
            projection = CognitiveNodeProjectionORM(
                node_id=node_id, user_id=user_id
            )
            self._session.add(projection)
            self._session.commit()
        return projection

    def upsert(self, projection: CognitiveNodeProjectionORM) -> CognitiveNodeProjectionORM:
        existing = self.get(projection.node_id)
        if existing is None:
            self._session.add(projection)
        else:
            self._session.merge(projection)
        self._session.commit()
        return projection

    def update_fields(
        self, user_id: str, node_id: str, **fields
    ) -> Optional[CognitiveNodeProjectionORM]:
        projection = self.get_or_create(user_id, node_id)
        for key, value in fields.items():
            if hasattr(projection, key):
                setattr(projection, key, value)
        self._session.commit()
        return projection

    def list_by_user(
        self, user_id: str, limit: int = 10000
    ) -> list[CognitiveNodeProjectionORM]:
        return (
            self._session.query(CognitiveNodeProjectionORM)
            .filter_by(user_id=user_id)
            .limit(limit)
            .all()
        )

    def list_review_queue(
        self,
        user_id: str,
        limit: int = 50,
        min_urgency: float = 0.0,
    ) -> list[CognitiveNodeProjectionORM]:
        return (
            self._session.query(CognitiveNodeProjectionORM)
            .filter_by(user_id=user_id)
            .filter(CognitiveNodeProjectionORM.sched_urgency >= min_urgency)
            .order_by(CognitiveNodeProjectionORM.sched_urgency.desc())
            .limit(limit)
            .all()
        )

    def list_due_for_review(
        self,
        user_id: str,
        before_ts: float,
        limit: int = 200,
    ) -> list[CognitiveNodeProjectionORM]:
        return (
            self._session.query(CognitiveNodeProjectionORM)
            .filter_by(user_id=user_id)
            .filter(
                CognitiveNodeProjectionORM.sched_next_review > 0,
                CognitiveNodeProjectionORM.sched_next_review <= before_ts,
            )
            .order_by(CognitiveNodeProjectionORM.sched_urgency.desc())
            .limit(limit)
            .all()
        )

    def delete(self, node_id: str) -> bool:
        projection = self.get(node_id)
        if projection is None:
            return False
        self._session.delete(projection)
        self._session.commit()
        return True

    # ═══════════════════════════════════════════════════════════════
    # ErrorCluster
    # ═══════════════════════════════════════════════════════════════

    def get_error_cluster(
        self, cluster_id: str
    ) -> Optional[CognitiveNodeErrorClusterORM]:
        return (
            self._session.query(CognitiveNodeErrorClusterORM)
            .filter_by(id=cluster_id)
            .first()
        )

    def list_error_clusters_for_node(
        self, user_id: str, node_id: str
    ) -> list[CognitiveNodeErrorClusterORM]:
        return (
            self._session.query(CognitiveNodeErrorClusterORM)
            .filter_by(user_id=user_id, node_id=node_id)
            .order_by(CognitiveNodeErrorClusterORM.frequency.desc())
            .all()
        )

    def upsert_error_cluster(
        self, cluster: CognitiveNodeErrorClusterORM
    ) -> CognitiveNodeErrorClusterORM:
        existing = (
            self._session.query(CognitiveNodeErrorClusterORM)
            .filter_by(
                user_id=cluster.user_id,
                node_id=cluster.node_id,
                error_type=cluster.error_type,
            )
            .first()
        )
        if existing is None:
            self._session.add(cluster)
        else:
            existing.frequency = cluster.frequency
            existing.last_occurred = cluster.last_occurred
            existing.cluster_metadata = cluster.cluster_metadata
            self._session.merge(existing)
        self._session.commit()
        return existing if existing else cluster

    def bump_error_cluster(
        self,
        user_id: str,
        node_id: str,
        error_type: str,
        occurred_at: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CognitiveNodeErrorClusterORM:
        cluster = (
            self._session.query(CognitiveNodeErrorClusterORM)
            .filter_by(user_id=user_id, node_id=node_id, error_type=error_type)
            .first()
        )
        if cluster is None:
            cluster = CognitiveNodeErrorClusterORM(
                user_id=user_id,
                node_id=node_id,
                error_type=error_type,
                frequency=1,
                last_occurred=occurred_at,
                cluster_metadata=metadata or {},
            )
            self._session.add(cluster)
        else:
            cluster.frequency += 1
            cluster.last_occurred = occurred_at
            if metadata:
                cluster.cluster_metadata.update(metadata)
            self._session.merge(cluster)
        self._session.commit()
        return cluster

    # ═══════════════════════════════════════════════════════════════
    # DeepProcessing
    # ═══════════════════════════════════════════════════════════════

    def get_deep_processing(
        self, task_id: str
    ) -> Optional[CognitiveNodeDeepProcessingORM]:
        return (
            self._session.query(CognitiveNodeDeepProcessingORM)
            .filter_by(id=task_id)
            .first()
        )

    def list_deep_processing_for_node(
        self,
        user_id: str,
        node_id: str,
        status: Optional[str] = None,
    ) -> list[CognitiveNodeDeepProcessingORM]:
        q = self._session.query(CognitiveNodeDeepProcessingORM).filter_by(
            user_id=user_id, node_id=node_id
        )
        if status:
            q = q.filter_by(status=status)
        return q.order_by(CognitiveNodeDeepProcessingORM.created_at.desc()).all()

    def create_deep_processing_task(
        self,
        user_id: str,
        node_id: str,
        task_type: str,
        prompt: str,
        result: Optional[dict[str, Any]] = None,
    ) -> CognitiveNodeDeepProcessingORM:
        task = CognitiveNodeDeepProcessingORM(
            user_id=user_id,
            node_id=node_id,
            task_type=task_type,
            prompt=prompt,
            result=result or {},
            status="pending",
        )
        self._session.add(task)
        self._session.commit()
        return task

    def complete_deep_processing_task(
        self,
        task_id: str,
        result: dict[str, Any],
    ) -> Optional[CognitiveNodeDeepProcessingORM]:
        task = self.get_deep_processing(task_id)
        if task is None:
            return None
        task.status = "completed"
        task.result = result
        task.completed_at = func.now()
        self._session.commit()
        return task

    # ═══════════════════════════════════════════════════════════════
    # Composition
    # ═══════════════════════════════════════════════════════════════

    def get_composition_member(
        self, member_id: str
    ) -> Optional[CognitiveNodeCompositionMemberORM]:
        return (
            self._session.query(CognitiveNodeCompositionMemberORM)
            .filter_by(id=member_id)
            .first()
        )

    def list_composition_members(
        self, chunk_id: str
    ) -> list[CognitiveNodeCompositionMemberORM]:
        return (
            self._session.query(CognitiveNodeCompositionMemberORM)
            .filter_by(chunk_id=chunk_id)
            .order_by(CognitiveNodeCompositionMemberORM.co_occurrence_count.desc())
            .all()
        )

    def list_chunks_for_node(
        self, user_id: str, node_id: str
    ) -> list[CognitiveNodeCompositionMemberORM]:
        return (
            self._session.query(CognitiveNodeCompositionMemberORM)
            .filter_by(user_id=user_id, node_id=node_id)
            .all()
        )

    def bump_co_occurrence(
        self,
        chunk_id: str,
        user_id: str,
        node_id: str,
    ) -> CognitiveNodeCompositionMemberORM:
        member = (
            self._session.query(CognitiveNodeCompositionMemberORM)
            .filter_by(chunk_id=chunk_id, node_id=node_id)
            .first()
        )
        if member is None:
            member = CognitiveNodeCompositionMemberORM(
                chunk_id=chunk_id,
                user_id=user_id,
                node_id=node_id,
                co_occurrence_count=1,
            )
            self._session.add(member)
        else:
            member.co_occurrence_count += 1
            self._session.merge(member)
        self._session.commit()
        return member

    def reset_projection(self, user_id: str, node_id: str) -> CognitiveNodeProjectionORM:
        """重置投影为默认值（用于回放重建）。"""
        projection = self.get(node_id)
        if projection:
            self._session.delete(projection)
            self._session.commit()
        return self.get_or_create(user_id, node_id)
