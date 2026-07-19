"""
AppleGo Resource Domain — Resource, ReadingState, Highlight.

Per Contract /vision/contracts/resource.html:
- Resource: wrapper around materials, lifecycle: closed → open ⇄ completed
- ReadingState: per-user persistent position (I1, I2)
- Highlight: belongs to Resource, survives session boundaries (I3)
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


class ResourceState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    COMPLETED = "completed"


@dataclass
class ReadingState:
    """Per-user persistent reading position. Contract I1: one per resource + user."""
    id: UUID = field(default_factory=_uid)
    resource_id: UUID = field(default_factory=_uid)
    user_id: UUID = field(default_factory=_uid)
    position_page: int = 0
    position_scroll: float = 0.0
    last_read_at: datetime = field(default_factory=_now)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def update_position(self, page: int, scroll: float) -> None:
        self.position_page = page
        self.position_scroll = scroll
        self.last_read_at = _now()
        self.updated_at = _now()


@dataclass
class Highlight:
    """User highlight on a resource. Contract I3: belongs to Resource, not Session."""
    id: UUID = field(default_factory=_uid)
    resource_id: UUID = field(default_factory=_uid)
    user_id: UUID = field(default_factory=_uid)
    text: str = ""
    note: str = ""
    position_page: int = 0
    position_scroll: float = 0.0
    created_at: datetime = field(default_factory=_now)


@dataclass
class Resource:
    """Resource aggregate — wraps a material with lifecycle state.

    Contract I1: One ReadingState per learner.
    Contract I3: Highlights persist across sessions.
    """
    id: UUID = field(default_factory=_uid)
    workspace_id: UUID = field(default_factory=_uid)
    material_id: UUID = field(default_factory=_uid)
    title: str = ""
    state: ResourceState = ResourceState.CLOSED
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def open(self) -> None:
        if self.state == ResourceState.COMPLETED:
            raise ValueError("Cannot reopen completed resource")
        if self.state != ResourceState.OPEN:
            self.state = ResourceState.OPEN
            self.updated_at = _now()

    def close(self) -> None:
        if self.state == ResourceState.OPEN:
            self.state = ResourceState.CLOSED
            self.updated_at = _now()

    def complete(self) -> None:
        self.state = ResourceState.COMPLETED
        self.updated_at = _now()
