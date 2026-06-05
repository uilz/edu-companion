"""
学习进度 REST API 端点
跟踪和查询学习进度、学习统计

Data sources (Phase 16 S7):
  - cognitive_nodes 表：掌握度、练习汇总、推荐 (Primary)
  - attempts 表：每日统计、日历 (DB-backed via AttemptRepo)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from shared.learner_model import learner_engine
from app.db.repository import AttemptRepo
from app.schemas.learner import ProgressSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/progress", tags=["学习进度"])

import time

# Simple in-memory TTL cache for expensive queries
_progress_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 60  # seconds

def _cached(key: str, ttl: int = _CACHE_TTL):
    """Decorator for caching function results with TTL."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            cache_key = f"{key}:{':'.join(str(a) for a in args)}"
            now = time.time()
            if cache_key in _progress_cache:
                ts, val = _progress_cache[cache_key]
                if now - ts < ttl:
                    return val
            result = fn(*args, **kwargs)
            _progress_cache[cache_key] = (now, result)
            return result
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════
# 源1: cognitive_nodes 表 (Primary)
# ═══════════════════════════════════════════════════


@_cached("progress")
def _build_progress_from_cognitive(user_id: str) -> ProgressSummary | None:
    """从 cognitive_nodes 表构建 ProgressSummary

    返回 None 表示无认知节点数据。
    """
    try:
        from app.cognitive.storage import list_all_nodes
        nodes = list_all_nodes(user_id)
        if not nodes:
            return None

        total = 0
        correct = 0
        study_seconds = 0.0
        mastered: list[str] = []
        struggling: list[str] = []

        for node in nodes:
            ps = node.practice_summary
            if ps:
                total += ps.total_attempts
                correct += ps.correct_attempts
                study_seconds += ps.total_time_spent

            # 掌握度判断
            if node.belief and node.belief.proficiency_mean is not None:
                mu = node.belief.proficiency_mean
                label = node.label or node.id
                if mu >= 0.8:
                    mastered.append(label)
                elif mu < 0.4:
                    struggling.append(label)

        accuracy = correct / total if total > 0 else 0.0
        study_minutes = study_seconds / 60.0

        # 生成建议
        recommendations: list[str] = []
        if struggling:
            recommendations.append(f"建议重点复习: {', '.join(struggling[:3])}")
        if accuracy < 0.6:
            recommendations.append("正确率较低，建议降低难度巩固基础")
        elif accuracy > 0.9:
            recommendations.append("掌握不错！可以尝试更高难度的挑战")

        return ProgressSummary(
            user_id=user_id,
            total_questions=total,
            correct_answers=correct,
            accuracy_rate=accuracy,
            study_minutes=study_minutes,
            mastered_skills=mastered,
            struggling_skills=struggling,
            recent_activity=[],
            recommendations=recommendations,
        )
    except Exception as e:
        logger.warning("cognitive_nodes 聚合失败, fallback: %s", e)
        return None


@_cached("cog_nodes")
def _list_cognitive_nodes(user_id: str) -> list[dict[str, Any]]:
    """列出用户的所有 CognitiveNode，返回精简 dict 列表"""
    try:
        from app.cognitive.storage import list_all_nodes
        nodes = list_all_nodes(user_id)
        result = []
        for n in nodes:
            mu = n.belief.proficiency_mean if n.belief else 0.0
            ps = n.practice_summary
            result.append({
                "id": n.id,
                "label": n.label,
                "level": n.level,
                "proficiency": round(mu, 4),
                "attempts": ps.total_attempts if ps else 0,
                "correct": ps.correct_attempts if ps else 0,
            })
        return result
    except Exception:
        return []


@_cached("weak_nodes")
def _get_weak_nodes(
    user_id: str, top_n: int = 3,
) -> list[dict[str, Any]]:
    """获取最弱的 N 个节点（按 proficiency_mean 升序）"""
    try:
        from app.cognitive.storage import list_all_nodes
        nodes = list_all_nodes(user_id)
        rated = []
        for n in nodes:
            if n.belief and n.practice_summary and n.practice_summary.total_attempts > 0:
                rated.append({
                    "skill_id": n.id,
                    "label": n.label or n.id,
                    "mastery": round(n.belief.proficiency_mean * 100),
                })
        rated.sort(key=lambda x: x["mastery"])
        return rated[:top_n]
    except Exception:
        return []


