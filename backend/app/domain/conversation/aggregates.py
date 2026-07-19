"""
AppleGo Conversation Domain — Conversation, Turn, ContextSnapshot.

Per Contract /vision/contracts/conversation.html:
- Conversation: belongs to Session, lifecycle: created → active ⇄ paused → closed
- Turn: immutable user-ai exchange with context snapshot reference
- ContextSnapshot: the state-of-the-world when AI responded
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


class ConversationState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


@dataclass
class ContextSnapshot:
    """The full context assembled for an AI response. Contract I1."""
    id: UUID = field(default_factory=_uid)
    conversation_id: UUID | None = None
    reading_page: int = 0
    reading_scroll: float = 0.0
    memory_tier: str = ""              # JSON: active memory entries
    knowledge_concepts: str = ""       # JSON: {concept_id: depth}
    captured_at: datetime = field(default_factory=_now)


@dataclass
class Turn:
    """Immutable user-AI exchange. Contract I6: every turn preserved."""
    id: UUID = field(default_factory=_uid)
    conversation_id: UUID = field(default_factory=_uid)
    seq: int = 1
    user_message: str = ""
    ai_response: str = ""
    context_snapshot_id: UUID | None = None
    orchestration: str = ""            # JSON: {decision, artifact_type, artifact_id}
    created_at: datetime = field(default_factory=_now)


@dataclass
class Conversation:
    """Conversation aggregate — manages dialogue turns within a session.

    Contract I1: Context assembled from reading position + workspace memory + learner model.
    Contract I6: Every turn replayable.
    Contract I8: Post-response orchestration recorded.
    """
    id: UUID = field(default_factory=_uid)
    session_id: UUID = field(default_factory=_uid)
    state: ConversationState = ConversationState.CREATED
    title: str = ""
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def activate(self) -> None:
        if self.state in (ConversationState.CREATED, ConversationState.PAUSED):
            self.state = ConversationState.ACTIVE
            self.updated_at = _now()
        else:
            raise ValueError(f"Cannot activate conversation in state {self.state}")

    def pause(self) -> None:
        if self.state == ConversationState.ACTIVE:
            self.state = ConversationState.PAUSED
            self.updated_at = _now()

    def resume(self) -> None:
        if self.state == ConversationState.PAUSED:
            self.state = ConversationState.ACTIVE
            self.updated_at = _now()

    def close(self) -> None:
        if self.state in (ConversationState.ACTIVE, ConversationState.PAUSED):
            self.state = ConversationState.CLOSED
            self.updated_at = _now()
