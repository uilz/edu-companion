"""Workspace API — WorkspaceRuntime-backed REST endpoints.

AppleGo Demo6.0 | Domain Freeze v1.1
All write operations go through WorkspaceRuntime service.
Read operations query DB directly for efficiency.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.workspace.schemas import (
    CreateSessionRequest,
    CreateWorkspaceRequest,
    RoadmapResponse,
    SearchResultItem,
    SessionItem,
    SessionLifecycleResponse,
    TimelineEntry,
    WorkspaceDetail,
    WorkspaceItem,
)
from app.application.di import get_workspace_runtime
from app.domain.auth.dependencies import current_user_id
from app.infrastructure.db.database import get_db
from app.infrastructure.db.repositories.workspace_repo import SessionRepo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspace"])


# ════════════════════════════════════════════════════════════════════
# State → backward-compat mappings
# ════════════════════════════════════════════════════════════════════

_STATE_TO_STATUS: dict[str, str] = {
    "created": "pending",
    "active": "active",
    "paused": "paused",
    "ended": "completed",
}

_STATE_TO_STAGE: dict[str, str] = {
    "created": "intro",
    "active": "learn",
    "paused": "paused",
    "ended": "completed",
}

_STATE_TO_PROGRESS: dict[str, int] = {
    "created": 0,
    "active": 50,
    "paused": 50,
    "ended": 100,
}


def _state_to_backcompat(state: str) -> tuple[str, str, int]:
    """Map domain state to (status, stage, progress) for frontend compat."""
    return (
        _STATE_TO_STATUS.get(state, "pending"),
        _STATE_TO_STAGE.get(state, "intro"),
        _STATE_TO_PROGRESS.get(state, 0),
    )


def _session_to_item(row: dict) -> SessionItem:
    """Convert a session DB row to SessionItem."""
    state = row.get("state", "created")
    status, stage, progress = _state_to_backcompat(state)
    return SessionItem(
        id=str(row["id"]),
        title=row.get("title", ""),
        description=row.get("mission_text", ""),
        stage=stage,
        progress=progress,
        estimated_minutes=25,
        created_at=str(row.get("created_at", "")),
        status=status,
        state=state,
        mission_source=row.get("mission_source", ""),
        mission_text=row.get("mission_text", ""),
        ended_at=str(row["ended_at"]) if row.get("ended_at") else None,
    )


def _workspace_to_item(row: dict, sess_counts: dict | None = None) -> WorkspaceItem:
    """Convert a workspace DB row to WorkspaceItem."""
    if sess_counts is None:
        sess_counts = {}
    ws_id = str(row["id"])
    counts = sess_counts.get(ws_id, {})
    return WorkspaceItem(
        id=ws_id,
        name=row.get("name", ""),
        icon=row.get("icon", "book"),
        color=row.get("color", "#5a8f6b"),
        state=row.get("state", "created"),
        day_count=row.get("day_count", 0),
        active_sessions_count=counts.get("active", 0),
        completed_sessions_count=counts.get("ended", 0),
        created_at=str(row.get("created_at", "")),
    )


def _workspace_to_detail(row: dict, sess_counts: dict | None = None) -> WorkspaceDetail:
    """Convert a workspace DB row to WorkspaceDetail."""
    if sess_counts is None:
        sess_counts = {"total": 0, "active": 0, "ended": 0}
    total = sess_counts.get("total", 0)
    ended = sess_counts.get("ended", 0)
    return WorkspaceDetail(
        id=str(row["id"]),
        name=row.get("name", ""),
        icon=row.get("icon", "book"),
        color=row.get("color", "#5a8f6b"),
        state=row.get("state", "created"),
        day_count=row.get("day_count", 0),
        total_sessions=total,
        active_sessions=sess_counts.get("active", 0),
        overall_progress=round(ended / total * 100) if total > 0 else 0,
    )


def _load_session_counts(db, ws_ids: list[str]) -> dict:
    """Load session counts for multiple workspaces in one query."""
    if not ws_ids:
        return {}
    placeholders = ",".join(["%s"] * len(ws_ids))
    rows = db.fetchall(
        f"""SELECT workspace_id::text as ws_id,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE state IN ('active','paused')) as active,
                   COUNT(*) FILTER (WHERE state = 'ended') as ended
            FROM sessions WHERE workspace_id IN ({placeholders})
            GROUP BY workspace_id""",
        tuple(ws_ids),
    )
    result: dict = {}
    for r in rows:
        result[r["ws_id"]] = {
            "total": r.get("total", 0),
            "active": r.get("active", 0),
            "ended": r.get("ended", 0),
        }
    return result


# ════════════════════════════════════════════════════════════════════
# Endpoints
# ════════════════════════════════════════════════════════════════════


@router.get("", response_model=list[WorkspaceItem])
async def list_workspaces(
    user_id: str = Depends(current_user_id),
):
    """List all workspaces for the current user."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    db = get_db()
    uid = UUID(user_id)

    rows = db.fetchall(
        """SELECT id, user_id, name, icon, color, state,
                  active_session_id, day_count, created_at, updated_at
           FROM workspaces WHERE user_id = %s ORDER BY created_at DESC""",
        (str(uid),),
    )

    if not rows:
        return []

    # Bulk-load session counts
    ws_ids = [str(r["id"]) for r in rows]
    counts = _load_session_counts(db, ws_ids)

    return [_workspace_to_item(r, counts) for r in rows]


