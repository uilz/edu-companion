"""
AppleGo Practice Domain — Practice, Question, Attempt.

Per Contract /vision/contracts/practice.html:
- I3: Attempts immutable (append-only)
- I4: AI reviews attempt, never reveals correct answer
- I7: Questions carry context (linked to Resources, Conversation turns)
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


class PracticeState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    REVIEWING = "reviewing"
    COMPLETED = "completed"


@dataclass
class Question:
    """A practice question. Contract I7: carries context (concept, source)."""
    id: UUID = field(default_factory=_uid)
    practice_id: UUID = field(default_factory=_uid)
    seq: int = 1
    text: str = ""
    concept_ids: str = ""          # JSON array
    context_source: str = ""        # resource_id | conversation_turn_id
    correct_answer: str = ""        # I4: hidden from user
    created_at: datetime = field(default_factory=_now)


@dataclass
class Attempt:
    """Immutable answer attempt. Contract I3: append-only, never overwritten."""
    id: UUID = field(default_factory=_uid)
    question_id: UUID = field(default_factory=_uid)
    user_id: UUID = field(default_factory=_uid)
    answer: str = ""
    is_correct: bool = False
    confidence: int = 0
    response_time_s: float = 0.0
    reviewed: bool = False          # I4: AI review flag
    review_comment: str = ""
    created_at: datetime = field(default_factory=_now)

    def review(self, is_correct_eval: bool, comment: str) -> None:
        self.reviewed = True
        self.review_comment = comment
        # I4: AI does not overwrite is_correct. Correctness is pre-computed.


@dataclass
class Practice:
    """Practice aggregate — a self-testing session.

    Contract I1: Belongs to Workspace.
    Contract I2: Questions generated from Knowledge gaps.
    """
    id: UUID = field(default_factory=_uid)
    workspace_id: UUID = field(default_factory=_uid)
    state: PracticeState = PracticeState.CREATED
    title: str = ""
    total_questions: int = 0
    correct_count: int = 0
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def start(self) -> None:
        if self.state in (PracticeState.CREATED, PracticeState.REVIEWING):
            self.state = PracticeState.ACTIVE
            self.updated_at = _now()

    def submit(self) -> None:
        if self.state == PracticeState.ACTIVE:
            self.state = PracticeState.REVIEWING
            self.updated_at = _now()

    def complete(self) -> None:
        self.state = PracticeState.COMPLETED
        self.updated_at = _now()
