"""
学习事件记录服务

将原 app/api/learning_events.py 中的 record_event 工具函数迁移到此。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from shared.constants import DEFAULT_USER_ID
from app.schemas.learning_event import LearningEvent

logger = logging.getLogger(__name__)

_MAX_EVENTS = 500  # 最多保留 500 条（超出自动裁剪）


def _get_user_data():
    from app.services.common import get_data_repo
    return get_data_repo().load(DEFAULT_USER_ID)


def _save_user_data(data):
    from app.services.common import get_data_repo
    get_data_repo().save(DEFAULT_USER_ID, data)


def record_event(
    event_type,
    user_id: str = DEFAULT_USER_ID,
    partition_id: str | None = None,
    branch_id: str | None = None,
    skill_ids: list[str] | None = None,
    data: dict | None = None,
):
    """记录一条学习事件（fire-and-forget 友好）"""
    try:
        user_data = _get_user_data()
        events = user_data.event_log

        now = datetime.now(timezone.utc)
        event = LearningEvent(
            user_id=user_id,
            type=event_type,
            timestamp=now,
            partition_id=partition_id,
            branch_id=branch_id,
            skill_ids=skill_ids or [],
            data=data or {},
            event_date=now.strftime("%Y-%m-%d"),
            event_hour=now.hour,
        )

        events.append(event.model_dump(mode="json"))
        # 裁剪旧事件
        if len(events) > _MAX_EVENTS:
            events = events[-_MAX_EVENTS:]

        user_data.event_log = events
        _save_user_data(user_data)
    except Exception as e:
        logger.warning(f"记录事件失败: {e}")
