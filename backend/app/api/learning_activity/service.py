"""Learning Activity service layer"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func

from app.infrastructure.db.models.learning_activity import LearningActivityORM
from app.infrastructure.db.session import get_db_session


def list_activities(
    user_id: str,
    *,
    module: str | None = None,
    activity_type: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """查询用户学习活动列表。"""
    with get_db_session() as session:
        query = session.query(LearningActivityORM).filter(
            LearningActivityORM.user_id == user_id
        )
        if module:
            query = query.filter(LearningActivityORM.module == module)
        if activity_type:
            query = query.filter(LearningActivityORM.activity_type == activity_type)
        if start_time:
            query = query.filter(LearningActivityORM.timestamp >= start_time)
        if end_time:
            query = query.filter(LearningActivityORM.timestamp <= end_time)

        total = query.count()
        items = (
            query.order_by(desc(LearningActivityORM.timestamp))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "items": [_orm_to_dict(a) for a in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def get_stats(
    user_id: str,
    *,
    days: int = 30,
    module: str | None = None,
) -> dict[str, Any]:
    """统计用户学习活动分布。"""
    with get_db_session() as session:
        start_time = datetime.now(timezone.utc) - timedelta(days=days)
        base_query = session.query(LearningActivityORM).filter(
            LearningActivityORM.user_id == user_id,
            LearningActivityORM.timestamp >= start_time,
        )
        if module:
            base_query = base_query.filter(LearningActivityORM.module == module)

        total = base_query.count()

        module_counts = {
            row[0]: row[1]
            for row in base_query.with_entities(
                LearningActivityORM.module,
                func.count(LearningActivityORM.id),
            ).group_by(LearningActivityORM.module).all()
        }

        type_counts = {
            row[0]: row[1]
            for row in base_query.with_entities(
                LearningActivityORM.activity_type,
                func.count(LearningActivityORM.id),
            ).group_by(LearningActivityORM.activity_type).all()
        }

        return {
            "user_id": user_id,
            "total": total,
            "by_module": module_counts,
            "by_activity_type": type_counts,
        }


def _orm_to_dict(activity: LearningActivityORM) -> dict[str, Any]:
    return {
        "id": activity.id,
        "user_id": activity.user_id,
        "activity_type": activity.activity_type,
        "module": activity.module,
        "source_event_id": activity.source_event_id,
        "source_event_type": activity.source_event_type,
        "idempotency_key": activity.idempotency_key,
        "title": activity.title,
        "description": activity.description,
        "status": activity.status,
        "timestamp": activity.timestamp,
        "deep_link": activity.deep_link,
        "meta": activity.meta,
        "created_at": activity.created_at,
        "updated_at": activity.updated_at,
    }
