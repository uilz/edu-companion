"""
AppleGo WorkspaceRuntime Domain Events
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from shared.events import DomainEvent, _now, _uid


@dataclass(frozen=True)
class WorkspaceCreated(DomainEvent):
    workspace_id: str = ""
    user_id: str = ""
    name: str = ""
    
    @property
    def event_type(self) -> str:
        return "WorkspaceCreated"


@dataclass(frozen=True)
class WorkspaceActivated(DomainEvent):
    workspace_id: str = ""
    user_id: str = ""
    
    @property
    def event_type(self) -> str:
        return "WorkspaceActivated"


@dataclass(frozen=True)
class WorkspaceEnded(DomainEvent):
    workspace_id: str = ""
    user_id: str = ""
    
    @property
    def event_type(self) -> str:
        return "WorkspaceEnded"


@dataclass(frozen=True)
class SessionCreated(DomainEvent):
    session_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    title: str = ""
    
    @property
    def event_type(self) -> str:
        return "SessionCreated"


@dataclass(frozen=True)
class SessionPaused(DomainEvent):
    session_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    
    @property
    def event_type(self) -> str:
        return "SessionPaused"


@dataclass(frozen=True)
class SessionResumed(DomainEvent):
    session_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    
    @property
    def event_type(self) -> str:
        return "SessionResumed"


@dataclass(frozen=True)
class SessionEnded(DomainEvent):
    session_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    
    @property
    def event_type(self) -> str:
        return "SessionEnded"
