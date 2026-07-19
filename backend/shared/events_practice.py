"""AppleGo Practice Domain Events."""
from __future__ import annotations
from dataclasses import dataclass
from shared.events import DomainEvent


@dataclass(frozen=True)
class PracticeStarted(DomainEvent):
    practice_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    title: str = ""

    @property
    def event_type(self) -> str:
        return "PracticeStarted"


@dataclass(frozen=True)
class AttemptSubmitted(DomainEvent):
    attempt_id: str = ""
    question_id: str = ""
    practice_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    is_correct: bool = False
    response_time_s: float = 0.0

    @property
    def event_type(self) -> str:
        return "AttemptSubmitted"


@dataclass(frozen=True)
class BreakthroughDetected(DomainEvent):
    attempt_id: str = ""
    question_id: str = ""
    practice_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    concept_id: str = ""

    @property
    def event_type(self) -> str:
        return "BreakthroughDetected"


@dataclass(frozen=True)
class PracticeCompleted(DomainEvent):
    practice_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    total_questions: int = 0
    correct_count: int = 0

    @property
    def event_type(self) -> str:
        return "PracticeCompleted"
