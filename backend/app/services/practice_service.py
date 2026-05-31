"""
Practice 业务逻辑服务层

从 practice.py 路由提取的共享业务逻辑：
- 认知节点更新（CognitiveNode 后练习更新）
- 练习统计计算
- 行为报告数据聚合
- 错题本操作
- 提示逻辑
- 日期解析工具
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from shared.constants import DEFAULT_USER_ID, get_mastery_label
from app.core.knowledge_trace import get_cognitive_state, get_all_cognitive_states
from app.db.database import get_db

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 日期工具
# ═══════════════════════════════════════════


def _dt(v, now=None):
    """将值转为 datetime"""
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
    """将值转为 ISO 格式字符串"""
    d = _dt(v)
    return d.isoformat() if isinstance(d, datetime) else str(d)


# ═══════════════════════════════════════════
# CognitiveNode 练习后更新
# ═══════════════════════════════════════════


def get_cognitive_proficiency(user_id: str, skill_id: str) -> float | None:
    """从 CognitiveNode 读取掌握度"""
    try:
        from app.cognitive.storage import get_node
        node = get_node(skill_id, user_id)
        if node and node.belief:
            return round(node.belief.proficiency_mean, 4)
    except Exception:
        logger.debug("CognitiveNode 掌握度查询失败，返回 None")
    return None


def update_cognitive_after_practice(
    user_id: str,
    skill_id: str,
    is_correct: bool,
    latency_ms: int = 0,
) -> dict:
    """练习后更新 CognitiveNode 并发布事件

    返回 {"p_before": float, "p_after": float, "mastery_label": str}
    """
    state = get_cognitive_state(user_id, skill_id)
    p_before = state.p_known
    p_after = p_before

    # 更新 CognitiveNode
    try:
        from app.cognitive.events import submit_practice
        submit_practice(
            user_id=user_id,
            node_id=skill_id,
            success=is_correct,
            latency_ms=latency_ms,
            consecutive=True,
        )
    except Exception as e:
        logger.warning("CognitiveNode submit_practice failed: %s", e)

    # 读取更新后的 p_after
    try:
        from app.cognitive.storage import get_node as _get_node
        _updated = _get_node(skill_id, user_id)
        if _updated and _updated.belief:
            p_after = _updated.belief.proficiency_mean
    except Exception:
        p_after = p_before

    # 发布 CognitiveNodeUpdated 事件
    try:
        from shared.events import CognitiveNodeUpdated
        from app.application.di import container
        import asyncio
        asyncio.create_task(container.event_bus.publish(CognitiveNodeUpdated(
            user_id=user_id,
            node_id=skill_id,
            label=skill_id,
            level="atom",
            proficiency_before=p_before,
            proficiency_after=p_after,
            update_type="practice",
        )))
    except Exception as e:
        logger.warning("CognitiveNodeUpdated event publish failed: %s", e)

    return {
        "p_before": p_before,
        "p_after": p_after,
        "mastery_label": get_mastery_label(p_after, 1),
        "cognitive_proficiency": get_cognitive_proficiency(user_id, skill_id),
    }


# ═══════════════════════════════════════════
# 答案校验
# ═══════════════════════════════════════════


def check_answer(user_answer: str, correct_answer: str) -> bool:
    """标准化比较答案"""
    return user_answer.strip().upper() == correct_answer.strip().upper()


def build_reply_text(is_correct: bool, correct_label: str, explanation: str) -> str:
    """构建内联回复文本"""
    if is_correct:
        return f"✅ 正确！{explanation}" if explanation else "✅ 正确！"
    else:
        base = f"❌ 不对哦。正确答案是 **{correct_label}**"
        return f"{base}。{explanation}" if explanation else f"{base}。"


# ═══════════════════════════════════════════
# 提示逻辑
# ═══════════════════════════════════════════


def get_hint_for_question(question_id: str, current_level: int) -> dict:
    """获取题目提示（逐级提示 → 最终解释）"""
    db = get_db()
    row = db.fetchone("SELECT * FROM questions WHERE question_id = %s", (question_id,))
    if not row:
        return None

    hints = row.get("hints_json")
    if isinstance(hints, str):
        hints = json.loads(hints)
    if not isinstance(hints, list):
        hints = []
    explanation = row["explanation"]

    level = current_level + 1

    if level <= len(hints):
        text = hints[level - 1]
        hint_type = "direction"
    else:
        text = explanation
        hint_type = "full"

    return {
        "hint": {"level": level, "text": text, "type": hint_type},
        "next_level_available": level < 4,
    }


def get_inline_hint(block_id: str) -> dict:
    """获取内联提示"""
    from app.services.storage import storage

    data = storage.load(DEFAULT_USER_ID)
    block = data.response_blocks.get(block_id)
    if not block:
        return None

    content = block.content or {}
    hint_text = content.get("hint", "再仔细想想题意，分析每个选项的差异。")
    hint_level = content.get("hint_level", 1)

    return {
        "hint_text": hint_text,
        "level": hint_level + 1 if isinstance(hint_level, (int, float)) else 2,
    }


# ═══════════════════════════════════════════
# 错题本操作
# ═══════════════════════════════════════════


def query_error_book(
    user_id: str = DEFAULT_USER_ID,
    resolved: Optional[bool] = None,
    skill_id: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """查询错题本（支持过滤）"""
    db = get_db()
    conditions = ["user_id = %s"]
    params = [user_id]
    if resolved is not None:
        conditions.append("is_resolved = %s")
        params.append(resolved)
    if skill_id:
        conditions.append("skill_id = %s")
        params.append(skill_id)
    sql = f"SELECT * FROM error_book WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    total = db.fetchone("SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s", (user_id,))
    unresolved = db.fetchone(
        "SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s AND is_resolved = FALSE",
        (user_id,),
    )
    return {
        "entries": [dict(r) for r in rows],
        "total": total["cnt"] if total else 0,
        "unresolved_count": unresolved["cnt"] if unresolved else 0,
    }


def review_error_entry(entry_id: str, is_correct: bool = True) -> Optional[dict]:
    """复习错题，返回更新结果（None 表示未找到）"""
    db = get_db()
    entry = db.fetchone("SELECT * FROM error_book WHERE entry_id = %s", (entry_id,))
    if not entry:
        return None
    new_count = entry["review_count"] + 1
    db.execute(
        "UPDATE error_book SET review_count = %s, is_resolved = %s WHERE entry_id = %s",
        (new_count, is_correct, entry_id),
    )
    return {"entry_id": entry_id, "review_count": new_count, "is_resolved": is_correct}


async def analyze_error_entry(entry_id: str) -> Optional[dict]:
    """LLM 深度分析单条错题，返回 {"entry_id": ..., "attribution": ...}"""
    from app.services.error_attribution import analyze_error

    db = get_db()
    entry = db.fetchone("SELECT * FROM error_book WHERE entry_id = %s", (entry_id,))
    if not entry:
        return None
    entry = dict(entry)

    # 已有归因则直接返回
    attribution = entry.get("attribution")
    if attribution:
        if isinstance(attribution, str):
            attribution = json.loads(attribution)
        return {"entry_id": entry_id, "attribution": attribution}

    # LLM 分析
    result = await analyze_error(
        question_text=entry.get("question_text", ""),
        user_answer=entry.get("user_answer", ""),
        correct_answer=entry.get("correct_answer", ""),
        error_type=entry.get("error_type", ""),
        skill_id=entry.get("skill_id", ""),
    )

    # 存入数据库
    db.execute(
        "UPDATE error_book SET attribution = %s WHERE entry_id = %s",
        (json.dumps(result, ensure_ascii=False), entry_id),
    )

    return {"entry_id": entry_id, "attribution": result}


def get_error_attribution_stats(user_id: str = DEFAULT_USER_ID) -> dict:
    """错因分布统计"""
    from app.services.error_attribution import get_error_stats

    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM error_book WHERE user_id = %s AND is_resolved = FALSE",
        (user_id,),
    )
    entries = [dict(r) for r in rows]
    return get_error_stats(entries)


# ═══════════════════════════════════════════
# 会话管理
# ═══════════════════════════════════════════


def list_practice_sessions(user_id: str = DEFAULT_USER_ID, limit: int = 20) -> dict:
    """列出用户的所有练习会话"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s ORDER BY started_at DESC LIMIT %s",
        (user_id, limit),
    )
    return {"sessions": [dict(r) for r in rows], "total": len(rows)}


