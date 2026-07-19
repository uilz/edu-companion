"""
AppleGo Workspace Domain — Workspace & Session aggregates.

Per Domain Freeze v1.1:
- Workspace: Persistent learning space. Lifecycle state machine.
- Session: Bounded learning event. Created → Active ⇄ Paused → Ended.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)

def _uid() -> UUID:
    return uuid4()


class WorkspaceState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    DORMANT = "dormant"
    ENDED = "ended"


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


@dataclass
class Mission:
    """Value object — what the learner is trying to accomplish in this session."""
    source: str = ""       # e.g. "user", "ai_suggested", "resumed"
    text: str = ""
    state: str = "active"  # active, completed, abandoned


@dataclass
class SessionArtifact:
    """Value object — snapshot of what's open during a session."""
    artifact_type: str    # e.g. "pdf", "video", "canvas", "flashcard"
    artifact_id: UUID
    position: dict | None = None


@dataclass
class Session:
    """Session aggregate — a single bounded learning event.
    
    State machine: Created → Active ⇄ Paused → Ended.
    Invariants per Contract: 
    - Only one active session per workspace (enforced by DB unique partial index)
    - Paused session auto-refreshes daily
    """
    id: UUID = field(default_factory=_uid)
    workspace_id: UUID = field(default_factory=_uid)
    project_id: UUID | None = None
    state: SessionState = SessionState.CREATED
    title: str = ""
    mission: Mission = field(default_factory=Mission)
    artifacts: list[SessionArtifact] = field(default_factory=list)
    last_refresh: datetime = field(default_factory=_now)
    created_at: datetime = field(default_factory=_now)
    ended_at: datetime | None = None

    def activate(self) -> None:
        if self.state not in (SessionState.CREATED, SessionState.PAUSED):
            raise ValueError(f"Cannot activate session in state {self.state}")
        self.state = SessionState.ACTIVE
        self.last_refresh = _now()

    def pause(self) -> None:
        if self.state != SessionState.ACTIVE:
            raise ValueError(f"Cannot pause session in state {self.state}")
        self.state = SessionState.PAUSED
        self.last_refresh = _now()

    def resume(self) -> None:
        if self.state != SessionState.PAUSED:
            raise ValueError(f"Cannot resume session in state {self.state}")
        self.state = SessionState.ACTIVE
        self.last_refresh = _now()

    def end(self) -> None:
        if self.state == SessionState.ENDED:
            raise ValueError("Session already ended")
        self.state = SessionState.ENDED
        self.ended_at = _now()

    @property
    def is_active(self) -> bool:
        return self.state == SessionState.ACTIVE


@dataclass
class Workspace:
    """Workspace aggregate — persistent learning space.
    
    State machine: Created → Active ⇄ Dormant → Ended.
    Invariants per Contract:
    - One learner owns one workspace (I1)
    - Permanent. Never deleted by system (I2)
    - One active session per workspace (I3)
    - AI cannot create/rename/delete (I5)
    """
    id: UUID = field(default_factory=_uid)
    user_id: UUID = field(default_factory=_uid)
    name: str = ""
    icon: str = "book"
    color: str = "#5a8f6b"
    state: WorkspaceState = WorkspaceState.CREATED
    active_session_id: UUID | None = None
    day_count: int = 0
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def activate(self) -> None:
        if self.state not in (WorkspaceState.CREATED, WorkspaceState.DORMANT):
            raise ValueError(f"Cannot activate workspace in state {self.state}")
        self.state = WorkspaceState.ACTIVE
        self.updated_at = _now()

    def mark_dormant(self) -> None:
        if self.state != WorkspaceState.ACTIVE:
            raise ValueError(f"Cannot mark dormant in state {self.state}")
        self.state = WorkspaceState.DORMANT
        self.updated_at = _now()

    def end(self) -> None:
        if self.state == WorkspaceState.ENDED:
            raise ValueError("Workspace already ended")
        self.state = WorkspaceState.ENDED
        self.updated_at = _now()
