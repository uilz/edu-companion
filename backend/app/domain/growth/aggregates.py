"""
AppleGo Growth Domain — Milestone, EvolutionSnapshot.

Per Contract /vision/contracts/growth.html:
- I1: Two levels — workspace-level and user-level
- I2: Consumer, not producer — observes events from other runtimes
- I3: Milestones derived from event patterns
- I4: EvolutionSnapshots materialized per day_number
- I6: Cross-time queries
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> UUID:
    return uuid4()


class MilestoneType:
    CONCEPT_FIRST = "concept_first"       # First time encountering a concept
    BREAKTHROUGH = "breakthrough"          # Depth transition (wrestling→stable)
    COMPLETION = "completion"             # Resource/practice completed
    HABIT = "habit"                       # N sessions created (milestone threshold)


@dataclass
class Milestone:
    """Derived growth event. Contract I3: detected from event patterns."""
    id: UUID = field(default_factory=_uid)
    workspace_id: UUID = field(default_factory=_uid)
    user_id: UUID = field(default_factory=_uid)
    type: str = ""
    title: str = ""
    description: str = ""
    concept_id: str = ""
    day_number: int = 0
    evidence_event: str = ""              # event_id from source runtime
    detected_at: datetime = field(default_factory=_now)
    created_at: datetime = field(default_factory=_now)


@dataclass
class EvolutionSnapshot:
    """Materialized daily growth snapshot. Contract I4: per day_number."""
    id: UUID = field(default_factory=_uid)
    workspace_id: UUID = field(default_factory=_uid)
    day_number: int = 0
    session_count: int = 0
    concept_count: int = 0
    connection_count: int = 0
    top_concepts: str = ""                # JSON
    milestone_ids: str = ""               # JSON
    created_at: datetime = field(default_factory=_now)
