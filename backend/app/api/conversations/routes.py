"""Conversation API — ConversationRuntime-backed endpoints."""

from __future__ import annotations
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.api.conversations.schemas import (
    CreateConversationRequest, TurnRecordRequest, OrchestrationRequest,
    TurnResponse, ConversationItem, LifecycleResponse,
)
from app.application.di import get_conversation_runtime
from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["conversation-runtime"])


@router.post("/{session_id}", response_model=LifecycleResponse)
async def start_conversation(session_id: str, body: CreateConversationRequest,
                              user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_conversation_runtime()
    conv = await rt.start_conversation(UUID(session_id), UUID(user_id), body.title)
    return LifecycleResponse(
        conversation_id=str(conv.id), state=conv.state.value, title=conv.title,
    )


@router.post("/{conv_id}/turns", response_model=TurnResponse)
async def create_turn(conv_id: str, body: TurnRecordRequest,
                      user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_conversation_runtime()
    try:
        turn = await rt.create_turn(
            UUID(conv_id), UUID(user_id),
            body.user_message, body.ai_response,
            body.reading_page, body.reading_scroll,
            body.memory_tier, body.knowledge_concepts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TurnResponse(
        id=str(turn.id), seq=turn.seq,
        user_message=turn.user_message[:200],
        ai_response=turn.ai_response[:200],
        orchestration=turn.orchestration,
        created_at=str(turn.created_at),
    )


@router.post("/{conv_id}/orchestration")
async def record_orchestration(conv_id: str, body: OrchestrationRequest,
                                user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_conversation_runtime()
    await rt.record_orchestration(
        UUID(body.turn_id), UUID(conv_id),
        body.decision, body.artifact_type, body.artifact_id,
    )
    return {"ok": True}


@router.post("/{conv_id}/pause", response_model=LifecycleResponse)
async def pause_conversation(conv_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_conversation_runtime()
    await rt.pause_conversation(UUID(conv_id), UUID(user_id))
    return LifecycleResponse(conversation_id=conv_id, state="paused", title="")


@router.post("/{conv_id}/close", response_model=LifecycleResponse)
async def close_conversation(conv_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_conversation_runtime()
    await rt.close_conversation(UUID(conv_id), UUID(user_id))
    return LifecycleResponse(conversation_id=conv_id, state="closed", title="")


@router.get("/{conv_id}/turns", response_model=list[TurnResponse])
async def get_turns(conv_id: str, user_id: str = Depends(current_user_id)):
    """I6: Replayable conversation history."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_conversation_runtime()
    turns = await rt.get_turns(UUID(conv_id))
    return [TurnResponse(
        id=str(t.id), seq=t.seq,
        user_message=t.user_message[:200],
        ai_response=t.ai_response[:200],
        orchestration=t.orchestration,
        created_at=str(t.created_at),
    ) for t in turns]
