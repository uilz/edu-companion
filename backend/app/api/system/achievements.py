"""
成就系统 REST API
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.domain.auth.dependencies import current_user_id
from shared.learner_model import learner_engine
from app.services.analytics.achievement_engine import achievement_engine
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/achievements", tags=["成就系统"])


def _collect_stats(user_id: str) -> dict[str, Any]:
    """从现有数据源收集所有统计指标（v7: 全部从 PG 真实读取）"""
    try:
        # 从 learner profile 拿持久化字段（streak/total_study_minutes 也走真实计算）
        profile = learner_engine.get_or_create_profile(user_id)
        summary = learner_engine.get_progress_summary(user_id)

        # Session count：从 PG practice_sessions 真实统计
        session_count = learner_engine.get_total_sessions(user_id)

        # 答题统计
        practice_count = summary.total_questions
        correct_count = summary.correct_answers
        accuracy = summary.accuracy_rate

        # Streak：从 PG 真实计算连续天数
        streak = learner_engine.get_streak_days(user_id)

        # 掌握技能数
        try:
            from app.domain.cognitive import get_repo
            cog_nodes = get_repo().list_all_nodes(user_id)
        except Exception:
            cog_nodes = []

        mastered_skills = sum(
            1 for n in cog_nodes
            if n.belief and n.belief.proficiency_mean >= 0.8
        )

        # 多学科覆盖
        try:
            from app.domain.knowledge.prerequisites import SKILL_TO_SUBJECT
        except Exception:
            SKILL_TO_SUBJECT = {}
        subject_mastered: set[str] = set()
        for node in cog_nodes:
            if node.belief and node.belief.proficiency_mean >= 0.8:
                subj = SKILL_TO_SUBJECT.get(node.id, "")
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
    except Exception as e:
        logger.warning("成就统计收集失败（返回默认值）: %s", e)
        return {
            "practice_count": 0, "correct_count": 0, "accuracy": 0,
            "session_count": 0, "conversation_count": 0, "streak": 0,
            "mastered_skills": 0, "multi_subject_count": 0,
            "fast_correct": 0, "perfect_session": 0, "comeback": 0,
        }


def _load_existing(user_id: str) -> dict[str, Any]:
    """加载已有成就记录"""
    try:
        data = get_data_repo().load(user_id)
        return getattr(data, "achievements", {}) or {}
    except Exception:
        return {}


def _save_achievements(user_id: str, achievements: dict[str, Any]) -> None:
    """保存成就记录"""
    try:
        data = get_data_repo().load(user_id)
        data.achievements = achievements
        get_data_repo().save(user_id, data)
    except Exception as e:
        logger.error("Failed to save achievements for %s: %s", user_id, e)


@router.get("/{user_id}")
async def get_achievements(user_id: str = Depends(current_user_id)):
    """获取所有成就状态（含进度）"""
    stats = _collect_stats(user_id)
    existing = _load_existing(user_id)
    result = achievement_engine.get_all_with_progress(stats, existing)
    return {
        "achievements": result,
        "total": len(result),
        "unlocked_count": sum(1 for a in result if a["unlocked"]),
    }

