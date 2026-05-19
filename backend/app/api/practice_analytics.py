"""
练习系统 — 统计 + 行为分析 API
Phase 4D: 从 api/practice.py 拆分
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter

from app.db.database import get_db
from app.core.knowledge_trace import bkt_engine
from app.services.behavior_analyzer import behavior_analyzer
from app.services.habit_formation import habit_formation

router = APIRouter(prefix="/practice", tags=["practice-analytics"])


def _dt(v, now=None):
    if now is None:
        now = datetime.now()
    if v is None:
        return now
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        return datetime.fromisoformat(v)
    return now


def _ds(v):
    d = _dt(v)
    return d.isoformat() if isinstance(d, datetime) else str(d)


@router.get("/stats")
async def get_stats(time_range: str = "week"):
    """获取练习统计"""
    db = get_db()
    user_id = "default_user"
    now = datetime.now()

    days_back = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
    prev_days_back = days_back * 2
    cutoff = (now - timedelta(days=days_back)).isoformat()
    prev_start = (now - timedelta(days=prev_days_back)).isoformat()
    prev_end = cutoff

    rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
        (user_id, cutoff))
    total = len(rows)
    correct = sum(1 for r in rows if r.get("is_correct"))
    accuracy = correct / total if total > 0 else 0.0

    sess_rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
        (user_id, cutoff))
    study_minutes = sum(r.get("estimated_minutes", 0) for r in sess_rows)
    study_days = len(set(r["started_at"].isoformat()[:10] for r in sess_rows if r.get("started_at")))

    prev_rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s AND submitted_at < %s",
        (user_id, prev_start, prev_end))
    prev_total = len(prev_rows)
    prev_correct = sum(1 for r in prev_rows if r.get("is_correct"))
    prev_accuracy = prev_correct / prev_total if prev_total > 0 else 0.0
    prev_sess = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s AND started_at < %s",
        (user_id, prev_start, prev_end))
    prev_minutes = sum(r.get("estimated_minutes", 0) for r in prev_sess)
    prev_days = len(set(r["started_at"].isoformat()[:10] for r in prev_sess if r.get("started_at")))

    error_dist = {}
    for r in rows:
        if not r.get("is_correct") and r.get("error_type"):
            et = r["error_type"]
            error_dist[et] = error_dist.get(et, 0) + 1

    skill_states = bkt_engine.load_all_states(user_id)
    mastery_bars = sorted(
        [{"skill_id": sid, "p_known": round(s.p_known, 2),
          "mastery_level": bkt_engine.get_mastery_level(s),
          "attempt_count": s.attempt_count, "correct_count": s.correct_count}
         for sid, s in skill_states.items() if s.attempt_count > 0],
        key=lambda x: x["p_known"])

    daily_trend = []
    for i in range(days_back - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_rows = [r for r in rows if _ds(r.get("submitted_at"))[:10] == day]
        dt = len(day_rows)
        dc = sum(1 for r in day_rows if r.get("is_correct"))
        daily_trend.append({"date": day[-5:], "questions": dt, "correct": dc,
                            "accuracy": round(dc/dt, 2) if dt > 0 else 0.0})

    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    hourly_heatmap = []
    for day_idx in range(7):
        for hour in [8, 10, 14, 16, 20, 22]:
            count = sum(1 for r in rows if r.get("submitted_at")
                       and _dt(r.get("submitted_at")).weekday() == day_idx
                       and _dt(r.get("submitted_at")).hour == hour)
            hourly_heatmap.append({"day": day_idx+1, "day_name": day_names[day_idx],
                                   "hour": hour, "questions": count})

    return {"user_id": user_id, "time_range": time_range,
            "overview": {"total_questions": total, "accuracy": round(accuracy, 2),
                         "study_days": study_days, "study_minutes": round(study_minutes, 1),
                         "prev_week": {"total_questions": prev_total, "accuracy": round(prev_accuracy, 2),
                                       "study_days": prev_days, "study_minutes": round(prev_minutes, 1)}},
            "daily_trend": daily_trend, "mastery_bars": mastery_bars,
            "error_distribution": [{"type": et, "count": cnt, "pct": round(cnt/sum(error_dist.values()), 2)}
                                   for et, cnt in sorted(error_dist.items(), key=lambda x: -x[1])],
            "hourly_heatmap": hourly_heatmap}


@router.get("/behavior")
async def get_behavior_report(time_range: str = "week"):
    """学习行为分析报告"""
    user_id = "default_user"
    now = datetime.now()

    days_back = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
    cutoff = now - timedelta(days=days_back)

    db = get_db()
    cutoff_str = cutoff.isoformat()
    session_rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
        (user_id, cutoff_str))
    attempt_rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
        (user_id, cutoff_str))

    today_str = now.strftime("%Y-%m-%d")
    today_attempts = [a for a in attempt_rows if _ds(a.get("submitted_at"))[:10] == today_str]
    today_questions = len(today_attempts)
    today_correct = sum(1 for a in today_attempts if a.get("is_correct"))
    today_accuracy = today_correct / today_questions if today_questions > 0 else 0.0

    daily_trend = []
    for i in range(days_back - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_attempts = [a for a in attempt_rows if _ds(a.get("submitted_at"))[:10] == day]
        daily_trend.append({
            "date": day[-5:],
            "questions": len(day_attempts),
            "correct": sum(1 for a in day_attempts if a.get("is_correct")),
            "accuracy": sum(1 for a in day_attempts if a.get("is_correct")) / max(len(day_attempts), 1),
        })

    hourly_heatmap = []
    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for day_idx in range(7):
        for hour in [8, 10, 14, 16, 20, 22]:
            count = sum(
                1 for a in attempt_rows
                if a.get("submitted_at") and _dt(a["submitted_at"]).weekday() == day_idx
                and _dt(a["submitted_at"]).hour == hour
            )
            hourly_heatmap.append({
                "day": day_idx + 1, "day_name": day_names[day_idx],
                "hour": hour, "questions": count,
            })

    skill_states = bkt_engine.load_all_states(user_id)
    mastery_bars = [
        {"skill_id": sid, "p_known": round(s.p_known, 2),
         "mastery_level": bkt_engine.get_mastery_level(s),
         "attempt_count": s.attempt_count, "correct_count": s.correct_count}
        for sid, s in skill_states.items() if s.attempt_count > 0
    ]
    mastery_bars.sort(key=lambda x: x["p_known"])
    total_sessions = len(session_rows)
    total_minutes = sum(r.get("estimated_minutes", 0) for r in session_rows)
    study_days = len(set(_ds(r.get("started_at"))[:10] for r in session_rows if r.get("started_at")))

    report = behavior_analyzer.analyze(
        daily_trend=daily_trend,
        hourly_heatmap=hourly_heatmap,
        mastery_bars=mastery_bars,
        total_sessions=total_sessions,
        total_minutes=total_minutes,
    )

    goal = habit_formation.check_daily_goal(
        today_questions=today_questions,
        today_correct=today_correct,
        today_accuracy=today_accuracy,
        current_streak=report.current_streak,
        total_questions=len(attempt_rows),
        study_days=study_days,
    )
    tiny_habits = habit_formation.get_tiny_habits(report.current_streak)
    pomodoro = habit_formation.get_pomodoro_recommendation(report.fatigue_drop_minute)

    return {
        "user_id": user_id,
        "behavior": report.to_dict(),
        "daily_goal": goal.to_dict(),
        "tiny_habits": [h.to_dict() for h in tiny_habits],
        "pomodoro": pomodoro,
    }
