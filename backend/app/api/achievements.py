"""
成就系统 REST API
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from app.shared.constants import DEFAULT_USER_ID
from app.core.knowledge_trace import bkt_engine
from app.core.learner_model import learner_engine
from app.services.achievement_engine import achievement_engine
from app.services.storage import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/achievements", tags=["成就系统"])

USER_ID = DEFAULT_USER_ID


def _collect_stats(user_id: str) -> dict[str, Any]:
    """从现有数据源收集所有统计指标"""
    # 从 learner profile 获取基础统计
    profile = learner_engine.get_or_create_profile(user_id)
    summary = learner_engine.get_progress_summary(user_id)

    # Session count
    session_count = profile.total_sessions if hasattr(profile, "total_sessions") else 0

    # 答题统计
    practice_count = summary.total_questions
    correct_count = summary.correct_answers
    accuracy = summary.accuracy_rate

    # Streak
    streak = profile.streak_days if hasattr(profile, "streak_days") else 0

    # 掌握技能数 (p_known >= 0.8)
    states = bkt_engine.load_all_states(user_id)
    mastered_skills = sum(1 for s in states.values() if s.p_known >= 0.8)

    # 多学科覆盖
    from domain.knowledge.prerequisites import SKILL_TO_SUBJECT
    subject_mastered: set[str] = set()
    for skill_id, state in states.items():
        if state.p_known >= 0.8:
            subj = SKILL_TO_SUBJECT.get(skill_id, "")
            if subj:
                subject_mastered.add(subj)

    return {
        "practice_count": practice_count,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "session_count": session_count,
        "conversation_count": 0,
        "streak": streak,
        "mastered_skills": mastered_skills,
        "multi_subject_count": len(subject_mastered),
        "fast_correct": 0,
        "perfect_session": 0,
        "comeback": 0,
    }


def _load_existing(user_id: str) -> dict[str, Any]:
    """加载已有成就记录"""
    try:
        data = storage.load(user_id)
        return getattr(data, "achievements", {}) or {}
    except Exception:
        return {}


def _save_achievements(user_id: str, achievements: dict[str, Any]) -> None:
    """保存成就记录"""
    try:
        data = storage.load(user_id)
        data.achievements = achievements
        storage.save(user_id, data)
    except Exception:
        pass


@router.get("/{user_id}")
async def get_achievements(user_id: str = USER_ID):
    """获取所有成就状态（含进度）"""
    stats = _collect_stats(user_id)
    existing = _load_existing(user_id)
    result = achievement_engine.get_all_with_progress(stats, existing)
    return {
        "achievements": result,
        "total": len(result),
        "unlocked_count": sum(1 for a in result if a["unlocked"]),
    }


@router.post("/{user_id}/check")
async def check_achievements(user_id: str = USER_ID):
    """触发成就检测（答题后调用），返回新解锁的成就"""
    stats = _collect_stats(user_id)
    existing = _load_existing(user_id)
    new_ones = achievement_engine.check_all(user_id, stats, existing)

    # 保存新解锁的成就
    if new_ones:
        for a in new_ones:
            existing[a["id"]] = {
                "level": a["level"],
                "unlocked_at": a["unlocked_at"],
            }
        _save_achievements(user_id, existing)

    return {
        "newly_unlocked": new_ones,
        "total_unlocked": len(existing),
    }