@router.post("", response_model=WorkspaceItem)
async def create_workspace(
    body: CreateWorkspaceRequest,
    user_id: str = Depends(current_user_id),
):
    """Create a new workspace. I5: user-driven only, AI cannot call this."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    runtime = get_workspace_runtime()
    ws = await runtime.create_workspace(UUID(user_id), body.name)

    return WorkspaceItem(
        id=str(ws.id),
        name=ws.name,
        icon=ws.icon,
        color=ws.color,
        state=ws.state.value,
        day_count=ws.day_count,
        active_sessions_count=0,
        completed_sessions_count=0,
        created_at=str(ws.created_at),
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(
    workspace_id: str,
    user_id: str = Depends(current_user_id),
):
    """Get workspace detail with derived stats."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    db = get_db()
    row = db.fetchone(
        """SELECT id, user_id, name, icon, color, state,
                  active_session_id, day_count, created_at, updated_at
           FROM workspaces WHERE id = %s""",
        (workspace_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="工作区不存在")

    counts = _load_session_counts(db, [workspace_id])
    return _workspace_to_detail(row, counts.get(workspace_id, {}))


@router.get("/{workspace_id}/sessions", response_model=list[SessionItem])
async def list_workspace_sessions(
    workspace_id: str,
    user_id: str = Depends(current_user_id),
):
    """List all sessions in a workspace, ordered by newest first."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    db = get_db()

    # Verify workspace exists
    exists = db.fetchone("SELECT 1 FROM workspaces WHERE id = %s", (workspace_id,))
    if not exists:
        raise HTTPException(status_code=404, detail="工作区不存在")

    rows = db.fetchall(
        """SELECT id, workspace_id, project_id, state, title,
                  mission_source, mission_text, mission_state,
                  last_refresh, created_at, ended_at
           FROM sessions WHERE workspace_id = %s
           ORDER BY created_at DESC""",
        (workspace_id,),
    )
    return [_session_to_item(r) for r in rows]


@router.get("/{workspace_id}/timeline", response_model=list[TimelineEntry])
async def get_workspace_timeline(
    workspace_id: str,
    user_id: str = Depends(current_user_id),
):
    """Get workspace timeline. Mock data for now — scope: future LOOP."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    db = get_db()
    exists = db.fetchone("SELECT 1 FROM workspaces WHERE id = %s", (workspace_id,))
    if not exists:
        raise HTTPException(status_code=404, detail="工作区不存在")

    # Build timeline from real sessions (basic: group by created_at day)
    rows = db.fetchall(
        """SELECT id, title, state, created_at
           FROM sessions WHERE workspace_id = %s
           ORDER BY created_at DESC""",
        (workspace_id,),
    )

    entries: list[TimelineEntry] = []
    seen_dates: set[str] = set()
    for r in rows:
        created = str(r.get("created_at", ""))
        date_label = created[:10] if created else "未知"
        if date_label not in seen_dates:
            seen_dates.add(date_label)
            status, stage, progress = _state_to_backcompat(r.get("state", "created"))
            entries.append(TimelineEntry(
                date_label=date_label,
                items=[TimelineItem(
                    type="session",
                    title=r.get("title", "未命名会话"),
                    meta=f"{progress}% · {status}",
                    session_id=str(r["id"]),
                )],
            ))

    if not entries:
        return [TimelineEntry(date_label="暂无活动", items=[])]
    return entries


@router.get("/{workspace_id}/roadmap", response_model=RoadmapResponse)
async def get_workspace_roadmap(
    workspace_id: str,
    user_id: str = Depends(current_user_id),
):
    """Get workspace roadmap. Mock data for now — scope: future LOOP."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    db = get_db()
    exists = db.fetchone("SELECT 1 FROM workspaces WHERE id = %s", (workspace_id,))
    if not exists:
        raise HTTPException(status_code=404, detail="工作区不存在")

    # Basic roadmap from sessions
    rows = db.fetchall(
        "SELECT title, state FROM sessions WHERE workspace_id = %s ORDER BY created_at",
        (workspace_id,),
    )
    if not rows:
        return RoadmapResponse(title="学习路线", overall_progress=0, stages=[])

    stages = []
    for r in rows:
        title = r.get("title", "未命名")
        state = r.get("state", "created")
        map_status = {"ended": "done", "active": "active", "paused": "paused"}.get(state, "future")
        stages.append({
            "name": title,
            "status": map_status,
            "desc": f"状态: {state}",
            "stats": "",
            "badge": state,
        })

    done = sum(1 for s in stages if s["status"] == "done")
    progress = round(done / len(stages) * 100) if stages else 0
    return RoadmapResponse(
        title="学习路线",
        overall_progress=progress,
        stages=[{
            "name": s["name"], "status": s["status"],
            "desc": s["desc"], "stats": s["stats"], "badge": s["badge"],
        } for s in stages],
    )


# ════════════════════════════════════════════════════════════════════
# Session Lifecycle (new — Demo6.0 Domain Model)
# ════════════════════════════════════════════════════════════════════


@router.post("/{workspace_id}/enter", response_model=SessionLifecycleResponse)
async def enter_workspace(
    workspace_id: str,
    user_id: str = Depends(current_user_id),
):
    """Enter a workspace. Resumes paused session or creates a new one.

    Contract I3: One active Session per Workspace.
    Returns the active session.
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    runtime = get_workspace_runtime()
    try:
        session = await runtime.enter_workspace(UUID(workspace_id), UUID(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SessionLifecycleResponse(
        session_id=str(session.id),
        workspace_id=str(session.workspace_id),
        state=session.state.value,
        title=session.title,
    )


@router.post("/{workspace_id}/pause", response_model=SessionLifecycleResponse)
async def pause_session(
    workspace_id: str,
    user_id: str = Depends(current_user_id),
):
    """Pause the active session in this workspace."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    runtime = get_workspace_runtime()
    await runtime.pause_session(UUID(workspace_id), UUID(user_id))

    repo = SessionRepo()
    paused = repo.find_paused_by_workspace(UUID(workspace_id))
    return SessionLifecycleResponse(
        session_id=str(paused.id) if paused else "",
        workspace_id=workspace_id,
        state="paused",
        title=paused.title if paused else "",
    )


@router.post("/{workspace_id}/end", response_model=SessionLifecycleResponse)
async def end_session(
    workspace_id: str,
    user_id: str = Depends(current_user_id),
):
    """End the active session in this workspace. Irreversible."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    runtime = get_workspace_runtime()
    await runtime.end_session(UUID(workspace_id), UUID(user_id))

    # Find the most recently ended session for this workspace
    rows = get_db().fetchall(
        """SELECT id FROM sessions WHERE workspace_id = %s AND state = 'ended'
           ORDER BY ended_at DESC LIMIT 1""",
        (workspace_id,),
    )
    sid = str(rows[0]["id"]) if rows else ""

    return SessionLifecycleResponse(
        session_id=sid,
        workspace_id=workspace_id,
        state="ended",
        title="",
    )


@router.post("/{workspace_id}/sessions", response_model=SessionLifecycleResponse)
async def create_workspace_session(
    workspace_id: str,
    body: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
):
    """Create a new session in the workspace.

    Note: In Demo6.0, session creation is handled by enter_workspace (I3).
    This endpoint remains for explicit session creation scenarios.
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    runtime = get_workspace_runtime()
    session = await runtime.enter_workspace(UUID(workspace_id), UUID(user_id))
    if body.title:
        session.title = body.title
        SessionRepo().save(session)

    return SessionLifecycleResponse(
        session_id=str(session.id),
        workspace_id=str(session.workspace_id),
        state=session.state.value,
        title=session.title,
    )


# ════════════════════════════════════════════════════════════════════
# Search
# ════════════════════════════════════════════════════════════════════


@router.get("/{workspace_id}/search", response_model=list[SearchResultItem])
async def search_workspace(
    workspace_id: str,
    q: str = Query(default="", description="搜索关键词"),
    user_id: str = Depends(current_user_id),
):
    """Search within a workspace (sessions only for now)."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    db = get_db()
    exists = db.fetchone("SELECT 1 FROM workspaces WHERE id = %s", (workspace_id,))
    if not exists:
        raise HTTPException(status_code=404, detail="工作区不存在")

    if not q.strip():
        return []

    query = f"%{q.strip().lower()}%"
    rows = db.fetchall(
        """SELECT id, title, mission_text, state
           FROM sessions WHERE workspace_id = %s
           AND (LOWER(title) LIKE %s OR LOWER(mission_text) LIKE %s)
           LIMIT 10""",
        (workspace_id, query, query),
    )

    results: list[SearchResultItem] = []
    for r in rows:
        status, _, progress = _state_to_backcompat(r.get("state", "created"))
        results.append(SearchResultItem(
            type="session",
            title=r.get("title", "未命名"),
            snippet=(r.get("mission_text", "") or "")[:100],
            meta=f"进度 {progress}%",
            badge=status,
        ))

    return results
