"""
Knowledge Graph SSE 端点 — 实时推送认知图谱变更

GET /api/knowledge-graph/events
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.domain.auth.dependencies import current_user_id
from app.services.knowledge_tree.event_bus_service import kb_event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-graph", tags=["认知图谱 SSE"])


@router.get("/events")
async def stream_knowledge_events(user_id: str = Depends(current_user_id)):
    """SSE 端点 — 实时推送认知图谱变更事件"""
    return StreamingResponse(
        kb_event_bus.stream_events(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
