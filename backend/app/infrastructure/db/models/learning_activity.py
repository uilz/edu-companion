"""
Learning Activity ORM 模型（SQLAlchemy 2.0）

统一记录用户在各壳中的学习行为，为秘书仪表盘、知识树详情等场景提供时间线数据。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.cognitive import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return f"la_{uuid.uuid4().hex[:12]}"


class LearningActivityORM(Base):
    """学习活动记录 — 跨壳统一的用户行为时间线。"""

    __tablename__ = "learning_activities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    activity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    source_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # 业务幂等键：同一学习行为只记录一次。
    # 例如 SessionCompleted → session_id, AnswerSubmitted → attempt_id,
    # FlashCardReviewed → card_id + reviewed_at(秒级)。
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )

    deep_link: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    __table_args__ = (
        Index("ix_learning_activities_user_time", "user_id", "timestamp"),
        Index("ix_learning_activities_user_module", "user_id", "module", "timestamp"),
        Index("ix_learning_activities_user_type", "user_id", "activity_type", "timestamp"),
        Index("ix_learning_activities_user_idempotency", "user_id", "idempotency_key", unique=True),
    )
