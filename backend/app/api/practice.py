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

# ── 内存存储（MVP，后续迁移PostgreSQL）──

_question_bank: dict[str, list[Question]] = {}  # skill_id → questions
_sessions: dict[str, PracticeSession] = {}       # session_id → session
_error_book: dict[str, list[ErrorBookEntry]] = {} # user_id → entries
_materials: dict[str, list[Material]] = {}        # user_id → materials
_material_chunks: dict[str, list[MaterialChunk]] = {}  # material_id → chunks


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

    # 存入题库
    if req.skill_id not in _question_bank:
        _question_bank[req.skill_id] = []
    _question_bank[req.skill_id].extend(questions)

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
    all_questions = []
    for skill_questions in _question_bank.values():
        all_questions.extend(skill_questions)

    if subject:
        all_questions = [q for q in all_questions if q.subject == subject]
    if skill_id:
        all_questions = [q for q in all_questions if q.skill_id == skill_id]
    if bloom_level:
        all_questions = [q for q in all_questions if q.bloom_level == bloom_level]

    return {
        "questions": [q.model_dump() for q in all_questions[:limit]],
        "total": len(all_questions),
    }


# ──────────────────────────────────────────────
# 练习会话
# ──────────────────────────────────────────────

@router.post("/sessions")
async def create_session(req: CreateSessionRequest):
    """创建练习会话"""
    user_id = "default_user"  # MVP单用户

    # 确定练习的知识点
    skill_ids = req.skill_ids or []
    if not skill_ids:
        # 自动选择：从题库中选有题的知识点
        skill_ids = [s for s, qs in _question_bank.items() if qs][:4]

    # 选题
    questions = []
    for skill_id in skill_ids:
        pool = _question_bank.get(skill_id, [])
        if pool:
            # 简单选题：按难度匹配
            target_diff = 0.5  # MVP默认
            sorted_q = sorted(pool, key=lambda q: abs(q.difficulty - target_diff))
            questions.extend(sorted_q[:3])

    session = PracticeSession(
        user_id=user_id,
        planned_skills=skill_ids,
        estimated_minutes=req.duration_minutes,
        mode=req.mode,
        question_ids=[q.question_id for q in questions],
    )

    _sessions[session.session_id] = session

    return {
        "session": session.model_dump(),
        "questions": [q.model_dump() for q in questions],
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"session": session.model_dump()}


@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str):
    """结束会话"""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = SessionStatus.COMPLETED
    session.completed_at = datetime.now()

    return {
        "session": session.model_dump(),
        "accuracy": session.accuracy,
        "total_questions": session.total_questions,
        "correct_count": session.correct_count,
        "struggling_skills": session.struggling_skills,
    }


# ──────────────────────────────────────────────
# 答题与反馈
# ──────────────────────────────────────────────

@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest):
    """提交答案"""
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 查找题目
    question = None
    for pool in _question_bank.values():
        for q in pool:
            if q.question_id == req.question_id:
                question = q
                break
        if question:
            break

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # 判对错
    is_correct = req.answer.strip().upper() == question.correct_answer.strip().upper()

    # 创建答题记录
    attempt = AttemptRecord(
        user_id=session.user_id,
        question_id=req.question_id,
        session_id=req.session_id,
        user_answer=req.answer,
        is_correct=is_correct,
        time_spent_seconds=req.time_spent_seconds,
        hints_used=req.hints_used,
        explanation_text=req.explanation_text,
    )

    # 更新知识状态
    from app.schemas.practice import KnowledgeState
    state = bkt_engine.create_knowledge_state(question.skill_id)
    updated_state = bkt_engine.update(
        state, is_correct,
        hint_level=req.hints_used,
        explanation_score=None,  # 需要LLM评分，MVP先跳过
    )

    attempt.knowledge_before = {question.skill_id: state.p_known}
    attempt.knowledge_after = {question.skill_id: updated_state.p_known}

    # 更新会话
    session.attempts.append(attempt)
    if is_correct:
        session.correct_count += 1

    # 生成反馈
    feedback = {
        "is_correct": is_correct,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "knowledge_update": {
            "skill_id": question.skill_id,
            "p_known_before": state.p_known,
            "p_known_after": updated_state.p_known,
            "mastery_level": bkt_engine.get_mastery_level(updated_state),
        },
    }

    # 错误时添加错因分析
    if not is_correct and question.options:
        chosen = next((o for o in question.options if o.letter.upper() == req.answer.upper()), None)
        if chosen and chosen.distractor_type:
            feedback["error_analysis"] = {
                "type": "misconception",
                "distractor_type": chosen.distractor_type,
                "suggestion": f"你选择了{chosen.letter}，可能的原因是{chosen.distractor_type}",
            }

    # 情感反馈
    recent = session.last_n_results(5)
    consecutive_wrong = sum(1 for a in reversed(recent) if not a.is_correct)
    if consecutive_wrong >= 3:
        feedback["emotional_feedback"] = "别着急，困难的知识点需要多花时间。要不要先看看相关视频讲解？🎬"
    elif consecutive_wrong >= 2:
        feedback["emotional_feedback"] = "这个知识点确实有点难，我们一步步来 🤝"

    return feedback


