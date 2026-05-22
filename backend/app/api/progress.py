"""
学习进度 REST API 端点
跟踪和查询学习进度、学习统计
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.learner_model import learner_engine
from app.db.repository import AttemptRepo
from app.schemas.learner import ProgressSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/progress", tags=["学习进度"])


def _count_cognitive_nodes(user_id: str) -> int:
    """统计 CognitiveNode 数量（Phase 6 迁移辅助）"""
    try:
        from app.db.database import get_db
        db = get_db()
        row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM cognitive_nodes WHERE user_id = %s",
            (user_id,)
        )
        return row["cnt"] if row else 0
    except Exception:
        return 0


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
        "cognitive_nodes_count": _count_cognitive_nodes(user_id),
        "total_study_minutes": profile.total_study_minutes,
        "streak_days": profile.streak_days,
        "created_at": profile.created_at.isoformat(),
    }


@router.get("/{user_id}/calendar")
async def get_calendar(
    user_id: str,
    year: int = 0,
    month: int = 0,
) -> dict[str, Any]:
    """
    获取指定月份的学习日历数据

    返回当月每天的总答题数、正确数、正确率。
    基于 attempts 表的时间戳聚合。
    """
    import calendar as cal_mod
    from datetime import datetime, date

    now = datetime.now()
    y = year if year > 0 else now.year
    m = month if 1 <= month <= 12 else now.month

    # 当月范围
    first_day = date(y, m, 1)
    last_day_num = cal_mod.monthrange(y, m)[1]
    last_day = date(y, m, last_day_num)

    since = first_day.isoformat()
    until = last_day.isoformat()

    # 查询当月所有 attempts
    try:
        attempts = await AttemptRepo.list_all(user_id, since=since)
    except Exception:
        attempts = []

    # 按日期聚合
    from collections import defaultdict
    daily: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})

    for a in attempts:
        ts = a.get("submitted_at", "")
        if not ts:
            continue
        date_key = ts[:10]  # "2026-05-19"
        if date_key > until:
            continue
        daily[date_key]["total"] += 1
        if a.get("is_correct"):
            daily[date_key]["correct"] += 1

    # 生成当月所有日期（包括过去、今天、未来）
    days = []
    month_total = 0
    month_correct = 0
    for d in range(1, last_day_num + 1):
        date_str = f"{y:04d}-{m:02d}-{d:02d}"
        entry = daily.get(date_str, {"total": 0, "correct": 0})
        total = entry["total"]
        correct = entry["correct"]
        accuracy = round(correct / total, 3) if total > 0 else None
        days.append({
            "date": date_str,
            "day": d,
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
        })
        month_total += total
        month_correct += correct

    month_accuracy = round(month_correct / month_total, 3) if month_total > 0 else None

    # 计算当月 streak（连续学习天数，从昨天往前数）
    streak = 0
    check = now.date() - __import__("datetime").timedelta(days=1)  # 从昨天开始
    for _ in range(32):
        date_str = check.isoformat()
        if date_str in daily and daily[date_str]["total"] > 0:
            streak += 1
            check = check - __import__("datetime").timedelta(days=1)
        else:
            break

    # Best day
    best_total = max((d["total"] for d in days), default=0)
    best_day = next((d for d in days if d["total"] == best_total and best_total > 0), None)

    return {
        "year": y,
        "month": m,
        "days": days,
        "month_total": month_total,
        "month_correct": month_correct,
        "month_accuracy": month_accuracy,
        "month_streak": streak,
        "best_day": {"date": best_day["date"], "total": best_total} if best_day else None,
    }


@router.get("/{user_id}/summary")
async def get_daily_summary(user_id: str) -> dict[str, Any]:
    """
    每日摘要 — 昨日总结 + 今日推荐，用于前端卡片展示。

    返回空对象 {} 表示昨天无学习记录。
    """
    from datetime import datetime, timedelta, date

    now = datetime.now()
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    day_before = (now - timedelta(days=2)).strftime("%Y-%m-%d")

    # 查昨日 attempts
    try:
        attempts = await AttemptRepo.list_all(user_id, since=yesterday)
    except Exception:
        return {}

    yesterday_total = 0
    yesterday_correct = 0
    for a in attempts:
        ts = a.get("submitted_at", "")
        if ts and ts[:10] == yesterday:
            yesterday_total += 1
            if a.get("is_correct"):
                yesterday_correct += 1

    if yesterday_total == 0:
        return {}

    accuracy = yesterday_correct / yesterday_total

    # 前日对比
    prev_total = 0
    try:
        prev_attempts = await AttemptRepo.list_all(user_id, since=day_before)
        for a in prev_attempts:
            ts = a.get("submitted_at", "")
            if ts and ts[:10] == day_before:
                prev_total += 1
    except Exception:
        pass

    delta = yesterday_total - prev_total

    # streak
    profile = learner_engine.get_or_create_profile(user_id)
    streak = profile.streak_days if hasattr(profile, "streak_days") else 0

    # 今日推荐：最弱的 3 个可练习技能
    recommendations = []
    try:
        from domain.knowledge.prerequisites import ALL_PREREQUISITES
        from app.core.knowledge_trace import bkt_engine as _bkt
        skills = []
        for sid in ALL_PREREQUISITES:
            state = _bkt.load_or_create(user_id, sid)
            skills.append((sid, state.p_known))
        skills.sort(key=lambda x: x[1])  # mastery 低优先
        for sid, pk in skills[:3]:
            recommendations.append({"skill_id": sid, "mastery": round(pk * 100)})
    except Exception:
        pass

    # 随机鼓励语
    import random
    encourages = [
        "坚持下去，复利效应正在发生 📈",
        "每一个知识点都是未来的砖瓦 🧱",
        "今天比昨天多会一点，就是胜利 ✨",
        "学习是一场马拉松，不是冲刺 🏃",
    ]

    return {
        "yesterday": {
            "date": yesterday,
            "total": yesterday_total,
            "correct": yesterday_correct,
            "accuracy": round(accuracy, 3),
        },
        "vs_previous": {"total": prev_total, "delta": delta},
        "streak": streak,
        "recommendations": recommendations,
        "encourage": random.choice(encourages),
    }
