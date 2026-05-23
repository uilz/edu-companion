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

    # Phase 4: 写共享状态（供 conversation_llm 等模块跨层读取）
    try:
        from app.shared.state import active_practice_sessions
        active_practice_sessions[session_id] = response_data["session"]
    except Exception:
        logger.debug("共享状态写入失败（非关键路径）", exc_info=True)

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
async def complete_session(
    session_id: str,
    user_id: str = "default_user",
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
    # 异步消费: achievement check, conversation update
    try:
        from app.shared.events import SessionCompleted
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

    # Phase 6: 同步写入 CognitiveNode
    try:
        from app.cognitive.events import submit_practice
        submit_practice(
            user_id=session["user_id"],
            node_id=question["skill_id"],
            success=is_correct,
            latency_ms=req.time_spent_seconds * 1000,
            consecutive=req.hints_used == 0,
        )
    except Exception:
        logger.debug("CognitiveNode 练习事件提交失败", exc_info=True)

    # v3.0: 记录练习事件
    try:
        from app.api.learning_events import record_event
        from app.schemas.learning_event import EventType
        sid = question["skill_id"]
        record_event(
            EventType.PRACTICE_SUBMIT,
            user_id=session["user_id"],
            partition_id=session.get("partition_id"),
            skill_ids=[sid],
            data={"correct": is_correct, "time_spent": req.time_spent_seconds},
        )
        old_p = state.p_known
        new_p = updated_state.p_known
        if old_p and abs(new_p - old_p) > 0.05:
            record_event(
                EventType.SKILL_MASTERY_CHANGED,
                user_id=session["user_id"],
                partition_id=session.get("partition_id"),
                skill_ids=[sid],
                data={"before": old_p, "after": new_p},
            )
    except Exception:
        logger.debug("学习事件记录失败", exc_info=True)

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
            "cognitive_proficiency": _get_cognitive_proficiency(session["user_id"], question["skill_id"]),
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

    # Phase 4C: 事件驱动 — 发布 AnswerSubmitted 事件
    # 异步消费: achievement check, adaptive planner, behavior analytics
    # 这些副作用不再阻塞用户响应
    old_mastery = bkt_engine.get_mastery_level(state)
    new_mastery = bkt_engine.get_mastery_level(updated_state)

    try:
        from app.shared.events import AnswerSubmitted as AnswerSubmittedEvent
        from app.infra.event_bus import EventBus
        # 使用 DI 容器的事件总线（如果可用），否则用临时实例
        try:
            from app.application.di import container
            bus = container.event_bus
        except Exception:
            bus = EventBus()

        event = AnswerSubmittedEvent(
            user_id=session["user_id"],
            session_id=req.session_id,
            question_id=req.question_id,
            skill_id=question["skill_id"],
            is_correct=is_correct,
            answer=req.answer,
            correct_answer=question["correct_answer"],
            time_spent=req.time_spent_seconds,
            hints_used=req.hints_used,
            p_known_before=state.p_known,
            p_known_after=updated_state.p_known,
        )
        # fire-and-forget: 不等待消费者完成
        import asyncio
        asyncio.create_task(bus.publish(event))

        # 如果 mastery 跨级别变化，额外发布 KnowledgeStateUpdated 事件
        SIGNIFICANT = {("初学","发展中"),("发展中","接近掌握"),("接近掌握","已掌握"),
                       ("未接触","初学"),("初学","接近掌握")}
        if (old_mastery, new_mastery) in SIGNIFICANT:
            from app.shared.events import KnowledgeStateUpdated
            ks_event = KnowledgeStateUpdated(
                user_id=session["user_id"],
                skill_id=question["skill_id"],
                old_mastery=old_mastery,
                new_mastery=new_mastery,
                p_known_before=state.p_known,
                p_known_after=updated_state.p_known,
                attempt_count=updated_state.attempt_count,
            )
            asyncio.create_task(bus.publish(ks_event))
    except Exception:
        logger.debug("事件发布失败（不影响答题流）", exc_info=True)

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



# ──────────────────────────────────────────────
# 错题 / 统计 / 行为 / 质量 API 已拆分至:
#   api/practice_errors.py     (errors)
#   api/practice_analytics.py  (stats + behavior)
#   api/practice_quality.py    (quality)
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
