"""AppleGo Conversation Domain — domain events."""
from __future__ import annotations
from dataclasses import dataclass
from shared.events import DomainEvent


@dataclass(frozen=True)
class ConversationStarted(DomainEvent):
    conversation_id: str = ""
    session_id: str = ""
    user_id: str = ""
    title: str = ""

    @property
    def event_type(self) -> str:
        return "ConversationStarted"


@dataclass(frozen=True)
class TurnCreated(DomainEvent):
    turn_id: str = ""
    conversation_id: str = ""
    session_id: str = ""
    user_id: str = ""
    seq: int = 1
    user_message: str = ""

    @property
    def event_type(self) -> str:
        return "TurnCreated"


@dataclass(frozen=True)
class ResponseComplete(DomainEvent):
    turn_id: str = ""
    conversation_id: str = ""
    session_id: str = ""
    user_id: str = ""
    ai_response_length: int = 0

    @property
    def event_type(self) -> str:
        return "ResponseComplete"


@dataclass(frozen=True)
class OrchestrationDecided(DomainEvent):
    turn_id: str = ""
    conversation_id: str = ""
    session_id: str = ""
    decision: str = ""                 # silence | suggest | generate | open_artifact
    artifact_type: str = ""
    artifact_id: str = ""

    @property
    def event_type(self) -> str:
        return "OrchestrationDecided"


@dataclass(frozen=True)
class ConversationPaused(DomainEvent):
    conversation_id: str = ""
    session_id: str = ""
    user_id: str = ""

    @property
    def event_type(self) -> str:
        return "ConversationPaused"


@dataclass(frozen=True)
class ConversationClosed(DomainEvent):
    conversation_id: str = ""
    session_id: str = ""
    user_id: str = ""

    @property
    def event_type(self) -> str:
        return "ConversationClosed"
