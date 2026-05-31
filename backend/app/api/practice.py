"""练习系统API v2.0
端点：题目生成、会话管理、答题提交、统计查询
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.constants import DEFAULT_USER_ID
from app.services.practice_service import (
    get_hint_for_question,
    get_inline_hint,
    check_answer,
    build_reply_text,
    update_cognitive_after_practice,
    get_cognitive_proficiency,
    list_practice_sessions,
    complete_practice_session,
    record_attempt,
    query_error_book,
    review_error_entry,
    analyze_error_entry,
    get_error_attribution_stats,
    compute_practice_stats,
    compute_behavior_report_data,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/practice", tags=["practice"])


# ──────────────────────────────────────────────
# Pydantic 请求模型
# ──────────────────────────────────────────────


class HintRequest(BaseModel):
    question_id: str
    current_level: int = 0


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str
    time_spent_seconds: float = 0.0
    hints_used: int = 0


class InlineAnswerRequest(BaseModel):
    block_id: str
    answer: str


class InlineHintRequest(BaseModel):
    block_id: str


# ──────────────────────────────────────────────
# 会话管理
# ──────────────────────────────────────────────


@router.get("/sessions")
async def list_sessions(user_id: str = DEFAULT_USER_ID, limit: int = 20):
    """列出用户的所有会话"""
    return list_practice_sessions(user_id, limit)


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    user_id: str = DEFAULT_USER_ID,
    partition_id: str | None = None,
    branch_id: str | None = None,
):
    """结束会话（如果有对话上下文，写入branch）"""
    result = complete_practice_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session = result["session"]

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
                correct_count=result["correct"],
                started_at=session.get("created_at", dt.now()),
                completed_at=dt.now(),
            )
            await integrate_practice_to_branch(user_id, ps, partition_id, branch_id)
        except Exception as e:
            logger.warning(f"练习结果写入branch失败: {e}")

    # 发布 SessionCompleted 事件
    try:
        from shared.events import SessionCompleted
        from app.application.di import container
        event = SessionCompleted(
            user_id=user_id,
            session_id=session_id,
            total_questions=result["total"],
            correct_count=result["correct"],
            accuracy=result["accuracy"],
            duration_minutes=session.get("estimated_minutes", 0),
        )
        asyncio.create_task(container.event_bus.publish(event))
    except Exception:
        logger.debug("SessionCompleted 事件发布失败", exc_info=True)

    return {
        "session": session,
        "accuracy": result["accuracy"],
        "struggling_skills": result["struggling"],
    }


# ──────────────────────────────────────────────
# 提示
# ──────────────────────────────────────────────


@router.post("/hint")
async def get_hint(req: HintRequest):
    """获取提示"""
    result = get_hint_for_question(req.question_id, req.current_level)
    if result is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return result


# ──────────────────────────────────────────────
# 独立练习答题提交
# ──────────────────────────────────────────────


@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest):
    """独立练习 — 提交单题答案"""
    from app.db.database import get_db

    db = get_db()
    row = db.fetchone("SELECT * FROM questions WHERE question_id = %s", (req.question_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")

    correct_answer = (row.get("correct_answer") or "").strip()
    is_correct = check_answer(req.answer, correct_answer)
    explanation = row.get("explanation", "")
    skill_id = row.get("skill_id", "")

    # 更新 CognitiveNode
    knowledge_update = None
    if skill_id:
        cog = update_cognitive_after_practice(
            user_id=DEFAULT_USER_ID,
            skill_id=skill_id,
            is_correct=is_correct,
            latency_ms=int(req.time_spent_seconds * 1000),
        )
        knowledge_update = {
            "skill_id": skill_id,
            "p_known_before": round(cog["p_before"], 4),
            "p_known_after": round(cog["p_after"], 4),
            "mastery_level": cog["mastery_label"],
        }

    # 记录答题
    record_attempt(
        user_id=DEFAULT_USER_ID,
        session_id=req.session_id,
        question_id=req.question_id,
        answer=req.answer,
        is_correct=is_correct,
        time_spent_seconds=req.time_spent_seconds,
        hints_used=req.hints_used,
    )

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "knowledge_update": knowledge_update,
    }


# ──────────────────────────────────────────────
# 对话内联练习（Inline Practice）
# ──────────────────────────────────────────────


@router.post("/inline/answer")
async def inline_answer(req: InlineAnswerRequest):
    """对话内联练习 — 提交答案，读取 response_block 内容校验"""
    from app.services.storage import storage
    from app.core.knowledge_trace import get_cognitive_state
    from shared.constants import get_mastery_label

    data = storage.load(DEFAULT_USER_ID)
    block = data.response_blocks.get(req.block_id)
    if not block:
        raise HTTPException(404, "Practice block not found")

    content = block.content or {}
    correct_answer = content.get("correct_answer", "").strip().upper()
    explanation = content.get("explanation") or content.get("reply_expected", "") or ""
    skill_id = content.get("skill_id", "")
    is_correct = req.answer.strip().upper() == correct_answer

    # 更新知识状态
    knowledge_update = {}
    if skill_id:
        state = get_cognitive_state(DEFAULT_USER_ID, skill_id)
        cog = update_cognitive_after_practice(
            user_id=DEFAULT_USER_ID,
            skill_id=skill_id,
            is_correct=is_correct,
        )
        knowledge_update = {
            "skill_id": skill_id,
            "p_known_before": cog["p_before"],
            "p_known_after": cog["p_after"],
            "mastery_level": get_mastery_label(state.p_known, state.attempt_count),
            "cognitive_proficiency": cog["cognitive_proficiency"],
        }

    correct_label = content.get("correct_answer", "")
    reply_text = build_reply_text(is_correct, correct_label, explanation)

    return {
        "is_correct": is_correct,
        "reply_text": reply_text,
        "knowledge_update": knowledge_update,
    }


@router.post("/inline/hint")
async def inline_hint(req: InlineHintRequest):
    """对话内联练习 — 获取提示"""
    result = get_inline_hint(req.block_id)
    if result is None:
        raise HTTPException(404, "Practice block not found")
    return result


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
    return query_error_book(
        user_id=DEFAULT_USER_ID,
        resolved=resolved,
        skill_id=skill_id,
        limit=limit,
    )


@router.post("/errors/{entry_id}/review")
async def review_error(entry_id: str, is_correct: bool = True):
    """复习错题"""
    result = review_error_entry(entry_id, is_correct)
    if result is None:
        raise HTTPException(status_code=404, detail="Error entry not found")
    return result


@router.post("/errors/{entry_id}/analyze")
async def analyze_error(entry_id: str):
    """LLM 深度分析单条错题的错因"""
    result = await analyze_error_entry(entry_id)
    if result is None:
        raise HTTPException(404, "错题记录不存在")
    return result


@router.get("/errors/stats")
async def get_error_stats():
    """错因分布统计"""
    return get_error_attribution_stats()


# ──────────────────────────────────────────────
# 统计 + 行为分析
# ──────────────────────────────────────────────


@router.get("/stats")
async def get_stats(time_range: str = "week"):
    """获取练习统计"""
    return compute_practice_stats(time_range=time_range)


@router.get("/behavior")
async def get_behavior_report(time_range: str = "week"):
    """学习行为分析报告"""
    return compute_behavior_report_data(time_range=time_range)


# ──────────────────────────────────────────────
# 题目质量监控
# ──────────────────────────────────────────────


@router.get("/quality")
async def get_quality_summary():
    """获取全量质量摘要"""
    from app.services.quality_analyzer import quality_analyzer
    summary = quality_analyzer.analyze_all()
    return summary.to_dict()


@router.post("/quality/apply")
async def apply_quality_actions(dry_run: bool = True):
    """执行质量分析建议动作"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.apply_actions(dry_run=dry_run)
    return result


@router.get("/quality/detail/{question_id}")
async def get_question_quality(question_id: str):
    """获取单题质量分析"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.analyze_question(question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return result.to_dict()


# ──────────────────────────────────────────────
# 统一知识状态 API (SharedKnowledgeState)
# ──────────────────────────────────────────────


@router.get("/knowledge/state")
async def get_knowledge_state():
    """获取统一知识状态"""
    from app.services.cognitive_queries import get_all_skills_summary
    return get_all_skills_summary()
