"""
Workspace Repository — raw SQL via Database class.
"""

from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from app.infrastructure.db.database import get_db
from app.domain.workspace.aggregates import Workspace, WorkspaceState, Session, SessionState, Mission, SessionArtifact


def _row_to_workspace(row: dict) -> Workspace:
    return Workspace(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        icon=row.get("icon", "book"),
        color=row.get("color", "#5a8f6b"),
        state=WorkspaceState(row["state"]),
        active_session_id=row.get("active_session_id"),
        day_count=row.get("day_count", 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_session(row: dict) -> Session:
    mission = Mission(
        source=row.get("mission_source", ""),
        text=row.get("mission_text", ""),
        state=row.get("mission_state", "active"),
    )
    return Session(
        id=row["id"],
        workspace_id=row["workspace_id"],
        project_id=row.get("project_id"),
        state=SessionState(row["state"]),
        title=row.get("title", ""),
        mission=mission,
        last_refresh=row.get("last_refresh", datetime.now(timezone.utc)),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
        ended_at=row.get("ended_at"),
    )


class WorkspaceRepo:
    """Repository for Workspace aggregate."""
    
    def find_by_id(self, ws_id: UUID) -> Workspace | None:
        db = get_db()
        row = db.fetchone(
            "SELECT id, user_id, name, icon, color, state, active_session_id, day_count, created_at, updated_at "
            "FROM workspaces WHERE id = %s",
            (str(ws_id),),
        )
        return _row_to_workspace(row) if row else None

    def find_by_user(self, user_id: UUID) -> list[Workspace]:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, user_id, name, icon, color, state, active_session_id, day_count, created_at, updated_at "
            "FROM workspaces WHERE user_id = %s ORDER BY created_at DESC",
            (str(user_id),),
        )
        return [_row_to_workspace(r) for r in rows]

    def save(self, ws: Workspace) -> None:
        db = get_db()
        db.upsert(
            "workspaces",
            {
                "id": str(ws.id),
                "user_id": str(ws.user_id),
                "name": ws.name,
                "icon": ws.icon,
                "color": ws.color,
                "state": ws.state.value,
                "active_session_id": str(ws.active_session_id) if ws.active_session_id else None,
                "day_count": ws.day_count,
                "updated_at": ws.updated_at.isoformat(),
            },
            "id",
        )


class SessionRepo:
    """Repository for Session aggregate."""
    
    def find_by_id(self, session_id: UUID) -> Session | None:
        db = get_db()
        row = db.fetchone(
            "SELECT id, workspace_id, project_id, state, title, "
            "mission_source, mission_text, mission_state, "
            "last_refresh, created_at, ended_at "
            "FROM sessions WHERE id = %s",
            (str(session_id),),
        )
        if not row:
            return None
        session = _row_to_session(row)
        # Load artifacts
        art_rows = db.fetchall(
            "SELECT artifact_type, artifact_id, position FROM session_artifacts WHERE session_id = %s",
            (str(session_id),),
        )
        for ar in art_rows:
            session.artifacts.append(SessionArtifact(
                artifact_type=ar["artifact_type"],
                artifact_id=ar["artifact_id"],
                position=ar.get("position"),
            ))
        return session

    def find_active_by_workspace(self, ws_id: UUID) -> Session | None:
        db = get_db()
        row = db.fetchone(
            "SELECT id, workspace_id, project_id, state, title, "
            "mission_source, mission_text, mission_state, "
            "last_refresh, created_at, ended_at "
            "FROM sessions WHERE workspace_id = %s AND state = 'active'",
            (str(ws_id),),
        )
        return _row_to_session(row) if row else None

    def find_paused_by_workspace(self, ws_id: UUID) -> Session | None:
        db = get_db()
        row = db.fetchone(
            "SELECT id, workspace_id, project_id, state, title, "
            "mission_source, mission_text, mission_state, "
            "last_refresh, created_at, ended_at "
            "FROM sessions WHERE workspace_id = %s AND state = 'paused' "
            "ORDER BY last_refresh DESC LIMIT 1",
            (str(ws_id),),
        )
        return _row_to_session(row) if row else None

    def find_by_workspace(self, ws_id: UUID) -> list[Session]:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, workspace_id, project_id, state, title, "
            "mission_source, mission_text, mission_state, "
            "last_refresh, created_at, ended_at "
            "FROM sessions WHERE workspace_id = %s ORDER BY created_at DESC",
            (str(ws_id),),
        )
        return [_row_to_session(r) for r in rows]

    def save(self, session: Session) -> None:
        db = get_db()
        db.upsert(
            "sessions",
            {
                "id": str(session.id),
                "workspace_id": str(session.workspace_id),
                "project_id": str(session.project_id) if session.project_id else None,
                "state": session.state.value,
                "title": session.title,
                "mission_source": session.mission.source,
                "mission_text": session.mission.text,
                "mission_state": session.mission.state,
                "last_refresh": session.last_refresh.isoformat(),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            },
            "id",
        )
        # Save artifacts
        if session.artifacts:
            db.execute(
                "DELETE FROM session_artifacts WHERE session_id = %s",
                (str(session.id),),
            )
            for art in session.artifacts:
                db.execute(
                    "INSERT INTO session_artifacts (session_id, artifact_type, artifact_id, position) "
                    "VALUES (%s, %s, %s, %s)",
                    (str(session.id), art.artifact_type, str(art.artifact_id), 
                     __import__('json').dumps(art.position) if art.position else None),
                )

    def update_state(self, session_id: UUID, state: SessionState) -> None:
        db = get_db()
        db.execute(
            "UPDATE sessions SET state = %s, last_refresh = %s WHERE id = %s",
            (state.value, datetime.now(timezone.utc).isoformat(), str(session_id)),
        )
