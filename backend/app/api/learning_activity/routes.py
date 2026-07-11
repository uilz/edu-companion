"""Learning Activity REST API

路由前缀: /api/activities
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.learning_activity.schemas import (
    LearningActivityListResponse,
    LearningActivityStatsResponse,
)
from app.api.learning_activity import service
from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/activities", tags=["Learning Activity 学习活动流"])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # 支持带 Z 的 ISO 格式
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as exc:
        raise HTTPException(400, f"无效的时间格式: {value}") from exc


@router.get(
    "/",
    response_model=LearningActivityListResponse,
    summary="查询用户学习活动流",
)
async def list_activities(
    user_id: str = Depends(current_user_id),
    module: Optional[str] = Query(None, description="按模块筛选，如 practice / flashcard / reading"),
    activity_type: Optional[str] = Query(None, description="按活动类型筛选，如 answer_submitted / session_completed"),
    start_time: Optional[str] = Query(None, description="ISO 8601 开始时间"),
    end_time: Optional[str] = Query(None, description="ISO 8601 结束时间"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if not user_id:
        raise HTTPException(401, "请先登录")

    data = service.list_activities(
        user_id,
        module=module,
        activity_type=activity_type,
        start_time=_parse_iso_datetime(start_time),
        end_time=_parse_iso_datetime(end_time),
        limit=limit,
        offset=offset,
    )
    return LearningActivityListResponse(**data)


@router.get(
    "/stats",
    response_model=LearningActivityStatsResponse,
    summary="学习活动统计",
)
async def get_activity_stats(
    user_id: str = Depends(current_user_id),
    days: int = Query(30, ge=1, le=365, description="统计最近 N 天"),
    module: Optional[str] = Query(None, description="按模块筛选"),
):
    if not user_id:
        raise HTTPException(401, "请先登录")

    data = service.get_stats(user_id, days=days, module=module)
    return LearningActivityStatsResponse(**data)
