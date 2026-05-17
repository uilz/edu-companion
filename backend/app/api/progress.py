"""
学习进度 REST API 端点
跟踪和查询学习进度、学习统计
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.learner_model import learner_engine
from app.schemas.learner import ProgressSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/progress", tags=["学习进度"])


@router.get("/{user_id}", response_model=ProgressSummary)
async def get_progress(user_id: str) -> ProgressSummary:
    """
    获取用户的学习进度摘要

    包含：
    - 总答题数和正确数
    - 正确率
    - 学习时长
    - 已掌握的知识点
    - 薄弱的知识点
    - 最近活动记录
    - 个性化建议

    参数:
        user_id: 用户ID

    返回:
        学习进度摘要
    """
    summary = learner_engine.get_progress_summary(user_id)
    return summary


@router.get("/{user_id}/stats")
async def get_detailed_stats(user_id: str) -> dict[str, Any]:
    """
    获取详细的学习统计数据

    包含更细粒度的统计信息，如按学科统计、按时间统计等

    参数:
        user_id: 用户ID

    返回:
        详细统计数据
    """
    profile = learner_engine.get_or_create_profile(user_id)
    summary = learner_engine.get_progress_summary(user_id)
    activities = learner_engine._activity_log.get(user_id, [])

    # 按学科统计
    subject_stats: dict[str, dict[str, Any]] = {}
    for activity in activities:
        if activity.get("type") == "practice":
            skill_id = activity.get("skill_id", "unknown")
            # 简单地将skill_id前缀作为学科
            subject = skill_id.split("_")[0] if "_" in skill_id else "其他"

            if subject not in subject_stats:
                subject_stats[subject] = {
                    "total": 0,
                    "correct": 0,
                    "total_time": 0.0,
                }
            subject_stats[subject]["total"] += 1
            if activity.get("is_correct"):
                subject_stats[subject]["correct"] += 1
            subject_stats[subject]["total_time"] += activity.get("time_spent", 0)

    # 计算各学科正确率
    for subject, stats in subject_stats.items():
        total = stats["total"]
        stats["accuracy"] = stats["correct"] / total if total > 0 else 0.0

    # 按日期统计（最近7天）
    from datetime import datetime, timedelta
    daily_stats: dict[str, dict[str, int]] = {}
    for i in range(7):
        date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_stats[date_str] = {"total": 0, "correct": 0}

    for activity in activities:
        if activity.get("type") == "practice":
            ts = activity.get("timestamp", "")
            if ts:
                date_str = ts[:10]  # 取日期部分
                if date_str in daily_stats:
                    daily_stats[date_str]["total"] += 1
                    if activity.get("is_correct"):
                        daily_stats[date_str]["correct"] += 1

    return {
        "user_id": user_id,
        "overall": {
            "total_questions": summary.total_questions,
            "correct_answers": summary.correct_answers,
            "accuracy_rate": summary.accuracy_rate,
            "study_minutes": summary.study_minutes,
        },
        "by_subject": subject_stats,
        "daily": daily_stats,
        "mastered_count": len(summary.mastered_skills),
        "struggling_count": len(summary.struggling_skills),
        "recommendations": summary.recommendations,
    }


@router.post("/{user_id}/session/start")
async def start_study_session(
    user_id: str,
    subject: str | None = None,
) -> dict[str, Any]:
    """
    开始一个新的学习会话

    参数:
        user_id: 用户ID
        subject: 学习学科

    返回:
        会话信息
    """
    session_id = learner_engine.create_session(user_id, subject)
    return {
        "session_id": session_id,
        "user_id": user_id,
        "subject": subject,
        "message": "学习会话已开始，加油！💪",
    }


@router.post("/{user_id}/profile/update")
async def update_profile(
    user_id: str,
    nickname: str | None = None,
    subjects: list[str] | None = None,
    grade_level: int | None = None,
    learning_style: str | None = None,
) -> dict[str, Any]:
    """
    更新学习者画像

    参数:
        user_id: 用户ID
        nickname: 昵称
        subjects: 学科列表
        grade_level: 年级
        learning_style: 学习风格

    返回:
        更新后的画像信息
    """
    updates: dict[str, Any] = {}
    if nickname is not None:
        updates["nickname"] = nickname
    if subjects is not None:
        updates["subjects"] = subjects
    if grade_level is not None:
        updates["grade_level"] = grade_level
    if learning_style is not None:
        updates["learning_style"] = learning_style

    profile = learner_engine.update_profile(user_id, updates)

    return {
        "user_id": profile.user_id,
        "nickname": profile.nickname,
        "subjects": profile.subjects,
        "grade_level": profile.grade_level,
        "learning_style": profile.learning_style,
        "message": "画像更新成功",
    }


@router.get("/{user_id}/profile")
async def get_profile(user_id: str) -> dict[str, Any]:
    """
    获取学习者画像

    参数:
        user_id: 用户ID

    返回:
        学习者画像信息
    """
    profile = learner_engine.get_or_create_profile(user_id)
    return {
        "user_id": profile.user_id,
        "nickname": profile.nickname,
        "subjects": profile.subjects,
        "grade_level": profile.grade_level,
        "learning_style": profile.learning_style,
        "knowledge_skills_count": len(profile.knowledge_states),
        "total_study_minutes": profile.total_study_minutes,
        "streak_days": profile.streak_days,
        "created_at": profile.created_at.isoformat(),
    }
