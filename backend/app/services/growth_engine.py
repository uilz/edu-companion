"""
GrowthEngine — Consumer of all runtime events.

Per Contract /vision/contracts/growth.html:
- I1: Workspace-level AND user-level snapshots
- I2: Consumer only. Receives events from other runtimes.
- I3: Milestones derived from event patterns (not user-created)
- I4: Evolution Snapshot per day_number
- I5: Non-destructive recomputation
- I6: Cross-time queries

Asynchronous only. Growth never blocks user actions.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from uuid import UUID
from app.domain.growth.aggregates import Milestone, EvolutionSnapshot, MilestoneType
from app.infrastructure.db.repositories.growth_repo import GrowthRepo

logger = logging.getLogger(__name__)


class GrowthEngine:
    """Passive consumer. Subscribes to runtime events and derives milestones + snapshots."""

    def __init__(self, event_bus=None):
        self.repo = GrowthRepo()
        self._event_bus = event_bus

    async def _publish(self, event) -> None:
        if self._event_bus:
            try:
                await self._event_bus.publish(event)
            except Exception:
                logger.exception("Failed to publish %s", type(event).__name__)

    async def detect_breakthrough(self, practice_id: str, question_id: str,
                                   workspace_id: str, user_id: str,
                                   concept_id: str = "") -> Milestone | None:
        """Detect a breakthrough milestone. Contract I3: from event patterns."""
        ws_id = UUID(workspace_id)
        uid = UUID(user_id)
        day = self.repo.get_latest_day(ws_id)

        m = Milestone(
            workspace_id=ws_id, user_id=uid,
            type=MilestoneType.BREAKTHROUGH,
            title="概念突破",
            description=f"在练习中突破了概念 {concept_id}",
            concept_id=concept_id,
            day_number=day,
            evidence_event=practice_id,
        )
        self.repo.save_milestone(m)

        from shared.events_growth import MilestoneDetected
        await self._publish(MilestoneDetected(
            milestone_id=str(m.id), workspace_id=workspace_id,
            user_id=user_id, type=MilestoneType.BREAKTHROUGH,
            title=m.title, concept_id=concept_id, day_number=day,
        ))
        logger.info("Milestone: breakthrough for concept %s in ws %s", concept_id, workspace_id)
        return m

    async def detect_completion(self, resource_id: str, workspace_id: str,
                                  user_id: str, resource_title: str = "") -> Milestone | None:
        """Detect completion milestone."""
        ws_id = UUID(workspace_id)
        uid = UUID(user_id)
        day = self.repo.get_latest_day(ws_id)

        m = Milestone(
            workspace_id=ws_id, user_id=uid,
            type=MilestoneType.COMPLETION,
            title=f"完成: {resource_title}",
            description=f"完成了资源 {resource_title} 的学习",
            day_number=day,
            evidence_event=resource_id,
        )
        self.repo.save_milestone(m)

        from shared.events_growth import MilestoneDetected
        await self._publish(MilestoneDetected(
            milestone_id=str(m.id), workspace_id=workspace_id,
            user_id=user_id, type=MilestoneType.COMPLETION,
            title=m.title, day_number=day,
        ))
        return m

    async def detect_habit(self, workspace_id: str, user_id: str,
                            session_count: int) -> Milestone | None:
        """Detect habit milestone (N-session streak)."""
        ws_id = UUID(workspace_id)
        uid = UUID(user_id)
        day = self.repo.get_latest_day(ws_id)

        # Thresholds: 7, 21, 50, 100 sessions
        thresholds = {7: "7天连续学习", 21: "21天习惯养成", 50: "50天坚持", 100: "100天里程碑"}
        title = next((v for k, v in sorted(thresholds.items(), reverse=True)
                       if session_count >= k), "")
        if not title:
            return None

        m = Milestone(
            workspace_id=ws_id, user_id=uid,
            type=MilestoneType.HABIT,
            title=title,
            description=f"累计 {session_count} 个会话",
            day_number=day,
        )
        self.repo.save_milestone(m)

        from shared.events_growth import MilestoneDetected
        await self._publish(MilestoneDetected(
            milestone_id=str(m.id), workspace_id=workspace_id,
            user_id=user_id, type=MilestoneType.HABIT,
            title=m.title, day_number=day,
        ))
        return m

    async def compute_snapshot(self, workspace_id: str, user_id: str) -> EvolutionSnapshot:
        """Compute current day's evolution snapshot. Contract I4."""
        ws_id = UUID(workspace_id)
        day = self.repo.get_latest_day(ws_id)

        from app.infrastructure.db.database import get_db
        db = get_db()

        # Aggregate from existing data
        s_row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM sessions WHERE workspace_id = %s AND state = 'ended'",
            (workspace_id,),
        )
        session_count = s_row["cnt"] if s_row else 0

        m_row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM milestones WHERE workspace_id = %s",
            (workspace_id,),
        )
        concept_count = m_row["cnt"] if m_row else 0

        snap = EvolutionSnapshot(
            workspace_id=ws_id, day_number=day,
            session_count=session_count,
            concept_count=concept_count,
            connection_count=0,
            top_concepts=json.dumps([]),
            milestone_ids=json.dumps([]),
        )
        self.repo.upsert_snapshot(snap)

        from shared.events_growth import EvolutionSnapshotComputed
        await self._publish(EvolutionSnapshotComputed(
            snapshot_id=str(snap.id), workspace_id=workspace_id,
            user_id=user_id, day_number=day,
            session_count=session_count, concept_count=concept_count,
        ))
        return snap

    # I6: Cross-time queries
    async def get_trajectory(self, workspace_id: str, from_day: int,
                               to_day: int) -> dict:
        """Cross-time comparison. Contract I6."""
        from_day = max(from_day, 1)
        to_day = max(to_day, from_day)

        repo = self.repo
        snap_from = repo.find_snapshot_by_day(UUID(workspace_id), from_day)
        snap_to = repo.find_snapshot_by_day(UUID(workspace_id), to_day)

        return {
            "from_day": from_day,
            "to_day": to_day,
            "delta_sessions": (snap_to.session_count if snap_to else 0) - (snap_from.session_count if snap_from else 0),
            "delta_concepts": (snap_to.concept_count if snap_to else 0) - (snap_from.concept_count if snap_from else 0),
        }
