"""
练习统计汇总

聚合来源:
- practice_attempts → 答题记录
- practice_sessions → 会话统计
- questions → 题库统计
- cognitive_nodes → 知识掌握度
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from shared.utils import safe_iso as _safe_iso

logger = logging.getLogger(__name__)


def get_overview(user_id: str) -> dict:
    """
    总体概览统计。

    返回:
        total_questions, total_correct, total_wrong, accuracy,
        total_sessions, study_minutes, mastered_count, weak_count,
        due_review_count, today_questions
    """
    from app.infrastructure.db.database import get_db
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
    from app.domain.cognitive import get_repo
    atoms = get_repo().get_nodes_by_level("atom", user_id) or []
    mastered = sum(1 for n in atoms if n.belief.proficiency_mean >= 0.8)
    weak = [n for n in atoms if 0 < n.belief.proficiency_mean < 0.4]

    # 待复习数量
    from app.services.practice.practice_scheduler import get_review_stats
    rev_stats = get_review_stats(user_id)
    due_now = rev_stats.get("due_now", 0)

    accuracy = round(correct / max(total, 1) * 100, 1)
    study_minutes = round(total_seconds / 60, 1)

    # 冷启动判断
    question_count = db.fetchone(
        "SELECT COUNT(*) as cnt FROM questions WHERE bank_id IN "
        "(SELECT id FROM question_banks WHERE user_id = %s)",
        (user_id,),
    )
    total_questions = question_count["cnt"] if question_count else 0

    if total_questions > 0 and total < 1:
        cold_start = True
        cold_start_hint = "选个题库开始你的第一次练习吧！"
    elif total < 5:
        cold_start = True
        cold_start_hint = "开始你的第一次练习吧！"
    else:
        cold_start = False
        cold_start_hint = ""

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
        "cold_start": cold_start,
        "cold_start_hint": cold_start_hint,
    }


def get_daily_trend(user_id: str, days: int = 30) -> list[dict]:
    """
    每日练习趋势。

    返回:
        [{date: "2026-06-01", count: 5, correct: 3, wrong: 2, minutes: 10.5}, ...]
    """
    from app.infrastructure.db.database import get_db
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


def get_session_history(user_id: str, limit: int = 10) -> list[dict]:
    """
    最近练习会话历史。

    返回:
        [{session_id, mode, status, total, correct, score, duration, date}, ...]
    """
    from app.infrastructure.db.database import get_db
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


def get_error_distribution(user_id: str) -> list[dict]:
    """错题分布（按错误次数分组）"""
    from app.infrastructure.db.database import get_db
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


def get_weak_skills(user_id: str) -> list[dict]:
    """从 cognitive_nodes 获取薄弱知识点"""
    from app.domain.cognitive import get_repo
    atoms = get_repo().get_nodes_by_level("atom", user_id) or []

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


def get_recommendations(user_id: str, limit: int = 5) -> dict:
    """
    综合推荐：基于用户薄弱点推荐练习内容。

    返回:
        weak_skills: 薄弱知识点
        due_questions: 待复习题目
        suggested_banks: 推荐练习的题库
        study_suggestions: 学习建议
    """
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_scheduler import get_due_questions, get_review_stats
    from app.services.practice.practice_question_bank import list_banks
    db = get_db()

    # 1. 薄弱知识点
    weak_skills = get_weak_skills(user_id)
    weak_skill_ids = [s["skill_id"] for s in weak_skills[:5]]

    # 2. 待复习题目
    due = get_due_questions(user_id, limit=limit)
    rev_stats = get_review_stats(user_id)

    # 3. 推荐题库（基于薄弱知识点的话题匹配）
    banks = list_banks(user_id) or []
    suggested_banks = []
    # 优先推荐有薄弱知识点题目的题库
    if weak_skill_ids:
        for b in banks[:5]:
            bank_questions = db.fetchone(
                """SELECT COUNT(*) as cnt FROM questions
                   WHERE bank_id = %s AND deleted_at IS NULL
                     AND cognitive_node_ids && %s""",
                (b["id"], weak_skill_ids),
            )
            if bank_questions and bank_questions["cnt"] > 0:
                suggested_banks.append({
                    "id": b["id"],
                    "name": b.get("name", ""),
                    "matching_questions": bank_questions["cnt"],
                })

    # 4. 学习建议
    suggestions = []
    if weak_skills:
        top_weak = weak_skills[0]
        suggestions.append(f"建议重点复习「{top_weak['label']}」，当前掌握度仅 {top_weak['mastery']*100:.0f}%")
    if rev_stats.get("due_now", 0) > 0:
        suggestions.append(f"有 {rev_stats['due_now']} 道题目待复习，及时复习可提升长期记忆效果")
    if suggested_banks:
        suggestions.append(f"推荐在「{suggested_banks[0]['name']}」中练习薄弱知识点")
    if not weak_skills and not due:
        suggestions.append("尝试 AI 出题探索新知识点，或开始一次自适应练习")

    return {
        "weak_skills": weak_skills[:5],
        "due_questions": due[:limit],
        "due_review_count": rev_stats.get("due_now", 0),
        "suggested_banks": suggested_banks[:3],
        "study_suggestions": suggestions,
        "total_weak": len(weak_skills),
    }


