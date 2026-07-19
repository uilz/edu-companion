"""Workspace API — Pydantic schemas (aligned with AppleGo Demo6.0 Domain Freeze v1.1)"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


# ── Workspace ──


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class WorkspaceItem(BaseModel):
    """Workspace list item. Derived counts computed from sessions."""
    id: str
    name: str
    icon: str = "book"
    color: str = "#5a8f6b"
    state: str = "created"                       # created | active | dormant | ended
    day_count: int = 0                            # total days studied
    active_sessions_count: int = 0                # derived: count of active sessions
    completed_sessions_count: int = 0             # derived: count of ended sessions
    created_at: str = ""


class WorkspaceDetail(BaseModel):
    """Workspace detail view. Derived stats computed from sessions."""
    id: str
    name: str
    icon: str = "book"
    color: str = "#5a8f6b"
    state: str = "created"
    day_count: int = 0
    total_sessions: int = 0                       # derived
    active_sessions: int = 0                      # derived: count of active/paused sessions
    overall_progress: int = 0                     # derived: % of ended / total sessions


# ── Session ──


class CreateSessionRequest(BaseModel):
    title: str | None = None


class SessionItem(BaseModel):
    """Session list item. Maps domain Session to API shape."""
    id: str
    title: str = ""
    description: str = ""                          # backward compat (mission text)
    stage: str = "intro"                           # backward compat (derived from lifecycle)
    progress: int = 0                              # backward compat (mapped from state)
    estimated_minutes: int = 25                    # backward compat (default)
    created_at: str = ""
    status: str = "pending"                        # backward compat (mapped from state)
    # New domain fields
    state: str = "created"                         # created | active | paused | ended
    mission_source: str = ""                       # user | ai_suggested | resumed
    mission_text: str = ""
    ended_at: str | None = None


class SessionLifecycleResponse(BaseModel):
    """Response for session lifecycle operations (pause/resume/end)."""
    session_id: str
    workspace_id: str
    state: str
    title: str = ""


# ── Timeline ──


class TimelineItem(BaseModel):
    type: str  # 'session' | 'note' | 'video' | 'material'
    title: str
    meta: str = ""
    session_id: str | None = None


class TimelineEntry(BaseModel):
    date_label: str
    items: list[TimelineItem] = Field(default_factory=list)


# ── Roadmap ──


class RoadmapStage(BaseModel):
    name: str
    status: str  # 'done' | 'active' | 'next' | 'future'
    desc: str = ""
    stats: str = ""
    badge: str = ""


class RoadmapResponse(BaseModel):
    title: str
    overall_progress: int = 0
    stages: list[RoadmapStage] = Field(default_factory=list)


# ── Search ──


class SearchResultItem(BaseModel):
    type: str  # 'session' | 'material' | 'note' | 'flashcard' | 'video'
    title: str
    snippet: str = ""
    meta: str = ""
    badge: str = ""
