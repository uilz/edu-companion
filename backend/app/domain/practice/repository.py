"""Practice 聚合根仓储。

负责聚合根的加载和保存。加载时优先读取快照，再应用快照版本之后的命令记录。
保存时写入快照和命令记录。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.domain.practice.aggregate import PracticeAggregateRoot
from app.infrastructure.db.models.cognitive import (
    PracticeAggregateSnapshotORM,
    PracticeCommandRecordORM,
)


class PracticeAggregateRepository:
    """PracticeAggregateRoot 仓储。"""

    def __init__(self, session: Session):
        self._session = session

    def get(self, session_id: str) -> Optional[PracticeAggregateRoot]:
        """加载聚合根。先读快照，再应用后续命令。"""
        snapshot = (
            self._session.query(PracticeAggregateSnapshotORM)
            .filter_by(session_id=session_id)
            .first()
        )
        if snapshot is None:
            return None

        aggregate = PracticeAggregateRoot.from_snapshot(snapshot.payload or {})

        # 应用快照版本之后的命令记录
        records = (
            self._session.query(PracticeCommandRecordORM)
            .filter_by(session_id=session_id)
            .filter(PracticeCommandRecordORM.version > snapshot.version)
            .order_by(PracticeCommandRecordORM.version.asc())
            .all()
        )
        for record in records:
            aggregate.apply_command_record(record.command_type, record.payload or {})

        return aggregate

    def save(self, aggregate: PracticeAggregateRoot, command_id: str, command_type: str, payload: dict) -> None:
        """保存聚合根快照和命令记录。"""
        snapshot = (
            self._session.query(PracticeAggregateSnapshotORM)
            .filter_by(session_id=aggregate.session_id)
            .first()
        )
        if snapshot is None:
            snapshot = PracticeAggregateSnapshotORM(
                session_id=aggregate.session_id,
                user_id=aggregate.user_id,
            )
            self._session.add(snapshot)

        snapshot.version = aggregate.version
        snapshot.status = aggregate.status
        snapshot.payload = aggregate.to_snapshot()

        record = PracticeCommandRecordORM(
            command_id=command_id,
            session_id=aggregate.session_id,
            user_id=aggregate.user_id,
            command_type=command_type,
            version=aggregate.version,
            payload=dict(payload),
        )
        self._session.add(record)
        # 注意：事务由 CommandHandler 统一提交，Repository 不主动 commit
