"""
Knowledge Tree SSE 端点 — 实时推送知识树变更

GET /api/knowledge-tree/events
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.domain.auth.dependencies import current_user_id
from app.services.knowledge_tree.event_bus_service import kb_event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-tree", tags=["知识树 SSE"])


@router.get("/events")
async def stream_knowledge_events(user_id: str = Depends(current_user_id)):
    """SSE 端点 — 实时推送知识树变更事件"""
    return StreamingResponse(
        kb_event_bus.stream_events(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )