"""练习系统API v2.0
端点：题目生成、会话管理、答题提交、统计查询
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.shared.constants import DEFAULT_USER_ID
from app.core.knowledge_trace import bkt_engine, get_cognitive_state, get_all_cognitive_states


def _get_cognitive_proficiency(user_id: str, skill_id: str) -> float | None:
    """从 CognitiveNode 读取掌握度（Phase 6 联动）"""
    try:
        from app.cognitive.storage import get_node
        node = get_node(skill_id, user_id)
        if node and node.belief:
            return round(node.belief.proficiency_mean, 4)
    except Exception:
        logger.debug("CognitiveNode 掌握度查询失败，返回 None")
    return None
from app.schemas.practice import (
    BloomLevel,
    Question,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/practice", tags=["practice"])

# PostgreSQL 数据库（替代内存存储）
from app.db.database import get_db
_db = get_db()  # 启动时初始化（main.py lifespan 已调用）


# 请求/响应模型

class GenerateQuestionRequest(BaseModel):
    subject: str = "数学"
    skill_id: str = ""
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    difficulty: float = 0.5
    count: int = 5
    content_type: str = "choice"
    material_ids: Optional[list[str]] = None  # 从用户资料生成


class HintRequest(BaseModel):
    question_id: str
    current_level: int = 0


# 题目管理

from app.services.question_generator import get_question_generator, QuestionGenerator


def _generate_questions(
    generator: QuestionGenerator,
    skill_id: str,
    subject: str,
    bloom_level: BloomLevel,
    difficulty: float,
    count: int,
) -> list[Question]:
    """使用LLM生成题目"""
    return generator.generate(
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type="choice",
    )


@router.post("/questions/generate")
async def generate_questions(req: GenerateQuestionRequest):
    """生成练习题（使用LLM）"""
    from app.services.llm_service import LLMService
    llm_service = LLMService()
    generator = get_question_generator(llm_service)
    
    questions = _generate_questions(
        generator,
        skill_id=req.skill_id,
        subject=req.subject,
        bloom_level=req.bloom_level,
        difficulty=req.difficulty,
        count=req.count,
    )

    # 存入数据库
    from app.db.database import get_db
    db = get_db()
    for q in questions:
        db.upsert("questions", {
            "question_id": q.question_id,
            "skill_id": q.skill_id,
            "subject": q.subject,
            "bloom_level": q.bloom_level.value if hasattr(q.bloom_level, 'value') else str(q.bloom_level),
            "text": q.text,
            "options_json": [o.model_dump() for o in q.options] if q.options else [],
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "hints_json": q.hints or [],
            "difficulty": q.difficulty,
            "answer_type": q.answer_type.value if hasattr(q.answer_type, 'value') else str(q.answer_type),
            "source": q.source,
            "tags_json": q.tags,
            "quality_score": q.quality_score,
            "status": "active",
        }, "question_id")

    return {
        "questions": [q.model_dump() for q in questions],
        "count": len(questions),
    }


@router.get("/questions")
async def get_questions(
    subject: Optional[str] = None,
    skill_id: Optional[str] = None,
    bloom_level: Optional[BloomLevel] = None,
    limit: int = 20,
):
    """获取题目列表"""
    from app.db.database import get_db
    db = get_db()

    conditions = ["status = 'active'"]
    params: list = []
    if subject:
        conditions.append("subject = %s"); params.append(subject)
    if skill_id:
        conditions.append("skill_id = %s"); params.append(skill_id)
    if bloom_level:
        conditions.append("bloom_level = %s"); params.append(bloom_level.value)
    sql = f"SELECT * FROM questions WHERE {' AND '.join(conditions)} LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))

    questions = []
    for r in rows:
        q = {
            "question_id": r["question_id"], "skill_id": r["skill_id"],
            "subject": r["subject"], "bloom_level": r["bloom_level"],
            "text": r["text"],
            "options": r.get("options_json") if isinstance(r.get("options_json"), list) else (json.loads(r["options_json"]) if isinstance(r.get("options_json"), str) else []),
            "correct_answer": r["correct_answer"], "explanation": r["explanation"],
            "hints": r.get("hints_json") if isinstance(r.get("hints_json"), list) else (json.loads(r["hints_json"]) if isinstance(r.get("hints_json"), str) else []),
            "difficulty": r["difficulty"], "answer_type": r["answer_type"],
            "source": r["source"], "status": r["status"],
        }
        questions.append(q)

    return {"questions": questions, "total": len(rows)}


@router.get("/sessions")
async def list_sessions(user_id: str = DEFAULT_USER_ID, limit: int = 20):
    """列出用户的所有会话"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s ORDER BY started_at DESC LIMIT %s",
        (user_id, limit),
    )
    return {"sessions": [dict(r) for r in rows], "total": len(rows)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    db = get_db()
    row = db.fetchone("SELECT * FROM practice_sessions WHERE session_id = %s", (session_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": dict(row)}


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    user_id: str = DEFAULT_USER_ID,
    partition_id: str | None = None,
    branch_id: str | None = None,
):
    """结束会话（如果有对话上下文，写入branch）"""
    db = get_db()
    session = db.fetchone("SELECT * FROM practice_sessions WHERE session_id = %s", (session_id,))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.execute("UPDATE practice_sessions SET status = 'completed', completed_at = NOW() WHERE session_id = %s", (session_id,))
    session["status"] = "completed"

    # 计算准确率
    total = session.get("question_count", len(session.get("question_ids", [])))
    correct = session.get("correct_count", 0)
    accuracy = correct / total if total > 0 else 0

    # 获取薄弱知识点
    attempts = db.fetchall(
        "SELECT skill_id, is_correct FROM practice_attempts WHERE session_id = %s AND is_correct = false",
        (session_id,)
    )
    struggling = list(set(a["skill_id"] for a in attempts)) if attempts else []

    # 写入对话branch
    if partition_id and branch_id:
        try:
            from app.services.practice_integrator import integrate_practice_to_branch
            from app.schemas.practice import PracticeSession
            from datetime import datetime as dt

            ps = PracticeSession(
                user_id=user_id,
                question_ids=session.get("question_ids", []),
                planned_skills=session.get("planned_skills", []),
                correct_count=correct,
                started_at=session.get("created_at", dt.now()),
                completed_at=dt.now(),
            )
            await integrate_practice_to_branch(user_id, ps, partition_id, branch_id)
        except Exception as e:
            logger.warning(f"练习结果写入branch失败: {e}")

    # P0: 同步到统一知识状态
    try:
        from app.services.knowledge_bridge import knowledge_bridge
        planned_skills = session.get("planned_skills", [])
        correct_skills = [
            a["skill_id"] for a in db.fetchall(
                "SELECT DISTINCT skill_id FROM practice_attempts WHERE session_id = %s AND is_correct = true",
                (session_id,)
            )
        ] if db else []
        await knowledge_bridge.sync_from_practice_session(
            skills_tested=planned_skills,
            accuracy=accuracy,
            correct_skills=correct_skills,
            struggling_skills=struggling,
        )
    except Exception as e:
        logger.warning(f"同步统一知识状态失败: {e}")

    # Phase 4C: 发布 SessionCompleted 事件
    try:
        from shared.events import SessionCompleted
        from app.application.di import container
        import asyncio
        event = SessionCompleted(
            user_id=user_id,
            session_id=session_id,
            total_questions=total,
            correct_count=correct,
            accuracy=accuracy,
            duration_minutes=session.get("estimated_minutes", 0),
        )
        asyncio.create_task(container.event_bus.publish(event))
    except Exception:
        logger.debug("SessionCompleted 事件发布失败", exc_info=True)

    return {
        "session": session,
        "accuracy": accuracy,
        "struggling_skills": struggling,
    }


@router.post("/hint")
async def get_hint(req: HintRequest):
    """获取提示"""
    db = get_db()
    row = db.fetchone("SELECT * FROM questions WHERE question_id = %s", (req.question_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")

    import json
    hints = row.get("hints_json")
    if isinstance(hints, str):
        hints = json.loads(hints)
    if not isinstance(hints, list):
        hints = []
    explanation = row["explanation"]

    level = req.current_level + 1

    if level == 0:
        text = "试着自己想想看 💪"
        hint_type = "encouragement"
    elif level <= len(hints):
        text = hints[level - 1]
        hint_type = "direction"
    else:
        text = explanation
        hint_type = "full"

    return {
        "hint": {"level": level, "text": text, "type": hint_type},
        "next_level_available": level < 4,
    }


# ──────────────────────────────────────────────
# 对话内联练习（Inline Practice）
# 从 response_block 内容直接校验答案
# ──────────────────────────────────────────────


class InlineAnswerRequest(BaseModel):
    block_id: str
    answer: str


class InlineHintRequest(BaseModel):
    block_id: str


@router.post("/inline/answer")
async def inline_answer(req: InlineAnswerRequest):
    """对话内联练习 — 提交答案，读取 response_block 内容校验"""
    from app.services.storage import storage

    data = storage.load(DEFAULT_USER_ID)
    block = data.response_blocks.get(req.block_id)
    if not block:
        raise HTTPException(404, "Practice block not found")

    content = block.content or {}
    correct_answer = content.get("correct_answer", "").strip().upper()
    explanation = content.get("explanation") or content.get("reply_expected", "") or ""
    content.get("question_id", "")
    skill_id = content.get("skill_id", "")

    is_correct = req.answer.strip().upper() == correct_answer

    # 更新知识状态
    if skill_id:
        state = get_cognitive_state(DEFAULT_USER_ID, skill_id)
        # CognitiveNode
        try:
            from app.cognitive.events import submit_practice
            submit_practice(user_id=DEFAULT_USER_ID, node_id=skill_id, success=is_correct, latency_ms=0, consecutive=True)
        except Exception:
            pass
        knowledge_update = {
            "skill_id": skill_id,
            "p_known_before": state.p_known,
            "mastery_level": bkt_engine.get_mastery_level(state),
            "cognitive_proficiency": _get_cognitive_proficiency(DEFAULT_USER_ID, skill_id),
        }
    else:
        knowledge_update = {}

    # 回复文本
    if is_correct:
        reply_text = f"✅ 正确！{explanation}" if explanation else "✅ 正确！"
    else:
        correct_label = content.get("correct_answer", "")
        reply_text = f"❌ 不对哦。正确答案是 **{correct_label}**。{explanation}" if explanation else f"❌ 不对哦。正确答案是 **{correct_label}**。"

    return {
        "is_correct": is_correct,
        "reply_text": reply_text,
        "knowledge_update": knowledge_update,
    }


@router.post("/inline/hint")
async def inline_hint(req: InlineHintRequest):
    """对话内联练习 — 获取提示"""
    from app.services.storage import storage

    data = storage.load(DEFAULT_USER_ID)
    block = data.response_blocks.get(req.block_id)
    if not block:
        raise HTTPException(404, "Practice block not found")

    content = block.content or {}
    hint_text = content.get("hint", "再仔细想想题意，分析每个选项的差异。")
    hint_level = content.get("hint_level", 1)

    return {
        "hint_text": hint_text,
        "level": hint_level + 1 if isinstance(hint_level, (int, float)) else 2,
    }


# ──────────────────────────────────────────────
# 错题本（增强）
# ──────────────────────────────────────────────


@router.get("/errors")
async def get_error_book(
    resolved: Optional[bool] = None,
    skill_id: Optional[str] = None,
    limit: int = 20,
):
    """获取错题本"""
    db = get_db()
    conditions = ["user_id = %s"]
    params = [DEFAULT_USER_ID]
    if resolved is not None:
        conditions.append("is_resolved = %s"); params.append(resolved)
    if skill_id:
        conditions.append("skill_id = %s"); params.append(skill_id)
    sql = f"SELECT * FROM error_book WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    total = db.fetchone("SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s", (DEFAULT_USER_ID,))
    unresolved = db.fetchone("SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s AND is_resolved = FALSE", (DEFAULT_USER_ID,))
    return {"entries": [dict(r) for r in rows], "total": total["cnt"] if total else 0, "unresolved_count": unresolved["cnt"] if unresolved else 0}


@router.post("/errors/{entry_id}/review")
async def review_error(entry_id: str, is_correct: bool = True):
    """复习错题"""
    db = get_db()
    entry = db.fetchone("SELECT * FROM error_book WHERE entry_id = %s", (entry_id,))
    if not entry:
        raise HTTPException(status_code=404, detail="Error entry not found")
    new_count = entry["review_count"] + 1
    db.execute("UPDATE error_book SET review_count = %s, is_resolved = %s WHERE entry_id = %s", (new_count, is_correct, entry_id))
    return {"entry_id": entry_id, "review_count": new_count, "is_resolved": is_correct}


@router.get("/errors/due")
async def get_due_errors():
    """获取待复习错题"""
    db = get_db()
    rows = db.fetchall("SELECT * FROM error_book WHERE user_id = %s AND is_resolved = FALSE ORDER BY created_at LIMIT 10", (DEFAULT_USER_ID,))
    return {"due": [dict(r) for r in rows], "total_due": len(rows)}


@router.post("/errors/{entry_id}/analyze")
async def analyze_error_entry(entry_id: str):
    """LLM 深度分析单条错题的错因"""
    from app.services.error_attribution import analyze_error

    db = get_db()
    entry = db.fetchone(
        "SELECT * FROM error_book WHERE entry_id = %s", (entry_id,)
    )
    if not entry:
        raise HTTPException(404, "错题记录不存在")
    entry = dict(entry)

    # 已有归因则直接返回
    attribution = entry.get("attribution")
    if attribution:
        if isinstance(attribution, str):
            import json as _json
            attribution = _json.loads(attribution)
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
    import json as _json
    db.execute(
        "UPDATE error_book SET attribution = %s WHERE entry_id = %s",
        (_json.dumps(result, ensure_ascii=False), entry_id),
    )

    return {"entry_id": entry_id, "attribution": result}


@router.get("/errors/stats")
async def get_error_attribution_stats():
    """错因分布统计"""
    from app.services.error_attribution import get_error_stats

    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM error_book WHERE user_id = %s AND is_resolved = FALSE",
        (DEFAULT_USER_ID,),
    )
    entries = [dict(r) for r in rows]
    stats = get_error_stats(entries)
    return stats


# ──────────────────────────────────────────────
# 统计 + 行为分析
# ──────────────────────────────────────────────

from app.services.behavior_analyzer import behavior_analyzer
from app.services.habit_formation import habit_formation


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
    user_id = DEFAULT_USER_ID
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

    skill_states = get_all_cognitive_states(user_id)
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
    user_id = DEFAULT_USER_ID
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

    skill_states = get_all_cognitive_states(user_id)
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


# ──────────────────────────────────────────────
# 题目质量监控
# ──────────────────────────────────────────────


@router.get("/quality")
async def get_quality_summary():
    """获取全量质量摘要"""
    from app.services.quality_analyzer import quality_analyzer
    summary = quality_analyzer.analyze_all()
    return summary.to_dict()


@router.get("/quality/worst")
async def get_worst_questions(limit: int = 10):
    """获取质量最差的题目列表"""
    from app.services.quality_analyzer import quality_analyzer
    db = get_db()
    rows = db.fetchall("SELECT question_id FROM questions WHERE status != 'retired'")
    results = []
    for r in rows:
        q = quality_analyzer.analyze_question(r["question_id"])
        if q and q.total_attempts >= quality_analyzer.MIN_ATTEMPTS:
            results.append(q)
    results.sort(key=lambda r: r.quality_score)
    worst = results[:limit]
    return {
        "worst": [r.to_dict() for r in worst],
        "total_analyzed": len(results),
        "threshold": quality_analyzer.MIN_ATTEMPTS,
    }


@router.post("/quality/apply")
async def apply_quality_actions(dry_run: bool = True):
    """执行质量分析建议动作"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.apply_actions(dry_run=dry_run)
    return result


@router.get("/quality/detail/{question_id}")
async def get_question_quality(question_id: str):
    """获取单题质量分析（精确 path，避免与 /stats /errors 等潜在冲突）"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.analyze_question(question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return result.to_dict()


@router.get("/quality/{question_id}/distractors")
async def get_distractor_analysis(question_id: str):
    """获取单题的干扰项分析"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.analyze_question(question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {
        "question_id": question_id,
        "distractors": [d.to_dict() for d in result.distractors],
        "correct_answer": next(
            (d.option_letter for d in result.distractors if d.is_correct), ""
        ),
    }


# ──────────────────────────────────────────────
# 统一知识状态 API (SharedKnowledgeState)
# ──────────────────────────────────────────────

@router.get("/knowledge/state")
async def get_knowledge_state():
    """获取统一知识状态（练习BKT + 对话证据融合）"""
    from app.services.knowledge_bridge import knowledge_bridge
    return knowledge_bridge.get_all_skills_summary()


@router.get("/knowledge/skill/{skill_id}")
async def get_skill_knowledge(skill_id: str):
    """获取单个技能的详细知识状态"""
    from app.services.knowledge_bridge import knowledge_bridge
    detail = knowledge_bridge.get_skill_detail(skill_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found in knowledge state")
    return detail


@router.get("/knowledge/weak")
async def get_weak_skills(limit: int = 5):
    """获取薄弱技能列表（用于针对性推荐）"""
    from app.services.knowledge_bridge import knowledge_bridge
    return {
        "weak_skills": knowledge_bridge.get_weak_skills(limit),
        "mastered_skills": knowledge_bridge.get_mastered_skills(),
    }


class EvidenceRequest(BaseModel):
    skill_id: str
    evidence_type: str
    confidence: float = 0.5
    source_text: str = ""
    branch_id: str = ""


@router.post("/knowledge/evidence")
async def add_conversation_evidence(req: EvidenceRequest):
    """手动添加对话知识证据（用于前端或 cron 任务）"""
    from app.services.knowledge_bridge import knowledge_bridge
    from app.domain.learning.shared_knowledge import EvidenceType

    try:
        ev_type = EvidenceType(req.evidence_type)
    except ValueError:
        raise HTTPException(400, f"Invalid evidence_type: {req.evidence_type}")

    knowledge_bridge.state.add_conversation_evidence(
        skill_id=req.skill_id,
        evidence_type=ev_type,
        confidence=req.confidence,
        source_text=req.source_text,
        branch_id=req.branch_id,
    )
    return {"ok": True, "skill_id": req.skill_id, "evidence_type": req.evidence_type}
