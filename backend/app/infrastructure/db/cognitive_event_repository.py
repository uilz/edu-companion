"""PracticeEvent / CognitiveEvent Repository（append-only 事件源）"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infrastructure.db.models.cognitive import (
    CognitiveEventORM,
    PracticeEventORM,
)


class CognitiveEventRepository:
    """事件层读写：practice_events（练习事件）与 cognitive_events（领域事件）。"""

    def __init__(self, session: Session):
        self._session = session

    # ═══════════════════════════════════════════════════════════════
    # PracticeEvent
    # ═══════════════════════════════════════════════════════════════

    def get_practice_event(self, event_id: str) -> Optional[PracticeEventORM]:
        return (
            self._session.query(PracticeEventORM).filter_by(id=event_id).first()
        )

    def get_practice_event_by_idempotency(
        self, idempotency_key: str
    ) -> Optional[PracticeEventORM]:
        return (
            self._session.query(PracticeEventORM)
            .filter_by(idempotency_key=idempotency_key)
            .first()
        )

    def list_practice_events_for_node(
        self,
        user_id: str,
        node_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[PracticeEventORM]:
        return (
            self._session.query(PracticeEventORM)
            .filter_by(user_id=user_id, node_id=node_id)
            .order_by(PracticeEventORM.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_practice_events_for_user(
        self,
        user_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[PracticeEventORM]:
        return (
            self._session.query(PracticeEventORM)
            .filter_by(user_id=user_id)
            .order_by(PracticeEventORM.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_practice_events_for_session(
        self, session_id: str
    ) -> list[PracticeEventORM]:
        return (
            self._session.query(PracticeEventORM)
            .filter_by(session_id=session_id)
            .order_by(PracticeEventORM.timestamp.asc())
            .all()
        )

    def count_practice_events_for_node(
        self, user_id: str, node_id: str
    ) -> tuple[int, int]:
        """返回 (总次数, 正确次数)。"""
        total = (
            self._session.query(func.count(PracticeEventORM.id))
            .filter_by(user_id=user_id, node_id=node_id)
            .scalar()
            or 0
        )
        correct = (
            self._session.query(func.count(PracticeEventORM.id))
            .filter_by(user_id=user_id, node_id=node_id, success=True)
            .scalar()
            or 0
        )
        return int(total), int(correct)

    def append_practice_event(
        self,
        event: PracticeEventORM,
    ) -> Optional[PracticeEventORM]:
        """幂等写入练习事件；若 idempotency_key 已存在则返回已存在记录。"""
        if not event.idempotency_key:
            event.idempotency_key = self._make_idempotency_key(event)

        existing = self.get_practice_event_by_idempotency(event.idempotency_key)
        if existing:
            return existing

        self._session.add(event)
        self._session.commit()
        return event

    def append_practice_event_upsert(
        self,
        event: PracticeEventORM,
    ) -> PracticeEventORM:
        """INSERT ... ON CONFLICT DO NOTHING，保证幂等。"""
        if not event.idempotency_key:
            event.idempotency_key = self._make_idempotency_key(event)

        stmt = (
            insert(PracticeEventORM)
            .values(
                id=event.id,
                user_id=event.user_id,
                node_id=event.node_id,
                session_id=event.session_id,
                question_id=event.question_id,
                timestamp=event.timestamp,
                success=event.success,
                latency_ms=event.latency_ms,
                weight=event.weight,
                difficulty=event.difficulty,
                guess=event.guess,
                slip=event.slip,
                confidence_before=event.confidence_before,
                confidence_after=event.confidence_after,
                hints_used=event.hints_used,
                time_spent=event.time_spent,
                error_embedding=event.error_embedding,
                actor_type=event.actor_type,
                source_type=event.source_type,
                source_id=event.source_id,
                idempotency_key=event.idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        self._session.execute(stmt)
        self._session.commit()

        # 返回实际 persisted 记录
        persisted = self.get_practice_event_by_idempotency(event.idempotency_key)
        return persisted if persisted else event

    @staticmethod
    def _make_idempotency_key(event: PracticeEventORM) -> str:
        return (
            f"pe:{event.user_id}:{event.node_id}:{event.session_id}:"
            f"{event.question_id}:{event.timestamp:.3f}"
        )

    # ═══════════════════════════════════════════════════════════════
    # CognitiveEvent
    # ═══════════════════════════════════════════════════════════════

    def get_cognitive_event(self, event_id: str) -> Optional[CognitiveEventORM]:
        return (
            self._session.query(CognitiveEventORM).filter_by(id=event_id).first()
        )

    def list_cognitive_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        node_id: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[CognitiveEventORM]:
        q = self._session.query(CognitiveEventORM).filter_by(user_id=user_id)
        if event_type:
            q = q.filter_by(event_type=event_type)
        if status:
            q = q.filter_by(status=status)
        if node_id:
            q = q.filter_by(node_id=node_id)
        return (
            q.order_by(CognitiveEventORM.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_pending_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        limit: int = 500,
    ) -> list[CognitiveEventORM]:
        return self.list_cognitive_events(
            user_id=user_id,
            event_type=event_type,
            status="pending",
            limit=limit,
        )

    def append_cognitive_event(
        self,
        user_id: str,
        event_type: str,
        payload: dict[str, Any],
        source_type: str = "",
        source_id: str = "",
        node_id: Optional[str] = None,
        actor_type: str = "user",
    ) -> CognitiveEventORM:
        event = CognitiveEventORM(
            user_id=user_id,
            event_type=event_type,
            source_type=source_type,
            source_id=source_id,
            actor_type=actor_type,
            node_id=node_id,
            payload=payload,
            status="pending",
        )
        self._session.add(event)
        self._session.commit()
        return event

    def mark_processed(self, event_id: str) -> Optional[CognitiveEventORM]:
        event = self.get_cognitive_event(event_id)
        if event is None:
            return None
        event.status = "processed"
        event.processed_at = func.now()
        self._session.commit()
        return event

    def mark_failed(self, event_id: str, reason: str = "") -> Optional[CognitiveEventORM]:
        event = self.get_cognitive_event(event_id)
        if event is None:
            return None
        event.status = "failed"
        event.payload["_failure_reason"] = reason
        event.processed_at = func.now()
        self._session.commit()
        return event

    # ═══════════════════════════════════════════════════════════════
    # 跨事件查询
    # ═══════════════════════════════════════════════════════════════

    def get_latest_practice_timestamp(self, user_id: str, node_id: str) -> float:
        ts = (
            self._session.query(func.max(PracticeEventORM.timestamp))
            .filter_by(user_id=user_id, node_id=node_id)
            .scalar()
        )
        return float(ts) if ts else 0.0

    def get_latest_cognitive_event_time(
        self, user_id: str, event_type: Optional[str] = None
    ) -> Optional[float]:
        q = self._session.query(func.max(CognitiveEventORM.created_at)).filter_by(
            user_id=user_id
        )
        if event_type:
            q = q.filter_by(event_type=event_type)
        dt = q.scalar()
        return dt.timestamp() if dt else None
