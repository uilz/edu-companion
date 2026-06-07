"""自适应组题 + 秘书联动 + 答题历史"""
from __future__ import annotations

import json as _json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_adaptive import adaptive_select_v2

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 自适应组题
# ═══════════════════════════════════════════════

@router.post("/adaptive/select")
async def api_adaptive_select(body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    count = max(1, min(50, int(body.get("count", 10))))
    questions = adaptive_select_v2(
        bank_id=bank_id,
        user_id=user_id,
        count=count,
        mode=body.get("mode", "adaptive"),
        cognitive_node_ids=body.get("cognitive_node_ids"),
        exclude_ids=body.get("exclude_ids"),
    )
    return {
        "selected": len(questions),
        "questions": questions,
        "params": {
            "bank_id": bank_id,
            "count": count,
            "mode": body.get("mode", "adaptive"),
        },
    }


# ═══════════════════════════════════════════════
# 秘书联动提案
# ═══════════════════════════════════════════════

@router.get("/secretary/proposals")
async def api_practice_secretary_proposals(
    user_id: str = Depends(current_user_id),
    limit: int = 5,
):
    from app.domain.secretary.proposal_store import ProposalStore
    store = ProposalStore()
    proposals = store.get_pending_proposals(user_id, limit=limit)
    practice_types = {"practice_error_alert", "practice_mastery_stuck", "practice_review_reminder", "practice_reflection"}
    filtered = [p for p in proposals if p.action_type in practice_types]
    result = []
    for p in filtered:
        result.append({
            "id": p.id,
            "emoji": p.emoji or "💡",
            "title": p.title,
            "description": p.description,
            "action_type": p.action_type,
            "payload": p.payload,
            "priority": p.priority,
            "created_at": p.created_at,
        })
    return {"proposals": result[:limit], "total": len(filtered)}


@router.post("/secretary/proposals/{proposal_id}/accept")
async def api_secretary_accept_proposal(proposal_id: str, body: dict = None, user_id: str = Depends(current_user_id)):
    from app.domain.secretary.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "accepted", user_id)
    return {"status": "accepted"}


@router.post("/secretary/proposals/{proposal_id}/dismiss")
async def api_secretary_dismiss_proposal(proposal_id: str, user_id: str = Depends(current_user_id)):
    from app.domain.secretary.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "dismissed", user_id)
    return {"status": "dismissed"}


# ═══════════════════════════════════════════════
# 答题历史
# ═══════════════════════════════════════════════

@router.get("/history/answers")
async def api_answer_history(
    user_id: str = Depends(current_user_id),
    question_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    _ensure_tables()
    from app.db.database import get_db
    db = get_db()

    conditions = ["a.user_id = %s"]
    params: list = [user_id]

    if question_id:
        conditions.append("a.question_id = %s")
        params.append(question_id)
    if session_id:
        conditions.append("a.session_id = %s")
        params.append(session_id)

    where = " AND ".join(conditions)

    total = db.fetchone(
        f"SELECT COUNT(*) as cnt FROM practice_attempts a WHERE {where}",
        tuple(params),
    )
    total_count = total["cnt"] if total else 0

    rows = db.fetchall(
        f"""SELECT a.id, a.session_id, a.question_id, a.user_answer,
                   a.is_correct, a.time_spent_seconds, a.is_wrong,
                   a.wrong_count, a.consecutive_correct, a.cognitive_node_ids,
                   a.created_at,
                   q.stem, q.options, q.question_type, q.difficulty, q.answer as correct_answer
            FROM practice_attempts a
            LEFT JOIN questions q ON a.question_id = q.id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT %s OFFSET %s""",
        tuple(params + [min(limit, 200), max(offset, 0)]),
    )

    items = []
    for r in rows:
        items.append({
            "attempt_id": r["id"],
            "session_id": r["session_id"],
            "question_id": r["question_id"],
            "user_answer": _json.loads(r["user_answer"]) if isinstance(r["user_answer"], str) else r["user_answer"],
            "is_correct": r["is_correct"],
            "time_spent_seconds": r.get("time_spent_seconds", 0),
            "is_wrong": r.get("is_wrong", False),
            "wrong_count": r.get("wrong_count", 0),
            "consecutive_correct": r.get("consecutive_correct", 0),
            "cognitive_node_ids": r.get("cognitive_node_ids") or [],
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            "question_stem": (r.get("stem") or "")[:120],
            "question_type": r.get("question_type", ""),
            "difficulty": r.get("difficulty", 3),
            "correct_answer": _json.loads(r["correct_answer"]) if isinstance(r.get("correct_answer"), str) else (r.get("correct_answer") or []),
        })

    return {
        "items": items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }
