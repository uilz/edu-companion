"""统计 + 成就"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_stats import (
    get_overview, get_daily_trend, get_session_history,
    get_error_distribution, get_weak_skills,
)
from app.services.practice.engine import (
    compute_practice_stats,
    compute_behavior_report_data,
)
from app.services.analytics.achievement_service import (
    check_achievements, get_all_achievements, get_recent_unlocks, get_badge_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 统计
# ═══════════════════════════════════════════════

@router.get("/stats/overview")
async def api_stats_overview(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return get_overview(user_id)


@router.get("/stats/daily")
async def api_stats_daily(user_id: str = Depends(current_user_id), days: int = 30):
    _ensure_tables()
    return get_daily_trend(user_id, days=min(days, 90))


@router.get("/stats/sessions")
async def api_stats_sessions(user_id: str = Depends(current_user_id), limit: int = 10):
    _ensure_tables()
    return get_session_history(user_id, limit=min(limit, 50))


@router.get("/stats/errors")
async def api_stats_errors(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return get_error_distribution(user_id)


@router.get("/stats/weak-skills")
async def api_stats_weak_skills(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return get_weak_skills(user_id)


# ═══════════════════════════════════════════════
# 成就/徽章
# ═══════════════════════════════════════════════

@router.get("/achievements")
async def api_get_achievements(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return get_all_achievements(user_id)


@router.get("/achievements/recent")
async def api_recent_achievements(user_id: str = Depends(current_user_id), limit: int = 5):
    _ensure_tables()
    return get_recent_unlocks(user_id, limit=min(limit, 20))


@router.get("/achievements/stats")
async def api_achievement_stats(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return get_badge_stats(user_id)


@router.post("/achievements/check")
async def api_check_achievements(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    newly = check_achievements(user_id)
    return {"newly_unlocked": newly, "count": len(newly)}


# ═══════════════════════════════════════════════
# 综合统计 + 学习行为分析（旧版兼容）
# ═══════════════════════════════════════════════


@router.get("/stats")
async def get_stats(user_id: str = Depends(current_user_id), time_range: str = "week"):
    """获取练习统计"""
    return compute_practice_stats(time_range=time_range, user_id=user_id)


@router.get("/behavior")
async def get_behavior_report(user_id: str = Depends(current_user_id), time_range: str = "week"):
    """学习行为分析报告"""
    return compute_behavior_report_data(time_range=time_range, user_id=user_id)
