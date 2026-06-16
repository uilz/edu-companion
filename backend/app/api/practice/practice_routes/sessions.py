"""练习会话 + 考试模式"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_session import (
    create_session, get_session, submit_answer, complete_session, list_sessions,
    start_session, pause_session, resume_session, cancel_session, get_session_result,
    delete_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 练习会话
# ═══════════════════════════════════════════════

@router.post("/sessions")
async def api_create_session(body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
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
    _ensure_tables()
    return list_sessions(
        user_id=user_id, bank_id=bank_id, status=status,
        session_type=session_type,
        mode=mode, date_from=date_from, date_to=date_to,
        score_min=score_min, score_max=score_max,
        limit=min(limit, 100), offset=max(offset, 0),
    )


@router.get("/sessions/unfinished")
async def api_unfinished_sessions(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT ps.id, ps.bank_id, ps.session_type, ps.mode, ps.status, ps.total_count, ps.conversation_id,
                  (SELECT COUNT(*) FROM practice_attempts pa
                   WHERE pa.session_id = ps.id
                  ) as answered_count,
                  ps.created_at
           FROM practice_sessions ps
           WHERE ps.user_id = %s AND ps.status IN ('created', 'active', 'paused')
             AND ps.total_count > 0
           ORDER BY ps.created_at DESC LIMIT 10""",
        (user_id,),
    )
    items = []
    for r in rows:
        # 跳过 created 状态但没有任何答题记录的空 session（用户从未真正开始）
        answered = r.get("answered_count", 0) or 0
        if r["status"] == "created" and answered == 0:
            continue
        items.append({
            "session_id": r["id"],
            "bank_id": r["bank_id"],
            "session_type": r["session_type"],
            "mode": r["mode"],
            "status": r["status"],
            "total_count": r["total_count"],
            "conversation_id": r.get("conversation_id", ""),
            "answered_count": answered,
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
        })
    return {"items": items, "total": len(items)}


@router.get("/sessions/{session_id}")
async def api_get_session(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    session = get_session(session_id, user_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    return session


@router.post("/sessions/{session_id}/submit")
async def api_submit_answer(session_id: str, body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
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
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/complete")
async def api_complete_session(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    result = complete_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    return result


@router.patch("/sessions/{session_id}/start")
async def api_start_session(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    result = start_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.patch("/sessions/{session_id}/pause")
async def api_pause_session(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    result = pause_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.patch("/sessions/{session_id}/resume")
async def api_resume_session(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    result = resume_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/sessions/{session_id}")
async def api_delete_session(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    ok = delete_session(session_id, user_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"ok": True, "message": "会话已删除"}


@router.get("/sessions/{session_id}/result")
async def api_session_result(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    result = get_session_result(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    return result


# ═══════════════════════════════════════════════
# 考试模式
# ═══════════════════════════════════════════════

@router.post("/exam")
async def api_create_exam(body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    from app.services.practice.practice_exam import create_exam
    config = body.get("config") or {}
    if isinstance(config, dict):
        config["exam_type"] = body.get("exam_type", "standard")
    return create_exam(
        user_id=user_id,
        bank_id=bank_id,
        count=body.get("count", 20),
        duration_minutes=body.get("duration_minutes", body.get("time_limit", 60)),
        config=config,
    )


@router.get("/exam/{session_id}")
async def api_get_exam(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    from app.services.practice.practice_exam import get_exam
    exam = get_exam(session_id, user_id)
    if not exam:
        raise HTTPException(404, "考试不存在或已结束")
    return exam


@router.post("/exam/{session_id}/submit")
async def api_submit_exam(session_id: str, body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
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
    _ensure_tables()
    from app.services.practice.practice_exam import auto_submit_exam
    result = auto_submit_exam(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在或已完成")
    return result


@router.post("/exam/{session_id}/grade")
async def api_grade_exam(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    from app.services.practice.practice_exam import grade_exam
    result = grade_exam(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在")
    return result


@router.get("/exam/{session_id}/answer-sheet")
async def api_exam_answer_sheet(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    from app.services.practice.practice_exam import get_exam_answer_sheet
    return get_exam_answer_sheet(session_id, user_id)


@router.get("/exam/{session_id}/time")
async def api_exam_time(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    from app.services.practice.practice_exam import get_exam_time
    return get_exam_time(session_id, user_id)


@router.post("/exam/{session_id}/submit-all")
async def api_submit_all_exam(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    from app.services.practice.practice_exam import submit_all_exam
    result = submit_all_exam(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在")
    return result


@router.get("/exam/{session_id}/result")
async def api_exam_result(session_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    from app.services.practice.practice_exam import get_exam_result
    result = get_exam_result(session_id, user_id)
    if not result:
        raise HTTPException(404, "考试不存在")
    return result
