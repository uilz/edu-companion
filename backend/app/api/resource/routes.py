"""Resource API — ReadingRuntime-backed endpoints."""

from __future__ import annotations
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.api.resource.schemas import (
    ResourceItem, ReadingStateResponse, PositionUpdateRequest,
    HighlightCreateRequest, HighlightResponse, ResourceLifecycleResponse,
)
from app.application.di import get_reading_runtime
from app.domain.auth.dependencies import current_user_id
from app.infrastructure.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resources", tags=["resource"])


@router.get("", response_model=list[ResourceItem])
async def list_resources(user_id: str = Depends(current_user_id)):
    """List resources for current user. Scoped to user via query."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    db = get_db()
    rows = db.fetchall(
        """SELECT r.id, r.workspace_id, r.material_id, r.title, r.state,
                  r.created_at
           FROM resources r JOIN workspaces w ON r.workspace_id = w.id
           WHERE w.user_id = %s ORDER BY r.created_at DESC""",
        (user_id,),
    )
    return [ResourceItem(
        id=str(r["id"]), workspace_id=str(r["workspace_id"]),
        material_id=str(r["material_id"]), title=r.get("title", ""),
        state=r.get("state", "closed"), created_at=str(r.get("created_at", "")),
    ) for r in rows]


@router.get("/{resource_id}/state", response_model=ReadingStateResponse)
async def get_reading_state(resource_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_reading_runtime()
    state = await rt.get_reading_state(UUID(resource_id), UUID(user_id))
    if not state:
        return ReadingStateResponse(resource_id=resource_id)
    return ReadingStateResponse(
        resource_id=str(state.resource_id),
        position_page=state.position_page,
        position_scroll=state.position_scroll,
        last_read_at=str(state.last_read_at),
    )


@router.post("/{resource_id}/open", response_model=ResourceLifecycleResponse)
async def open_resource(resource_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_reading_runtime()
    try:
        res = await rt.open_resource(UUID(resource_id), UUID(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ResourceLifecycleResponse(
        resource_id=str(res.id), state=res.state.value, title=res.title,
    )


@router.post("/{resource_id}/progress")
async def update_position(resource_id: str, body: PositionUpdateRequest,
                          user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_reading_runtime()
    await rt.update_position(UUID(resource_id), UUID(user_id), body.page, body.scroll)
    return {"ok": True}


@router.post("/{resource_id}/highlights", response_model=HighlightResponse)
async def create_highlight(resource_id: str, body: HighlightCreateRequest,
                           user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_reading_runtime()
    hl = await rt.create_highlight(
        UUID(resource_id), UUID(user_id), body.text, body.note, body.page, body.scroll,
    )
    return HighlightResponse(
        id=str(hl.id), resource_id=str(hl.resource_id),
        text=hl.text, note=hl.note,
        position_page=hl.position_page, position_scroll=hl.position_scroll,
        created_at=str(hl.created_at),
    )


@router.post("/{resource_id}/close", response_model=ResourceLifecycleResponse)
async def close_resource(resource_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_reading_runtime()
    await rt.close_resource(UUID(resource_id), UUID(user_id))
    return ResourceLifecycleResponse(resource_id=resource_id, state="closed", title="")


@router.post("/{resource_id}/complete", response_model=ResourceLifecycleResponse)
async def complete_resource(resource_id: str, user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    rt = get_reading_runtime()
    try:
        res = await rt.complete_resource(UUID(resource_id), UUID(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ResourceLifecycleResponse(
        resource_id=str(res.id), state=res.state.value, title=res.title,
    )
