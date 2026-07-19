"""
Resource & ReadingState Repository — raw SQL via Database class.
"""

from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from app.infrastructure.db.database import get_db
from app.domain.resource.aggregates import Resource, ResourceState, ReadingState


def _row_to_resource(row: dict) -> Resource:
    return Resource(
        id=row["id"],
        workspace_id=row["workspace_id"],
        material_id=row["material_id"],
        title=row.get("title", ""),
        state=ResourceState(row["state"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_reading_state(row: dict) -> ReadingState:
    return ReadingState(
        id=row["id"],
        resource_id=row["resource_id"],
        user_id=row["user_id"],
        position_page=row.get("position_page", 0),
        position_scroll=row.get("position_scroll", 0.0),
        last_read_at=row.get("last_read_at", datetime.now(timezone.utc)),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
        updated_at=row.get("updated_at", datetime.now(timezone.utc)),
    )


class ResourceRepo:
    """Repository for Resource aggregate."""

    def find_by_id(self, res_id: UUID) -> Resource | None:
        db = get_db()
        row = db.fetchone(
            "SELECT id, workspace_id, material_id, title, state, created_at, updated_at "
            "FROM resources WHERE id = %s",
            (str(res_id),),
        )
        return _row_to_resource(row) if row else None

    def find_by_workspace(self, ws_id: UUID) -> list[Resource]:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, workspace_id, material_id, title, state, created_at, updated_at "
            "FROM resources WHERE workspace_id = %s ORDER BY created_at DESC",
            (str(ws_id),),
        )
        return [_row_to_resource(r) for r in rows]

    def save(self, res: Resource) -> None:
        db = get_db()
        db.upsert(
            "resources",
            {
                "id": str(res.id),
                "workspace_id": str(res.workspace_id),
                "material_id": str(res.material_id),
                "title": res.title,
                "state": res.state.value,
                "updated_at": res.updated_at.isoformat(),
            },
            "id",
        )


class ReadingStateRepo:
    """Repository for ReadingState value object."""

    def find_by_resource_and_user(self, res_id: UUID, user_id: UUID) -> ReadingState | None:
        db = get_db()
        row = db.fetchone(
            "SELECT id, resource_id, user_id, position_page, position_scroll, "
            "last_read_at, created_at, updated_at "
            "FROM reading_states WHERE resource_id = %s AND user_id = %s",
            (str(res_id), str(user_id)),
        )
        return _row_to_reading_state(row) if row else None

    def upsert(self, state: ReadingState) -> None:
        db = get_db()
        db.upsert(
            "reading_states",
            {
                "id": str(state.id),
                "resource_id": str(state.resource_id),
                "user_id": str(state.user_id),
                "position_page": state.position_page,
                "position_scroll": state.position_scroll,
                "last_read_at": state.last_read_at.isoformat(),
                "updated_at": state.updated_at.isoformat(),
            },
            "id",
        )

    def update_position(self, res_id: UUID, user_id: UUID, page: int, scroll: float) -> None:
        db = get_db()
        db.execute(
            "UPDATE reading_states SET position_page = %s, position_scroll = %s, "
            "last_read_at = %s, updated_at = %s "
            "WHERE resource_id = %s AND user_id = %s",
            (page, scroll, datetime.now(timezone.utc).isoformat(),
             datetime.now(timezone.utc).isoformat(),
             str(res_id), str(user_id)),
        )
