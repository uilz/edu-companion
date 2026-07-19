"""Resource API — Pydantic schemas"""

from __future__ import annotations
from pydantic import BaseModel, Field


class ResourceItem(BaseModel):
    id: str
    workspace_id: str
    material_id: str
    title: str = ""
    state: str = "closed"
    created_at: str = ""


class ReadingStateResponse(BaseModel):
    resource_id: str
    position_page: int = 0
    position_scroll: float = 0.0
    last_read_at: str = ""


class PositionUpdateRequest(BaseModel):
    page: int = 0
    scroll: float = 0.0


class HighlightCreateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    note: str = ""
    page: int = 0
    scroll: float = 0.0


class HighlightResponse(BaseModel):
    id: str
    resource_id: str
    text: str = ""
    note: str = ""
    position_page: int = 0
    position_scroll: float = 0.0
    created_at: str = ""


class ResourceLifecycleResponse(BaseModel):
    resource_id: str
    state: str
    title: str = ""
