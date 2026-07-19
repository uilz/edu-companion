"""Growth Repository — raw SQL via Database class."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from app.infrastructure.db.database import get_db
from app.domain.growth.aggregates import Milestone, EvolutionSnapshot


def _row_to_milestone(row: dict) -> Milestone:
    return Milestone(
        id=row["id"], workspace_id=row["workspace_id"],
        user_id=row["user_id"], type=row.get("type", ""),
        title=row.get("title", ""), description=row.get("description", ""),
        concept_id=row.get("concept_id", ""),
        day_number=row.get("day_number", 0),
        evidence_event=row.get("evidence_event", ""),
        detected_at=row.get("detected_at", datetime.now(timezone.utc)),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
    )


def _row_to_snapshot(row: dict) -> EvolutionSnapshot:
    return EvolutionSnapshot(
        id=row["id"], workspace_id=row["workspace_id"],
        day_number=row.get("day_number", 0),
        session_count=row.get("session_count", 0),
        concept_count=row.get("concept_count", 0),
        connection_count=row.get("connection_count", 0),
        top_concepts=row.get("top_concepts", ""),
        milestone_ids=row.get("milestone_ids", ""),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
    )


class GrowthRepo:
    def save_milestone(self, m: Milestone) -> None:
        db = get_db()
        db.insert("milestones", {
            "id": str(m.id), "workspace_id": str(m.workspace_id),
            "user_id": str(m.user_id), "type": m.type,
            "title": m.title, "description": m.description,
            "concept_id": m.concept_id, "day_number": m.day_number,
            "evidence_event": m.evidence_event,
            "detected_at": m.detected_at.isoformat(),
        })

    def find_milestones(self, ws_id: UUID, limit: int = 50) -> list[Milestone]:
        db = get_db()
        rows = db.fetchall(
            """SELECT id, workspace_id, user_id, type, title, description,
               concept_id, day_number, evidence_event, detected_at, created_at
               FROM milestones WHERE workspace_id = %s
               ORDER BY detected_at DESC LIMIT %s""",
            (str(ws_id), limit),
        )
        return [_row_to_milestone(r) for r in rows]

    def find_milestones_by_user(self, user_id: UUID, limit: int = 50) -> list[Milestone]:
        db = get_db()
        rows = db.fetchall(
            """SELECT id, workspace_id, user_id, type, title, description,
               concept_id, day_number, evidence_event, detected_at, created_at
               FROM milestones WHERE user_id = %s
               ORDER BY detected_at DESC LIMIT %s""",
            (str(user_id), limit),
        )
        return [_row_to_milestone(r) for r in rows]

    def upsert_snapshot(self, snap: EvolutionSnapshot) -> None:
        db = get_db()
        db.upsert("evolution_snapshots", {
            "id": str(snap.id), "workspace_id": str(snap.workspace_id),
            "day_number": snap.day_number,
            "session_count": snap.session_count,
            "concept_count": snap.concept_count,
            "connection_count": snap.connection_count,
            "top_concepts": snap.top_concepts,
            "milestone_ids": snap.milestone_ids,
        }, "id")

    def find_snapshots(self, ws_id: UUID, limit: int = 30) -> list[EvolutionSnapshot]:
        db = get_db()
        rows = db.fetchall(
            """SELECT id, workspace_id, day_number, session_count, concept_count,
               connection_count, top_concepts, milestone_ids, created_at
               FROM evolution_snapshots WHERE workspace_id = %s
               ORDER BY day_number DESC LIMIT %s""",
            (str(ws_id), limit),
        )
        return [_row_to_snapshot(r) for r in rows]

    def find_snapshot_by_day(self, ws_id: UUID, day: int) -> EvolutionSnapshot | None:
        db = get_db()
        row = db.fetchone(
            """SELECT id, workspace_id, day_number, session_count, concept_count,
               connection_count, top_concepts, milestone_ids, created_at
               FROM evolution_snapshots WHERE workspace_id = %s AND day_number = %s""",
            (str(ws_id), day),
        )
        return _row_to_snapshot(row) if row else None

    def get_latest_day(self, ws_id: UUID) -> int:
        db = get_db()
        row = db.fetchone(
            "SELECT COALESCE(day_count, 0) as max_day FROM workspaces WHERE id = %s",
            (str(ws_id),),
        )
        return row["max_day"] if row else 0