def complete_practice_session(session_id: str) -> Optional[dict]:
    """完成会话，返回会话数据 + 统计。None 表示未找到。"""
    db = get_db()
    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE session_id = %s", (session_id,)
    )
    if not session:
        return None

    db.execute(
        "UPDATE practice_sessions SET status = 'completed', completed_at = NOW() WHERE session_id = %s",
        (session_id,),
    )
    session["status"] = "completed"

    # 计算准确率
    total = session.get("question_count", len(session.get("question_ids", [])))
    correct = session.get("correct_count", 0)
    accuracy = correct / total if total > 0 else 0

    # 获取薄弱知识点
    attempts = db.fetchall(
        "SELECT skill_id, is_correct FROM practice_attempts WHERE session_id = %s AND is_correct = false",
        (session_id,),
    )
    struggling = list(set(a["skill_id"] for a in attempts)) if attempts else []

    return {
        "session": session,
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "struggling": struggling,
    }


def record_attempt(
    user_id: str,
    session_id: str,
    question_id: str,
    answer: str,
    is_correct: bool,
    time_spent_seconds: float,
    hints_used: int,
) -> None:
    """记录一次答题到 attempts 表"""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO attempts (user_id, session_id, question_id, answer, is_correct, time_spent, hints_used, submitted_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, session_id, question_id, answer,
             is_correct, time_spent_seconds, hints_used, datetime.now().isoformat()),
        )
    except Exception:
        logger.debug("Failed to record attempt")


