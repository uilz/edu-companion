from app.shared.constants import DEFAULT_USER_ID
"""
学习事件记录与查询 API

存储: UserData 上附加 event_log 字段（轻量，不增加 DB 表）
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.schemas.learning_event import (
    DailyMetrics,
    EventStats,
    EventType,
    LearningEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning-events", tags=["学习事件"])

_MAX_EVENTS = 500  # 最多保留 500 条（超出自动裁剪）


def _get_user_data():
    from app.services.storage import storage
    return storage.load(DEFAULT_USER_ID)

def _save_user_data(data):
    from app.services.storage import storage
    storage.save(DEFAULT_USER_ID, data)


def record_event(
    event_type: EventType,
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


# ═══════════════════════════════════════════════════
# API
# ═══════════════════════════════════════════════════

@router.get("/stats/{partition_id}", response_model=EventStats)
async def get_event_stats(partition_id: str, days: int = 7):
    """获取某分区最近 N 天的事件统计"""
    user_data = _get_user_data()
    events = user_data.event_log

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = [
        e for e in events
        if e.get("partition_id") == partition_id
        and datetime.fromisoformat(e["timestamp"]) > cutoff
    ]

    skills_discussed = []
    peak_hours: list[int] = []
    practice_count = 0
    conversation_count = 0
    mastery_changes = 0
    frustration_count = 0

    for e in recent:
        t = e["type"]
        if t == EventType.PRACTICE_SUBMIT:
            practice_count += 1
        elif t == EventType.CONVERSATION_MESSAGE:
            conversation_count += 1
        elif t == EventType.SKILL_DISCUSSED:
            for sid in e.get("skill_ids", []):
                if sid not in skills_discussed:
                    skills_discussed.append(sid)
        elif t == EventType.SKILL_MASTERY_CHANGED:
            mastery_changes += 1
        elif t == EventType.FRUSTRATION_PEAK:
            frustration_count += 1

    # 高频时段
    hour_counts: dict[int, int] = {}
    for e in recent:
        h = e.get("event_hour", 0)
        hour_counts[h] = hour_counts.get(h, 0) + 1
    peak_hours = sorted(hour_counts, key=hour_counts.get, reverse=True)[:3]

    return EventStats(
        partition_id=partition_id,
        days=days,
        total_events=len(recent),
        practice_count=practice_count,
        conversation_count=conversation_count,
        skills_discussed=skills_discussed,
        mastery_changes=mastery_changes,
        peak_hours=peak_hours,
        frustration_count=frustration_count,
    )


@router.get("/daily/{partition_id}", response_model=list[DailyMetrics])
async def get_daily_metrics(partition_id: str, days: int = 7):
    """获取某分区最近 N 天的每日指标"""
    user_data = _get_user_data()
    events = user_data.event_log

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = [
        e for e in events
        if e.get("partition_id") == partition_id
        and datetime.fromisoformat(e["timestamp"]) > cutoff
    ]

    # 按天分组
    day_groups: dict[str, list[dict]] = {}
    for e in recent:
        day_groups.setdefault(e["event_date"], []).append(e)

    result = []
    for date_str, day_events in sorted(day_groups.items()):
        skills = []
        practice_count = 0
        correct_count = 0
        conversations = 0
        practice_minutes = 0.0

        for e in day_events:
            t = e["type"]
            if t == EventType.PRACTICE_SUBMIT:
                practice_count += 1
                if e.get("data", {}).get("correct"):
                    correct_count += 1
                practice_minutes += e.get("data", {}).get("time_spent", 0)
            elif t == EventType.CONVERSATION_MESSAGE:
                conversations += 1
            elif t == EventType.SKILL_DISCUSSED:
                skills = e.get("skill_ids", [])

        result.append(DailyMetrics(
            date=date_str,
            practice_minutes=practice_minutes,
            practice_count=practice_count,
            correct_count=correct_count,
            conversations=conversations,
            skills_covered=skills,
        ))

    return result
