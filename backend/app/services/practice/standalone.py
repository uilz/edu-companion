"""独立练习答题服务

处理 /api/practice/submit 路径：不强制属于某个 session，
直接校验题目、记录尝试并发布领域事件。
"""
from __future__ import annotations

from typing import Optional


def _get_metacognition_feedback(confidence_before: int | None, is_correct: bool) -> str:
    if confidence_before is None:
        return ""
    if confidence_before >= 3:
        if is_correct:
            return "你确实掌握了，自信是对的"
        return "⚠️ 元认知偏差：你以为掌握了但其实没有。建议重新学习推导过程。"
    if is_correct:
        return "💡 谦逊的正确：你比你以为的更懂。试着给别人讲一遍确认。"
    return "还有提升空间，继续努力"


async def submit_standalone_answer(
    user_id: str,
    session_id: str,
    question_id: str,
    answer: str,
    time_spent_seconds: float = 0.0,
    hints_used: int = 0,
    confidence_before: int | None = None,
) -> dict:
    """提交独立练习答案，返回判题结果与元认知反馈。

    路径: /api/practice/submit (与 /api/practice/sessions/{id}/submit 共用底层事件)
    """
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_service import check_answer, record_attempt
    from app.services.practice.engine import publish_practice_events

    db = get_db()
    row = db.fetchone("SELECT * FROM questions WHERE id = %s", (question_id,))
    if not row:
        raise ValueError("Question not found")

    # 校验 session 归属 (跨用户提交防护)
    if session_id:
        from app.services.practice.session_repository import get_session
        owner = get_session(db, session_id, user_id)
        if not owner:
            raise ValueError("Session not found or not owned by user")

    correct_answer = (row.get("answer") or "").strip()
    is_correct = check_answer(answer, correct_answer)
    explanation = row.get("analysis", "") or row.get("explanation", "")

    record_attempt(
        user_id=user_id,
        session_id=session_id,
        question_id=question_id,
        answer=answer,
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
        hints_used=hints_used,
        confidence_before=confidence_before,
    )

    # 发布领域事件 (SSOT = engine.publish_practice_events)
    # 认知更新由认知中心订阅 AnswerSubmitted 统一处理，不再直接调用认知服务。
    await publish_practice_events(
        user_id=user_id,
        session_id=session_id,
        question_id=question_id,
        question=dict(row) if not isinstance(row, dict) else row,
        is_correct=is_correct,
        user_answer=answer,
        correct_answer=correct_answer,
        time_spent_seconds=int(time_spent_seconds),
        hints_used=hints_used,
    )

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "knowledge_update": {},
        "metacognition_feedback": _get_metacognition_feedback(confidence_before, is_correct),
    }