# ═══════════════════════════════════════════
# 练习统计计算
# ═══════════════════════════════════════════


def compute_practice_stats(time_range: str = "week", user_id: str = DEFAULT_USER_ID) -> dict:
    """计算练习统计（overview + daily_trend + mastery_bars + error_distribution + heatmap）"""
    db = get_db()
    now = datetime.now()

    days_back = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
    prev_days_back = days_back * 2
    cutoff = (now - timedelta(days=days_back)).isoformat()
    prev_start = (now - timedelta(days=prev_days_back)).isoformat()
    prev_end = cutoff

    rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
        (user_id, cutoff),
    )
    total = len(rows)
    correct = sum(1 for r in rows if r.get("is_correct"))
    accuracy = correct / total if total > 0 else 0.0

    sess_rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
        (user_id, cutoff),
    )
    study_minutes = sum(r.get("estimated_minutes", 0) for r in sess_rows)
    study_days = len(
        set(r["started_at"].isoformat()[:10] for r in sess_rows if r.get("started_at"))
    )

    prev_rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s AND submitted_at < %s",
        (user_id, prev_start, prev_end),
    )
    prev_total = len(prev_rows)
    prev_correct = sum(1 for r in prev_rows if r.get("is_correct"))
    prev_accuracy = prev_correct / prev_total if prev_total > 0 else 0.0
    prev_sess = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s AND started_at < %s",
        (user_id, prev_start, prev_end),
    )
    prev_minutes = sum(r.get("estimated_minutes", 0) for r in prev_sess)
    prev_days = len(
        set(r["started_at"].isoformat()[:10] for r in prev_sess if r.get("started_at"))
    )

    error_dist = {}
    for r in rows:
        if not r.get("is_correct") and r.get("error_type"):
            et = r["error_type"]
            error_dist[et] = error_dist.get(et, 0) + 1

    skill_states = get_all_cognitive_states(user_id)
    mastery_bars = sorted(
        [
            {
                "skill_id": sid,
                "p_known": round(s.p_known, 2),
                "mastery_level": get_mastery_label(s.p_known, s.attempt_count),
                "attempt_count": s.attempt_count,
                "correct_count": s.correct_count,
            }
            for sid, s in skill_states.items()
            if s.attempt_count > 0
        ],
        key=lambda x: x["p_known"],
    )

    daily_trend = []
    for i in range(days_back - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_rows = [r for r in rows if _ds(r.get("submitted_at"))[:10] == day]
        dt = len(day_rows)
        dc = sum(1 for r in day_rows if r.get("is_correct"))
        daily_trend.append(
            {
                "date": day[-5:],
                "questions": dt,
                "correct": dc,
                "accuracy": round(dc / dt, 2) if dt > 0 else 0.0,
            }
        )

    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    hourly_heatmap = []
    for day_idx in range(7):
        for hour in [8, 10, 14, 16, 20, 22]:
            count = sum(
                1
                for r in rows
                if r.get("submitted_at")
                and _dt(r.get("submitted_at")).weekday() == day_idx
                and _dt(r.get("submitted_at")).hour == hour
            )
            hourly_heatmap.append(
                {
                    "day": day_idx + 1,
                    "day_name": day_names[day_idx],
                    "hour": hour,
                    "questions": count,
                }
            )

    error_dist_list = [
        {
            "type": et,
            "count": cnt,
            "pct": round(cnt / sum(error_dist.values()), 2) if error_dist else 0,
        }
        for et, cnt in sorted(error_dist.items(), key=lambda x: -x[1])
    ]

    return {
        "user_id": user_id,
        "time_range": time_range,
        "overview": {
            "total_questions": total,
            "accuracy": round(accuracy, 2),
            "study_days": study_days,
            "study_minutes": round(study_minutes, 1),
            "prev_week": {
                "total_questions": prev_total,
                "accuracy": round(prev_accuracy, 2),
                "study_days": prev_days,
                "study_minutes": round(prev_minutes, 1),
            },
        },
        "daily_trend": daily_trend,
        "mastery_bars": mastery_bars,
        "error_distribution": error_dist_list,
        "hourly_heatmap": hourly_heatmap,
    }


# ═══════════════════════════════════════════
# 行为报告数据聚合
# ═══════════════════════════════════════════


def compute_behavior_report_data(
    time_range: str = "week", user_id: str = DEFAULT_USER_ID
) -> dict:
    """聚合行为报告所需数据，返回 dict 供 behavior_analyzer / habit_formation 消费"""
    from app.services.behavior_analyzer import behavior_analyzer
    from app.services.habit_formation import habit_formation

    now = datetime.now()
    days_back = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
    cutoff = now - timedelta(days=days_back)
    cutoff_str = cutoff.isoformat()

    db = get_db()
    session_rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
        (user_id, cutoff_str),
    )
    attempt_rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
        (user_id, cutoff_str),
    )

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
                if a.get("submitted_at")
                and _dt(a["submitted_at"]).weekday() == day_idx
                and _dt(a["submitted_at"]).hour == hour
            )
            hourly_heatmap.append({
                "day": day_idx + 1, "day_name": day_names[day_idx],
                "hour": hour, "questions": count,
            })

    skill_states = get_all_cognitive_states(user_id)
    mastery_bars = sorted(
        [
            {
                "skill_id": sid,
                "p_known": round(s.p_known, 2),
                "mastery_level": get_mastery_label(s.p_known, s.attempt_count),
                "attempt_count": s.attempt_count,
                "correct_count": s.correct_count,
            }
            for sid, s in skill_states.items()
            if s.attempt_count > 0
        ],
        key=lambda x: x["p_known"],
    )

    total_sessions = len(session_rows)
    total_minutes = sum(r.get("estimated_minutes", 0) for r in session_rows)
    study_days = len(
        set(_ds(r.get("started_at"))[:10] for r in session_rows if r.get("started_at"))
    )

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