# ═══════════════════════════════════════════════════
# 端点
# ═══════════════════════════════════════════════════


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
    - 个性化建议
    """
    summary = _build_progress_from_cognitive(user_id)
    if summary is not None:
        return summary

    # 无认知数据时返回空摘要
    return ProgressSummary(
        user_id=user_id,
        total_questions=0,
        correct_answers=0,
        accuracy_rate=0.0,
        study_minutes=0.0,
        mastered_skills=[],
        struggling_skills=[],
        recent_activity=[],
        recommendations=[],
    )


@router.get("/{user_id}/stats")
async def get_detailed_stats(user_id: str) -> dict[str, Any]:
    """
    获取详细的学习统计数据

    包含更细粒度的统计信息，如按学科统计、按时间统计等。
    来自 cognitive_nodes (掌握度) + attempts 表 (日维度)。
    """
    # 从 cognitive_nodes 获取总体指标
    nodes = _list_cognitive_nodes(user_id)
    total_q = sum(n["attempts"] for n in nodes)
    correct_q = sum(n["correct"] for n in nodes)
    accuracy = correct_q / total_q if total_q > 0 else 0.0

    mastered = [n for n in nodes if n["proficiency"] >= 0.8]
    struggling = [n for n in nodes if n["proficiency"] < 0.4]

    # 按学科归类（从 node 层级/前缀推断）
    subject_stats: dict[str, dict[str, Any]] = {}
    for n in nodes:
        # 取 id 中点之前的部分作为学科名
        subject = n["id"].split(".")[0] if "." in n["id"] else (n["level"] or "其他")
        if subject not in subject_stats:
            subject_stats[subject] = {"total": 0, "correct": 0}
        subject_stats[subject]["total"] += n["attempts"]
        subject_stats[subject]["correct"] += n["correct"]
    for subj, stats in subject_stats.items():
        t = stats["total"]
        stats["accuracy"] = round(stats["correct"] / t, 3) if t > 0 else 0.0

    # 从 attempts 表获取最近 7 天
    from datetime import datetime, timedelta
    daily_stats: dict[str, dict[str, int]] = {}
    for i in range(7):
        date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_stats[date_str] = {"total": 0, "correct": 0}

    try:
        attempts = await AttemptRepo.list_all(user_id)
        for a in attempts:
            ts = a.get("submitted_at", "")
            if ts:
                date_str = ts[:10]
                if date_str in daily_stats:
                    daily_stats[date_str]["total"] += 1
                    if a.get("is_correct"):
                        daily_stats[date_str]["correct"] += 1
    except Exception as e:
        logger.warning("Failed to compute daily stats from attempts: %s", e)

    return {
        "user_id": user_id,
        "overall": {
            "total_questions": total_q,
            "correct_answers": correct_q,
            "accuracy_rate": round(accuracy, 3),
            "study_minutes": round(total_q * 2.5, 1),  # 估算
        },
        "by_subject": subject_stats,
        "daily": daily_stats,
        "mastered_count": len(mastered),
        "struggling_count": len(struggling),
        "cognitive_nodes_count": len(nodes),
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
    from datetime import timedelta
    check = now.date() - timedelta(days=1)  # 从昨天开始
    for _ in range(32):
        date_str = check.isoformat()
        if date_str in daily and daily[date_str]["total"] > 0:
            streak += 1
            check = check - timedelta(days=1)
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
    今日推荐来自 cognitive_nodes 表。
    """
    from datetime import datetime, timedelta

    now = datetime.now()
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

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

    # streak
    profile = learner_engine.get_or_create_profile(user_id)
    streak = profile.streak_days if hasattr(profile, "streak_days") else 0

    # 今日推荐：从 cognitive_nodes 获取最弱的 3 个
    recommendations = _get_weak_nodes(user_id, top_n=3)

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
        "streak": streak,
        "recommendations": [
            {"skill_id": r["skill_id"], "label": r.get("label", r["skill_id"]), "mastery": r["mastery"]}
            for r in recommendations
        ],
        "encourage": random.choice(encourages),
    }
