"""Practice API — PracticeRuntime-backed endpoints."""

from __future__ import annotations
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.api.practices.schemas import (
    CreatePracticeRequest, SubmitAttemptRequest, ReviewAttemptRequest,
    PracticeResponse, QuestionResponse, AttemptResponse,
)
from app.application.di import get_practice_runtime
from app.domain.auth.dependencies import current_user_id
from app.infrastructure.db.repositories.practice_repo import PracticeRepo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/practices", tags=["practice-runtime"])


@router.post("", response_model=PracticeResponse)
async def create_practice(body: CreatePracticeRequest, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_practice_runtime()
    practice = await rt.create_practice(
        UUID(body.workspace_id), UUID(user_id),
        body.title,
        [{"text": q.text, "concept_ids": q.concept_ids,
          "context_source": q.context_source, "correct_answer": q.correct_answer or ""}
         for q in body.questions] if body.questions else None,
    )
    return PracticeResponse(
        id=str(practice.id), workspace_id=str(practice.workspace_id),
        state=practice.state.value, title=practice.title,
        total_questions=practice.total_questions,
        correct_count=practice.correct_count,
        created_at=str(practice.created_at),
    )


@router.post("/{practice_id}/start", response_model=PracticeResponse)
async def start_practice(practice_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_practice_runtime()
    try:
        practice = await rt.start_practice(UUID(practice_id), UUID(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PracticeResponse(
        id=str(practice.id), workspace_id=str(practice.workspace_id),
        state=practice.state.value, title=practice.title,
        total_questions=practice.total_questions,
        correct_count=practice.correct_count,
        created_at=str(practice.created_at),
    )


@router.get("/{practice_id}/questions", response_model=list[QuestionResponse])
async def get_questions(practice_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    repo = PracticeRepo()
    questions = repo.find_questions(UUID(practice_id))
    return [QuestionResponse(
        id=str(q.id), seq=q.seq,
        text=q.text, concept_ids=q.concept_ids,
        context_source=q.context_source,
        created_at=str(q.created_at),
    ) for q in questions]


@router.post("/{practice_id}/attempts", response_model=AttemptResponse)
async def submit_attempt(practice_id: str, body: SubmitAttemptRequest,
                          user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_practice_runtime()
    attempt = await rt.submit_attempt(
        UUID(body.question_id), UUID(user_id),
        body.answer, body.is_correct,
        body.confidence, body.response_time_s,
    )
    return AttemptResponse(
        id=str(attempt.id), question_id=str(attempt.question_id),
        is_correct=attempt.is_correct, reviewed=attempt.reviewed,
        review_comment=attempt.review_comment,
        created_at=str(attempt.created_at),
    )


@router.post("/{practice_id}/review", response_model=dict)
async def review_attempt(practice_id: str, body: ReviewAttemptRequest,
                          user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_practice_runtime()
    await rt.review_attempt(UUID(body.attempt_id), body.comment)
    return {"ok": True}


@router.post("/{practice_id}/complete", response_model=PracticeResponse)
async def complete_practice(practice_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_practice_runtime()
    try:
        practice = await rt.complete_practice(UUID(practice_id), UUID(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PracticeResponse(
        id=str(practice.id), workspace_id=str(practice.workspace_id),
        state=practice.state.value, title=practice.title,
        total_questions=practice.total_questions,
        correct_count=practice.correct_count,
        created_at=str(practice.created_at),
    )
