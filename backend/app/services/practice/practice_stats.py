"""
练习统计汇总 — v7 数据驱动

聚合来源:
- practice_attempts → 答题记录
- practice_sessions → 会话统计
- questions → 题库统计
- cognitive_nodes → 知识掌握度
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)


def get_overview(user_id: str = DEFAULT_USER_ID) -> dict:
    """
    总体概览统计。

    返回:
        total_questions, total_correct, total_wrong, accuracy,
        total_sessions, study_minutes, mastered_count, weak_count,
        due_review_count, today_questions
    """
    from app.db.database import get_db
    db = get_db()

    # 总答题统计
    agg = db.fetchone(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
                  SUM(CASE WHEN is_wrong THEN 1 ELSE 0 END) as wrong,
                  SUM(time_spent_seconds) as total_seconds
           FROM practice_attempts WHERE user_id = %s""",
        (user_id,),
    )
    total = agg["total"] or 0 if agg else 0
    correct = agg["correct"] or 0 if agg else 0
    wrong = agg["wrong"] or 0 if agg else 0
    total_seconds = agg["total_seconds"] or 0 if agg else 0

    # 会话统计
    session_count = db.fetchone(
        "SELECT COUNT(*) as cnt FROM practice_sessions WHERE user_id = %s AND status = 'completed'",
        (user_id,),
    )
    total_sessions = session_count["cnt"] if session_count else 0

    # 今日练习
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today = db.fetchone(
        "SELECT COUNT(*) as cnt FROM practice_attempts WHERE user_id = %s AND created_at >= %s",
        (user_id, today_start),
    )
    today_questions = today["cnt"] if today else 0

    # 知识点掌握度 — 从 cognitive_nodes 读取
    from app.cognitive.storage import get_nodes_by_level
    atoms = get_nodes_by_level("atom", user_id) or []
    mastered = sum(1 for n in atoms if n.belief.proficiency_mean >= 0.8)
    weak = [n for n in atoms if 0 < n.belief.proficiency_mean < 0.4]

    # 待复习数量
    from app.services.practice.practice_scheduler import get_review_stats
    rev_stats = get_review_stats(user_id)
    due_now = rev_stats.get("due_now", 0)

    accuracy = round(correct / max(total, 1) * 100, 1)
    study_minutes = round(total_seconds / 60, 1)

    return {
        "total_questions": total,
        "total_correct": correct,
        "total_wrong": wrong,
        "accuracy": accuracy,
        "total_sessions": total_sessions,
        "study_minutes": study_minutes,
        "mastered_count": mastered,
        "weak_count": len(weak),
        "due_review_count": due_now,
        "today_questions": today_questions,
    }


def get_daily_trend(user_id: str = DEFAULT_USER_ID, days: int = 30) -> list[dict]:
    """
    每日练习趋势。

    返回:
        [{date: "2026-06-01", count: 5, correct: 3, wrong: 2, minutes: 10.5}, ...]
    """
    from app.db.database import get_db
    db = get_db()

    since = (datetime.now() - timedelta(days=days)).isoformat()

    rows = db.fetchall(
        """SELECT DATE(created_at) as day,
                  COUNT(*) as count,
                  SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
                  SUM(CASE WHEN is_wrong THEN 1 ELSE 0 END) as wrong,
                  SUM(time_spent_seconds) as seconds
           FROM practice_attempts
           WHERE user_id = %s AND created_at >= %s
           GROUP BY DATE(created_at)
           ORDER BY day""",
        (user_id, since),
    )

    trend = []
    for r in rows:
        trend.append({
            "date": str(r["day"]),
            "count": r["count"] or 0,
            "correct": r["correct"] or 0,
            "wrong": r["wrong"] or 0,
            "minutes": round((r["seconds"] or 0) / 60, 1),
        })

    # 填充空白日
    filled = []
    for i in range(days):
        d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        existing = next((t for t in trend if t["date"] == d), None)
        filled.append(existing or {
            "date": d, "count": 0, "correct": 0, "wrong": 0, "minutes": 0,
        })

    return filled


def get_session_history(user_id: str = DEFAULT_USER_ID, limit: int = 10) -> list[dict]:
    """
    最近练习会话历史。

    返回:
        [{session_id, mode, status, total, correct, score, duration, date}, ...]
    """
    from app.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        """SELECT id, mode, status, total_count, correct_count, wrong_count,
                  score, duration_seconds, created_at
           FROM practice_sessions
           WHERE user_id = %s
           ORDER BY created_at DESC LIMIT %s""",
        (user_id, limit),
    )

    result = []
    for r in rows:
        result.append({
            "session_id": r["id"],
            "mode": r["mode"],
            "status": r["status"],
            "total": r["total_count"],
            "correct": r.get("correct_count", 0),
            "wrong": r.get("wrong_count", 0),
            "score": r.get("score"),
            "duration_seconds": r.get("duration_seconds"),
            "date": _safe_iso(r.get("created_at")),
        })

    return result


def get_error_distribution(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """错题分布（按错误次数分组）"""
    from app.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        """SELECT question_id, q.stem as stem_abbr,
                  COUNT(*) as total,
                  SUM(CASE WHEN is_wrong THEN 1 ELSE 0 END) as wrongs
           FROM practice_attempts att
           LEFT JOIN questions q ON att.question_id = q.id
           WHERE att.user_id = %s
           GROUP BY att.question_id, q.stem
           ORDER BY wrongs DESC
           LIMIT 20""",
        (user_id,),
    )

    return [
        {
            "question_id": r["question_id"],
            "stem": (r["stem_abbr"] or "")[:60],
            "total_attempts": r["total"] or 0,
            "wrong_count": r["wrongs"] or 0,
        }
        for r in rows
    ]


def get_weak_skills(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """从 cognitive_nodes 获取薄弱知识点"""
    from app.cognitive.storage import get_nodes_by_level
    atoms = get_nodes_by_level("atom", user_id) or []

    weak = []
    for n in atoms:
        pm = n.belief.proficiency_mean
        if pm < 0.6:  # 掌握度低于 60%
            weak.append({
                "skill_id": n.id,
                "label": n.label or n.id,
                "mastery": round(pm, 3),
                "attempts": n.practice_summary.total_attempts,
                "trend": n.trend.direction if n.trend else "stable",
                "load": round(n.cognitive_load.intrinsic, 2) if n.cognitive_load else 0,
            })

    weak.sort(key=lambda x: x["mastery"])
    return weak


def _safe_iso(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)