@router.post("/hint")
async def get_hint(req: HintRequest):
    """获取提示"""
    # 查找题目
    question = None
    for pool in _question_bank.values():
        for q in pool:
            if q.question_id == req.question_id:
                question = q
                break
        if question:
            break

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    level = req.current_level + 1
    hints = question.hints or []

    if level == 0:
        text = "试着自己想想看 💪"
        hint_type = "encouragement"
    elif level <= len(hints):
        text = hints[level - 1]
        hint_type = "direction"
    else:
        text = question.explanation
        hint_type = "full"

    return {
        "hint": {"level": level, "text": text, "type": hint_type},
        "next_level_available": level < 4,
    }


# ──────────────────────────────────────────────
# 错题本
# ──────────────────────────────────────────────

@router.get("/errors")
async def get_error_book(
    resolved: Optional[bool] = None,
    skill_id: Optional[str] = None,
    limit: int = 20,
):
    """获取错题本"""
    user_id = "default_user"
    entries = _error_book.get(user_id, [])

    if resolved is not None:
        entries = [e for e in entries if e.is_resolved == resolved]
    if skill_id:
        entries = [e for e in entries if e.skill_id == skill_id]

    return {
        "entries": [e.model_dump() for e in entries[:limit]],
        "total": len(entries),
        "unresolved_count": sum(1 for e in _error_book.get(user_id, []) if not e.is_resolved),
    }


# ──────────────────────────────────────────────
# 统计
# ──────────────────────────────────────────────

@router.get("/stats")
async def get_stats(time_range: str = "week"):
    """获取练习统计"""
    user_id = "default_user"
    all_attempts = []
    for session in _sessions.values():
        if session.user_id == user_id:
            all_attempts.extend(session.attempts)

    if not all_attempts:
        return PracticeStats(user_id=user_id).model_dump()

    total = len(all_attempts)
    correct = sum(1 for a in all_attempts if a.is_correct)

    # 按知识点统计
    skill_stats: dict[str, SkillStat] = {}
    for attempt in all_attempts:
        if attempt.error_analysis:
            for skill in attempt.error_analysis.related_skills:
                if skill not in skill_stats:
                    skill_stats[skill] = SkillStat(skill_id=skill)
                skill_stats[skill].total_attempts += 1
                if attempt.is_correct:
                    skill_stats[skill].correct_count += 1

    for stat in skill_stats.values():
        if stat.total_attempts > 0:
            stat.accuracy = stat.correct_count / stat.total_attempts

    weak = [(s.skill_id, s.accuracy) for s in skill_stats.values() if s.accuracy < 0.6]
    strong = [(s.skill_id, s.accuracy) for s in skill_stats.values() if s.accuracy >= 0.8]

    return PracticeStats(
        user_id=user_id,
        total_questions=total,
        total_correct=correct,
        accuracy=correct / total if total > 0 else 0.0,
        weak_skills=sorted(weak, key=lambda x: x[1])[:5],
        strong_skills=sorted(strong, key=lambda x: x[1], reverse=True)[:5],
    ).model_dump()
