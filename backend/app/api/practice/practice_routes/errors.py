"""错题本 + 复习调度"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_scheduler import (
    get_due_questions, get_review_stats,
)
from app.services.practice.practice_error_book import (
    get_error_book, get_error_session_stats, clear_mastered_errors,
    review_error_question, get_error_materials,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 复习调度
# ═══════════════════════════════════════════════

@router.get("/review/due")
async def api_review_due(
    user_id: str = Depends(current_user_id),
    bank_id: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
    limit: int = 20,
):
    _ensure_tables()
    return get_due_questions(
        user_id=user_id,
        bank_id=bank_id,
        cognitive_node_id=cognitive_node_id,
        limit=min(limit, 100),
    )


@router.get("/review/stats")
async def api_review_stats(
    user_id: str = Depends(current_user_id),
    bank_id: Optional[str] = None,
):
    _ensure_tables()
    return get_review_stats(user_id=user_id, bank_id=bank_id)


# ═══════════════════════════════════════════════
# 错题本
# ═══════════════════════════════════════════════

@router.get("/error-book")
async def api_error_book(
    user_id: str = Depends(current_user_id),
    bank_id: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
    min_wrongs: int = 1,
    sort_by: str = "wrongs_desc",
    page: int = 1,
    page_size: int = 20,
):
    _ensure_tables()
    return get_error_book(
        user_id=user_id, bank_id=bank_id,
        cognitive_node_id=cognitive_node_id,
        min_wrongs=min_wrongs, sort_by=sort_by,
        page=page, page_size=min(page_size, 100),
    )


@router.get("/error-book/stats")
async def api_error_book_stats(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return get_error_session_stats(user_id)


@router.post("/error-book/clear-mastered")
async def api_clear_mastered(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return clear_mastered_errors(user_id)


@router.post("/error-book/{question_id}/review")
async def api_review_error(question_id: str, body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return review_error_question(
        question_id=question_id,
        user_id=user_id,
        is_correct=body.get("is_correct", False),
        time_spent=body.get("time_spent", 0),
    )


@router.get("/error-book/{question_id}/materials")
async def api_error_materials(question_id: str, user_id: str = Depends(current_user_id), limit: int = 3):
    _ensure_tables()
    return get_error_materials(question_id, user_id, limit=min(limit, 10))
