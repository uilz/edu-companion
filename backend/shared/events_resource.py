"""
AppleGo ReadingRuntime Domain Events.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from shared.events import DomainEvent


@dataclass(frozen=True)
class ResourceOpened(DomainEvent):
    resource_id: str = ""
    workspace_id: str = ""
    user_id: str = ""

    @property
    def event_type(self) -> str:
        return "ResourceOpened"


@dataclass(frozen=True)
class ReadingProgressed(DomainEvent):
    resource_id: str = ""
    user_id: str = ""
    position_page: int = 0
    position_scroll: float = 0.0

    @property
    def event_type(self) -> str:
        return "ReadingProgressed"


@dataclass(frozen=True)
class HighlightCreated(DomainEvent):
    highlight_id: str = ""
    resource_id: str = ""
    user_id: str = ""
    text: str = ""

    @property
    def event_type(self) -> str:
        return "HighlightCreated"


@dataclass(frozen=True)
class ResourceClosed(DomainEvent):
    resource_id: str = ""
    workspace_id: str = ""
    user_id: str = ""

    @property
    def event_type(self) -> str:
        return "ResourceClosed"


@dataclass(frozen=True)
class ResourceCompleted(DomainEvent):
    resource_id: str = ""
    workspace_id: str = ""
    user_id: str = ""

    @property
    def event_type(self) -> str:
        return "ResourceCompleted"
