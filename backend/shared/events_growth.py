"""AppleGo Growth Domain Events."""
from __future__ import annotations
from dataclasses import dataclass
from shared.events import DomainEvent


@dataclass(frozen=True)
class MilestoneDetected(DomainEvent):
    milestone_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    type: str = ""
    title: str = ""
    concept_id: str = ""
    day_number: int = 0

    @property
    def event_type(self) -> str:
        return "MilestoneDetected"


@dataclass(frozen=True)
class EvolutionSnapshotComputed(DomainEvent):
    snapshot_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    day_number: int = 0
    session_count: int = 0
    concept_count: int = 0

    @property
    def event_type(self) -> str:
        return "EvolutionSnapshotComputed"


@dataclass(frozen=True)
class TrajectoryUpdated(DomainEvent):
    workspace_id: str = ""
    user_id: str = ""
    from_day: int = 0
    to_day: int = 0
    delta_concepts: int = 0
    delta_sessions: int = 0

    @property
    def event_type(self) -> str:
        return "TrajectoryUpdated"
