"""
WorkspaceRuntime — Session lifecycle orchestration.

Coordinates: Workspace + Session aggregates.
Contract: /vision/contracts/workspace.html
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional

from app.domain.workspace.aggregates import (
    Workspace, WorkspaceState, Session, SessionState, Mission,
)
from app.infrastructure.db.repositories.workspace_repo import WorkspaceRepo, SessionRepo

logger = logging.getLogger(__name__)


class WorkspaceRuntime:
    """Manages the lifecycle of workspaces and their sessions."""
    
    def __init__(self, event_bus=None):
        self.ws_repo = WorkspaceRepo()
        self.sess_repo = SessionRepo()
        self._event_bus = event_bus

    async def _publish(self, event) -> None:
        if self._event_bus:
            try:
                await self._event_bus.publish(event)
            except Exception:
                logger.exception("Failed to publish event %s", type(event).__name__)

    # ── Workspace Operations ──

    async def create_workspace(self, user_id: UUID, name: str) -> Workspace:
        """Create a new workspace. I5: AI cannot call this — only user-driven API."""
        ws = Workspace(
            user_id=user_id,
            name=name,
            state=WorkspaceState.CREATED,
        )
        self.ws_repo.save(ws)
        from shared.events_workspace import WorkspaceCreated
        await self._publish(WorkspaceCreated(
            workspace_id=str(ws.id),
            user_id=str(user_id),
            name=name,
        ))
        logger.info("Workspace created: %s (user=%s)", ws.id, user_id)
        return ws

    async def get_workspaces(self, user_id: UUID) -> list[Workspace]:
        return self.ws_repo.find_by_user(user_id)

    async def get_workspace(self, ws_id: UUID) -> Workspace | None:
        return self.ws_repo.find_by_id(ws_id)

    # ── Session Lifecycle ──

    async def enter_workspace(self, ws_id: UUID, user_id: UUID) -> Session:
        """Enter a workspace. I3: Opens a paused session or creates a new one.
        
        Returns the active session.
        """
        ws = self.ws_repo.find_by_id(ws_id)
        if not ws:
            raise ValueError(f"Workspace {ws_id} not found")
        if ws.state == WorkspaceState.ENDED:
            raise ValueError(f"Workspace {ws_id} has ended")

        # Activate workspace if needed
        if ws.state in (WorkspaceState.CREATED, WorkspaceState.DORMANT):
            ws.activate()
            from shared.events_workspace import WorkspaceActivated
            await self._publish(WorkspaceActivated(
                workspace_id=str(ws.id), user_id=str(user_id),
            ))

        # Check for paused session to resume
        paused = self.sess_repo.find_paused_by_workspace(ws_id)
        if paused:
            paused.resume()
            self.sess_repo.save(paused)
            ws.active_session_id = paused.id
            ws.updated_at = datetime.now(timezone.utc)
            self.ws_repo.save(ws)
            from shared.events_workspace import SessionResumed
            await self._publish(SessionResumed(
                session_id=str(paused.id), workspace_id=str(ws_id), user_id=str(user_id),
            ))
            logger.info("Session resumed: %s in workspace %s", paused.id, ws_id)
            return paused

        # Check for active session (already in)
        active = self.sess_repo.find_active_by_workspace(ws_id)
        if active:
            return active

        # Create new session
        return await self._create_session(ws_id, user_id)

    async def pause_session(self, ws_id: UUID, user_id: UUID) -> None:
        """Pause the active session. State: active → paused."""
        active = self.sess_repo.find_active_by_workspace(ws_id)
        if not active:
            logger.warning("No active session to pause in workspace %s", ws_id)
            return
        
        active.pause()
        self.sess_repo.save(active)
        
        # Update workspace
        ws = self.ws_repo.find_by_id(ws_id)
        if ws:
            ws.active_session_id = None
            ws.updated_at = datetime.now(timezone.utc)
            self.ws_repo.save(ws)
        
        from shared.events_workspace import SessionPaused
        await self._publish(SessionPaused(
            session_id=str(active.id), workspace_id=str(ws_id), user_id=str(user_id),
        ))
        logger.info("Session paused: %s", active.id)

    async def end_session(self, ws_id: UUID, user_id: UUID) -> None:
        """End the active session. State: active → ended."""
        active = self.sess_repo.find_active_by_workspace(ws_id)
        if not active:
            logger.warning("No active session to end in workspace %s", ws_id)
            return
        
        active.end()
        self.sess_repo.save(active)
        
        ws = self.ws_repo.find_by_id(ws_id)
        if ws:
            ws.active_session_id = None
            ws.day_count += 1
            ws.updated_at = datetime.now(timezone.utc)
            self.ws_repo.save(ws)
        
        from shared.events_workspace import SessionEnded
        await self._publish(SessionEnded(
            session_id=str(active.id), workspace_id=str(ws_id), user_id=str(user_id),
        ))
        logger.info("Session ended: %s", active.id)

    async def _create_session(self, ws_id: UUID, user_id: UUID) -> Session:
        """Create a new session. State: created → active."""
        session = Session(workspace_id=ws_id, state=SessionState.CREATED)
        session.activate()
        self.sess_repo.save(session)
        
        ws = self.ws_repo.find_by_id(ws_id)
        if ws:
            ws.active_session_id = session.id
            ws.updated_at = datetime.now(timezone.utc)
            self.ws_repo.save(ws)
        
        from shared.events_workspace import SessionCreated
        await self._publish(SessionCreated(
            session_id=str(session.id), workspace_id=str(ws_id), user_id=str(user_id),
            title=session.title,
        ))
        logger.info("Session created: %s in workspace %s", session.id, ws_id)
        return session
