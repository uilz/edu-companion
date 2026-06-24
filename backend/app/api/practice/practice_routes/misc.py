"""自适应组题 + 秘书联动 + 答题历史 + 推荐 + 提示 + 内联练习"""
from __future__ import annotations

import json as _json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_adaptive import adaptive_select_v2
from app.services.practice.practice_stats import get_recommendations
from app.services.practice.engine import (
    get_hint_for_question,
    get_inline_hint,
    build_reply_text,
    update_cognitive_after_practice,
)

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
    from app.infrastructure.db.proposal_store import ProposalStore
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
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "accepted", user_id)
    return {"status": "accepted"}


@router.post("/secretary/proposals/{proposal_id}/dismiss")
async def api_secretary_dismiss_proposal(proposal_id: str, user_id: str = Depends(current_user_id)):
    from app.infrastructure.db.proposal_store import ProposalStore
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
    from app.infrastructure.db.database import get_db
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
                   q.stem, q.options, q.question_type, q.difficulty, q.answer
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
            "correct_answer": _json.loads(r["answer"]) if isinstance(r.get("answer"), str) else (r.get("answer") or []),
        })

    return {
        "items": items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


# ═══════════════════════════════════════════════
# 练习推荐
# ═══════════════════════════════════════════════

@router.get("/recommendations")
async def api_practice_recommendations(
    user_id: str = Depends(current_user_id),
    limit: int = 5,
):
    """综合推荐：薄弱知识点 + 待复习题目 + 推荐题库 + 学习建议"""
    _ensure_tables()
    return get_recommendations(user_id, limit=min(limit, 20))


# ═══════════════════════════════════════════════
# 提示 + 内联练习
# ═══════════════════════════════════════════════


class _HintRequest(BaseModel):
    question_id: str
    current_level: int = 0


class _InlineAnswerRequest(BaseModel):
    block_id: str
    answer: str


class _InlineHintRequest(BaseModel):
    block_id: str


@router.post("/hint")
async def get_hint(req: _HintRequest):
    """获取提示"""
    result = get_hint_for_question(req.question_id, req.current_level)
    if result is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return result


@router.post("/inline/answer")
async def inline_answer(req: _InlineAnswerRequest, user_id: str = Depends(current_user_id)):
    """对话内联练习 — 提交答案，读取 response_block 内容校验"""
    from app.services.common import get_data_repo
    from shared.knowledge_trace import get_cognitive_state
    from shared.constants import get_mastery_label

    data = get_data_repo().load(user_id)
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
        state = get_cognitive_state(user_id, skill_id)
        cog = update_cognitive_after_practice(
            user_id=user_id,
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
async def inline_hint(req: _InlineHintRequest, user_id: str = Depends(current_user_id)):
    """对话内联练习 — 获取提示"""
    result = get_inline_hint(req.block_id, user_id)
    if result is None:
        raise HTTPException(404, "Practice block not found")
    return result
