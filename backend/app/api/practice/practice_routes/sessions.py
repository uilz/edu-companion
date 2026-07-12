"""练习会话 + 考试模式

本文件仅做 HTTP 参数转换与错误映射，所有业务逻辑委托给
app.services.practice.practice_session / practice_exam。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_session import (
    create_session, get_session, submit_answer, complete_session, list_sessions,
    start_session, pause_session, resume_session, cancel_session, get_session_result,
    delete_session, get_unfinished_sessions,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 练习会话
# ═══════════════════════════════════════════════

@router.post("/sessions")
async def api_create_session(body: dict, user_id: str = Depends(current_user_id)):
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    return await create_session(
        bank_id=bank_id,
        user_id=user_id,
        session_type=body.get("session_type", "practice"),
        mode=body.get("mode", "adaptive"),
        question_count=body.get("count", 10),
        config=body.get("config"),
        exclude_ids=body.get("exclude_ids"),
        cognitive_node_ids=body.get("cognitive_node_ids"),
        sources=body.get("sources"),
        question_ids=body.get("question_ids"),
    )


@router.get("/sessions")
async def api_list_sessions(
    user_id: str = Depends(current_user_id),
    bank_id: Optional[str] = None,
    status: Optional[str] = None,
    session_type: Optional[str] = None,
    mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    duration_min: Optional[int] = None,
    duration_max: Optional[int] = None,
    question_count_min: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    cursor: Optional[str] = None,
):
    return list_sessions(
        user_id=user_id, bank_id=bank_id, status=status,
        session_type=session_type,
        mode=mode, date_from=date_from, date_to=date_to,
        score_min=score_min, score_max=score_max,
        limit=min(limit, 100), offset=max(offset, 0),
    )


@router.get("/sessions/unfinished")
async def api_unfinished_sessions(user_id: str = Depends(current_user_id)):
    return get_unfinished_sessions(user_id)


@router.get("/sessions/{session_id}")
async def api_get_session(session_id: str, user_id: str = Depends(current_user_id)):
    session = get_session(session_id, user_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    return session


@router.post("/sessions/{session_id}/submit")
async def api_submit_answer(session_id: str, body: dict, user_id: str = Depends(current_user_id)):
    question_id = body.get("question_id", "")
    if not question_id:
        raise HTTPException(400, "question_id 不能为空")
    result = submit_answer(
        session_id=session_id,
        question_id=question_id,
        user_id=user_id,
        user_answer=body.get("answer"),
        time_spent=body.get("time_spent", 0),
        hints_used=body.get("hints_used", 0),
        confidence_before=body.get("confidence_before"),
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/complete")
async def api_complete_session(session_id: str, user_id: str = Depends(current_user_id)):
    result = complete_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    return result


@router.patch("/sessions/{session_id}/start")
async def api_start_session(session_id: str, user_id: str = Depends(current_user_id)):
    result = start_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.patch("/sessions/{session_id}/pause")
async def api_pause_session(session_id: str, user_id: str = Depends(current_user_id)):
    result = pause_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.patch("/sessions/{session_id}/resume")
async def api_resume_session(session_id: str, user_id: str = Depends(current_user_id)):
    result = resume_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/sessions/{session_id}")
async def api_delete_session(session_id: str, user_id: str = Depends(current_user_id)):
    ok = delete_session(session_id, user_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"ok": True, "message": "会话已删除"}


@router.get("/sessions/{session_id}/result")
async def api_session_result(session_id: str, user_id: str = Depends(current_user_id)):
    result = get_session_result(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    return result


# ═══════════════════════════════════════════════
# 考试模式
# ═══════════════════════════════════════════════

@router.post("/exam")
async def api_create_exam(body: dict, user_id: str = Depends(current_user_id)):
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    from app.services.practice.practice_exam import create_exam_from_request
    return create_exam_from_request(user_id=user_id, bank_id=bank_id, body=body)


@router.get("/exam/{session_id}")
async def api_get_exam(session_id: str, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import get_exam
    exam = get_exam(session_id, user_id)
    if not exam:
        raise HTTPException(404, "考试不存在或已结束")
    return exam


@router.post("/exam/{session_id}/submit")
async def api_submit_exam(session_id: str, body: dict, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import submit_exam_answer
    return submit_exam_answer(
        session_id=session_id,
        user_id=user_id,
        question_id=body.get("question_id", ""),
        answer=body.get("answer"),
        time_spent=body.get("time_spent", 0),
        is_final=body.get("is_final", False),
    )


@router.post("/exam/{session_id}/auto-submit")
async def api_auto_submit_exam(session_id: str, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import auto_submit_exam
    result = auto_submit_exam(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在或已完成")
    return result


@router.post("/exam/{session_id}/grade")
async def api_grade_exam(session_id: str, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import grade_exam
    result = grade_exam(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在")
    return result


@router.get("/exam/{session_id}/answer-sheet")
async def api_exam_answer_sheet(session_id: str, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import get_exam_answer_sheet
    return get_exam_answer_sheet(session_id, user_id)


@router.get("/exam/{session_id}/time")
async def api_exam_time(session_id: str, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import get_exam_time
    return get_exam_time(session_id, user_id)


@router.post("/exam/{session_id}/submit-all")
async def api_submit_all_exam(session_id: str, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import submit_all_exam
    result = submit_all_exam(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在")
    return result


@router.get("/exam/{session_id}/result")
async def api_exam_result(session_id: str, user_id: str = Depends(current_user_id)):
    from app.services.practice.practice_exam import get_exam_result
    result = get_exam_result(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在")
    return result


@router.get("/feedback/{attempt_id}")
async def api_get_feedback(attempt_id: str, user_id: str = Depends(current_user_id)):
    """按 attempt_id 查询答题后的信息增益、掌握度变化与元认知建议。"""
    from app.api.practice.feedback_service import get_feedback
    return get_feedback(user_id=user_id, attempt_id=attempt_id)
