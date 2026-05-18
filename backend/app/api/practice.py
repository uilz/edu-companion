"""
练习系统API v2.0
端点：题目生成、会话管理、答题提交、统计查询
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.core.knowledge_trace import bkt_engine
from app.schemas.practice import (
    AnswerType,
    AttemptRecord,
    BloomLevel,
    CoverageGap,
    DailyStat,
    ErrorAnalysis,
    ErrorBookEntry,
    ErrorType,
    Material,
    MaterialChunk,
    PracticeSession,
    PracticeStats,
    PracticeSessionPlan,
    Question,
    QuestionOption,
    ReviewTask,
    SessionStatus,
    SkillStat,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/practice", tags=["practice"])

# ── PostgreSQL 数据库（替代内存存储）──

from app.db.database import get_db
_db = get_db()  # 启动时初始化（main.py lifespan 已调用）


# ──────────────────────────────────────────────
# 请求/响应模型
# ──────────────────────────────────────────────

class GenerateQuestionRequest(BaseModel):
    subject: str = "数学"
    skill_id: str = ""
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    difficulty: float = 0.5
    count: int = 5
    content_type: str = "choice"
    material_ids: Optional[list[str]] = None  # 从用户资料生成


class CreateSessionRequest(BaseModel):
    subject: Optional[str] = None
    skill_ids: Optional[list[str]] = None
    duration_minutes: int = 30
    mode: str = "adaptive"  # adaptive/targeted/review/challenge/contextual


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str
    time_spent_seconds: float = 0.0
    hints_used: int = 0
    explanation_text: Optional[str] = None


class HintRequest(BaseModel):
    question_id: str
    current_level: int = 0


# ──────────────────────────────────────────────
# 题目管理
# ──────────────────────────────────────────────

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
            "options": r.get("options_json") if isinstance(r.get("options_json"), list) else (__import__("json").loads(r["options_json"]) if isinstance(r.get("options_json"), str) else []),
            "correct_answer": r["correct_answer"], "explanation": r["explanation"],
            "hints": r.get("hints_json") if isinstance(r.get("hints_json"), list) else (__import__("json").loads(r["hints_json"]) if isinstance(r.get("hints_json"), str) else []),
            "difficulty": r["difficulty"], "answer_type": r["answer_type"],
            "source": r["source"], "status": r["status"],
        }
        questions.append(q)

    return {"questions": questions, "total": len(rows)}


# ──────────────────────────────────────────────
# 练习会话
# ──────────────────────────────────────────────

@router.post("/sessions")
async def create_session(req: CreateSessionRequest):
    """创建练习会话（含前置知识卡控）"""
    user_id = "default_user"

    # 从数据库选题
    skill_ids = req.skill_ids or []
    if not skill_ids:
        db = get_db()
        rows = db.fetchall("SELECT DISTINCT skill_id FROM questions WHERE status = 'active' LIMIT 4")
        skill_ids = [r["skill_id"] for r in rows] if rows else []

    # ── 前置知识卡控 ──
    from domain.knowledge.checker import PrerequisiteChecker
    from domain.knowledge.prerequisites import ALL_PREREQUISITES
    from app.core.knowledge_trace import bkt_engine
    from app.services.storage import storage

    # 构造简易 PracticeService adapter（现有架构过渡方案）
    class _KnowledgeAdapter:
        async def get_knowledge_state(self, uid: str, sid: str):
            return bkt_engine.load_or_create(uid, sid).model_dump()

    checker = PrerequisiteChecker(_KnowledgeAdapter())
    blocked_skills: list[str] = []
    prerequisites_info: list[dict] = []

    for sid in skill_ids:
        result = await checker.can_practice(user_id, sid)
        if not result.can_practice:
            blocked_skills.append(sid)
            prerequisites_info.append({
                "skill_id": sid,
                "blocked_by": result.blocked,
                "reason": result.reason,
            })

    # 过滤掉被卡控的技能
    allowed_skills = [s for s in skill_ids if s not in blocked_skills]

    # 如果所有技能都被卡控
    if not allowed_skills and skill_ids:
        return {
            "blocked": True,
            "message": "当前知识基础不足以练习所选内容，建议先完成前置知识",
            "prerequisites": prerequisites_info,
            "session": None,
        }

    questions = []
    for sid in allowed_skills:
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM questions WHERE skill_id = %s AND status = 'active' ORDER BY difficulty LIMIT 3",
            (sid,),
        )
        questions.extend(dict(r) for r in rows)

    import uuid
    from datetime import datetime
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    db = get_db()
    db.upsert("practice_sessions", {
        "session_id": session_id,
        "user_id": user_id,
        "planned_skills_json": allowed_skills,
        "question_ids_json": [q["question_id"] for q in questions],
        "estimated_minutes": req.duration_minutes,
        "mode": req.mode,
        "status": "active",
        "started_at": now,
    }, "session_id")

    response_data = {
        "session": {"session_id": session_id, "question_ids": [q["question_id"] for q in questions],
                     "planned_skills": allowed_skills, "mode": req.mode, "status": "active"},
        "questions": [{"question_id": q["question_id"], "skill_id": q.get("skill_id",""),
                      "subject": q.get("subject",""), "bloom_level": q.get("bloom_level",""),
                      "text": q.get("text",""),
                      "options": q.get("options_json") if isinstance(q.get("options_json"), list) else [],
                      "correct_answer": q.get("correct_answer",""),
                      "explanation": q.get("explanation",""),
                      "hints": q.get("hints_json") if isinstance(q.get("hints_json"), list) else [],
                      "difficulty": q.get("difficulty",0.5)} for q in questions],
    }

    # 附上卡控信息
    if blocked_skills:
        response_data["prerequisites_info"] = prerequisites_info
        response_data["blocked_skills"] = blocked_skills

    return response_data


@router.get("/sessions")
async def list_sessions(user_id: str = "default_user", limit: int = 20):
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
async def complete_session(session_id: str, partition_id: str | None = None, branch_id: str | None = None):
    """结束会话（可选：写入对话branch）"""
    db = get_db()
    session = db.fetchone("SELECT * FROM practice_sessions WHERE session_id = %s", (session_id,))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.execute("UPDATE practice_sessions SET status = 'completed', completed_at = NOW() WHERE session_id = %s", (session_id,))
    session["status"] = "completed"

    result = {"session": session}
    # P1: 练习结果写入对话记忆（略，session dict 已不完整）
    return result


# ──────────────────────────────────────────────
# 答题与反馈
# ──────────────────────────────────────────────

@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest):
    """提交答案"""
    db = get_db()
    session = db.fetchone("SELECT * FROM practice_sessions WHERE session_id = %s", (req.session_id,))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 查找题目
    question_row = db.fetchone("SELECT * FROM questions WHERE question_id = %s", (req.question_id,))
    if not question_row:
        raise HTTPException(status_code=404, detail="Question not found")

    question = dict(question_row)

    # 判对错
    is_correct = req.answer.strip().upper() == question["correct_answer"].strip().upper()

    # 记录答题
    import uuid
    attempt_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    # 知识状态
    state = bkt_engine.load_or_create(session["user_id"], question["skill_id"])
    updated_state = bkt_engine.update(state, is_correct, hint_level=req.hints_used)
    bkt_engine.save_state(session["user_id"], updated_state)

    # 生成反馈
    import json
    options_list = question.get("options_json")
    if isinstance(options_list, str):
        options_list = json.loads(options_list)
    if not isinstance(options_list, list):
        options_list = []

    feedback = {
        "is_correct": is_correct,
        "correct_answer": question["correct_answer"],
        "explanation": question["explanation"],
        "knowledge_update": {
            "skill_id": question["skill_id"],
            "p_known_before": state.p_known,
            "p_known_after": updated_state.p_known,
            "mastery_level": bkt_engine.get_mastery_level(updated_state),
        },
    }

    # 错误时添加错因分析
    if not is_correct and options_list:
        chosen = next((o for o in options_list if o.get("letter", "").upper() == req.answer.upper()), None)
        if chosen and chosen.get("distractor_type"):
            feedback["error_analysis"] = {
                "type": "misconception",
                "distractor_type": chosen["distractor_type"],
                "suggestion": f"你选择了{chosen['letter']}，可能的原因是{chosen['distractor_type']}",
            }

    # 存 attempt 到数据库
    db.upsert("attempts", {
        "attempt_id": attempt_id,
        "user_id": session["user_id"],
        "question_id": req.question_id,
        "session_id": req.session_id,
        "user_answer": req.answer,
        "is_correct": is_correct,
        "time_spent_seconds": req.time_spent_seconds,
        "hints_used": req.hints_used,
        "explanation_text": req.explanation_text,
        "knowledge_before_json": {question["skill_id"]: state.p_known},
        "knowledge_after_json": {question["skill_id"]: updated_state.p_known},
        "started_at": now,
        "submitted_at": now,
    }, "attempt_id")

    # 更新 session correct_count
    if is_correct:
        db.execute(
            "UPDATE practice_sessions SET correct_count = correct_count + 1 WHERE session_id = %s",
            (req.session_id,),
        )
    else:
        # 记录到错题本（如果还没有）
        existing = db.fetchone(
            "SELECT entry_id FROM error_book WHERE user_id = %s AND question_id = %s AND is_resolved = FALSE",
            (session["user_id"], req.question_id),
        )
        if not existing:
            import uuid as _uuid
            db.upsert("error_book", {
                "entry_id": str(_uuid.uuid4()),
                "user_id": session["user_id"],
                "question_id": req.question_id,
                "skill_id": question["skill_id"],
                "error_type": feedback.get("error_analysis", {}).get("type", "careless"),
                "misconception": feedback.get("error_analysis", {}).get("distractor_type", ""),
                "user_answer": req.answer,
                "correct_answer": question["correct_answer"],
                "question_text": question["text"][:500],
                "review_count": 0,
                "is_resolved": False,
                "created_at": now,
            }, "entry_id")
            feedback["error_entry"] = "created"

    return feedback


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
    params = ["default_user"]
    if resolved is not None:
        conditions.append("is_resolved = %s"); params.append(resolved)
    if skill_id:
        conditions.append("skill_id = %s"); params.append(skill_id)
    sql = f"SELECT * FROM error_book WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    total = db.fetchone("SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s", ("default_user",))
    unresolved = db.fetchone("SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s AND is_resolved = FALSE", ("default_user",))
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
    rows = db.fetchall("SELECT * FROM error_book WHERE user_id = %s AND is_resolved = FALSE ORDER BY created_at LIMIT 10", ("default_user",))
    return {"due": [dict(r) for r in rows], "total_due": len(rows)}



# ──────────────────────────────────────────────
# 统计（增强）
# ──────────────────────────────────────────────


@router.get("/stats")
async def get_stats(time_range: str = "week"):
    """获取练习统计"""
    from datetime import datetime, timedelta
    db = get_db()
    user_id = "default_user"
    now = datetime.now()

    def _dt(v):
        """安全转换为 datetime"""
        if v is None: return now
        if isinstance(v, datetime): return v
        if isinstance(v, str): return datetime.fromisoformat(v)
        return now
    def _dt_str(v):
        """安全获取 ISO 字符串"""
        d = _dt(v)
        return d.isoformat() if isinstance(d, datetime) else str(d)

    days_back = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
    prev_days_back = days_back * 2
    cutoff = (now - timedelta(days=days_back)).isoformat()
    prev_start = (now - timedelta(days=prev_days_back)).isoformat()
    prev_end = cutoff

    # 当期 attempts
    rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
        (user_id, cutoff))
    total = len(rows)
    correct = sum(1 for r in rows if r.get("is_correct"))
    accuracy = correct / total if total > 0 else 0.0

    # 当期 sessions
    sess_rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
        (user_id, cutoff))
    study_minutes = sum(r.get("estimated_minutes", 0) for r in sess_rows)
    study_days = len(set(r["started_at"].isoformat()[:10] for r in sess_rows if r.get("started_at")))

    # 环比
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

    # 错因分布
    error_dist = {}
    for r in rows:
        if not r.get("is_correct") and r.get("error_type"):
            et = r["error_type"]
            error_dist[et] = error_dist.get(et, 0) + 1

    # 知识掌握度
    skill_states = bkt_engine.load_all_states(user_id)
    mastery_bars = sorted(
        [{"skill_id": sid, "p_known": round(s.p_known, 2),
          "mastery_level": bkt_engine.get_mastery_level(s),
          "attempt_count": s.attempt_count, "correct_count": s.correct_count}
         for sid, s in skill_states.items() if s.attempt_count > 0],
        key=lambda x: x["p_known"])

    # 每日趋势
    import json
    daily_trend = []
    for i in range(days_back - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_rows = [r for r in rows if _dt_str(r.get("submitted_at"))[:10] == day]
        dt = len(day_rows)
        dc = sum(1 for r in day_rows if r.get("is_correct"))
        daily_trend.append({"date": day[-5:], "questions": dt, "correct": dc,
                            "accuracy": round(dc/dt,2) if dt>0 else 0.0})

    # 时段热力图
    day_names = ["周一","周二","周三","周四","周五","周六","周日"]
    hourly_heatmap = []
    for day_idx in range(7):
        for hour in [8,10,14,16,20,22]:
            count = sum(1 for r in rows if r.get("submitted_at")
                       and _dt(r.get("submitted_at")).weekday()==day_idx
                       and _dt(r.get("submitted_at")).hour==hour)
            hourly_heatmap.append({"day": day_idx+1, "day_name": day_names[day_idx],
                                   "hour": hour, "questions": count})

    return {"user_id": user_id, "time_range": time_range,
            "overview": {"total_questions": total, "accuracy": round(accuracy,2),
                         "study_days": study_days, "study_minutes": round(study_minutes,1),
                         "prev_week": {"total_questions": prev_total, "accuracy": round(prev_accuracy,2),
                                       "study_days": prev_days, "study_minutes": round(prev_minutes,1)}},
            "daily_trend": daily_trend, "mastery_bars": mastery_bars,
            "error_distribution": [{"type": et, "count": cnt, "pct": round(cnt/sum(error_dist.values()),2)}
                                   for et, cnt in sorted(error_dist.items(), key=lambda x: -x[1])],
            "hourly_heatmap": hourly_heatmap}


@router.get("/behavior")
async def get_behavior_report(time_range: str = "week"):
    """
    学习行为分析报告：
    - 连续学习天数 (streak)
    - 最佳学习时段
    - 学习规律性评分
    - 疲劳曲线
    - 每日目标完成情况
    - 微习惯推荐
    - 番茄钟建议
    - 个性化行动建议
    """
    from datetime import datetime, timedelta
    from app.services.behavior_analyzer import behavior_analyzer
    from app.services.habit_formation import habit_formation

    user_id = "default_user"
    now = datetime.now()
    from datetime import datetime as dt_cls

    def _d(v):
        if v is None: return now
        if isinstance(v, dt_cls): return v
        if isinstance(v, str): return dt_cls.fromisoformat(v)
        return now

    def _ds(v):
        return _d(v).isoformat()

    days_back = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
    cutoff = now - timedelta(days=days_back)

    # 汇集当期数据（从 PostgreSQL）
    db = get_db()
    cutoff_str = cutoff.isoformat()
    session_rows = db.fetchall(
        "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
        (user_id, cutoff_str))
    attempt_rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
        (user_id, cutoff_str))

    # 今日数据
    today_str = now.strftime("%Y-%m-%d")
    today_attempts = [a for a in attempt_rows if _ds(a.get("submitted_at"))[:10] == today_str]
    today_questions = len(today_attempts)
    today_correct = sum(1 for a in today_attempts if a.get("is_correct"))
    today_accuracy = today_correct / today_questions if today_questions > 0 else 0.0

    # 构建分析器需要的输入
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
                if a.get("submitted_at") and _d(a["submitted_at"]).weekday() == day_idx
                and _d(a["submitted_at"]).hour == hour
            )
            hourly_heatmap.append({
                "day": day_idx + 1, "day_name": day_names[day_idx],
                "hour": hour, "questions": count,
            })

    skill_states = bkt_engine.load_all_states(user_id)
    mastery_bars = [
        {
            "skill_id": sid, "p_known": round(s.p_known, 2),
            "mastery_level": bkt_engine.get_mastery_level(s),
            "attempt_count": s.attempt_count, "correct_count": s.correct_count,
        }
        for sid, s in skill_states.items() if s.attempt_count > 0
    ]
    mastery_bars.sort(key=lambda x: x["p_known"])
    total_sessions = len(session_rows)
    # 估算总分钟
    total_minutes = sum(r.get("estimated_minutes", 0) for r in session_rows)
    study_days = len(set(_ds(r.get("started_at"))[:10] for r in session_rows if r.get("started_at")))

    # 行为分析
    report = behavior_analyzer.analyze(
        daily_trend=daily_trend,
        hourly_heatmap=hourly_heatmap,
        mastery_bars=mastery_bars,
        total_sessions=total_sessions,
        total_minutes=total_minutes,
    )

    # 习惯养成
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
