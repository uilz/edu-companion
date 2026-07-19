"""
ReadingRuntime — Intake observation service.

Per Contract /vision/contracts/resource.html:
- Manages Resource lifecycle: closed → open ⇄ completed
- Tracks ReadingState per user per resource (I1, I2)
- Manages Highlights (I3)
- Publishes events for Companion observation
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID
from app.domain.resource.aggregates import Resource, ResourceState, ReadingState, Highlight
from app.infrastructure.db.repositories.resource_repo import ResourceRepo, ReadingStateRepo

logger = logging.getLogger(__name__)


class ReadingRuntime:
    """Manages resource lifecycle and intake observation."""

    def __init__(self, event_bus=None):
        self.res_repo = ResourceRepo()
        self.state_repo = ReadingStateRepo()
        self._event_bus = event_bus

    async def _publish(self, event) -> None:
        if self._event_bus:
            try:
                await self._event_bus.publish(event)
            except Exception:
                logger.exception("Failed to publish %s", type(event).__name__)

    async def open_resource(self, res_id: UUID, user_id: UUID) -> Resource:
        """Open a resource. Contract: Closed → Open."""
        res = self.res_repo.find_by_id(res_id)
        if not res:
            raise ValueError(f"Resource {res_id} not found")
        res.open()
        self.res_repo.save(res)

        # Ensure ReadingState exists
        state = self.state_repo.find_by_resource_and_user(res_id, user_id)
        if not state:
            state = ReadingState(resource_id=res_id, user_id=user_id)
            self.state_repo.upsert(state)

        from shared.events_resource import ResourceOpened
        await self._publish(ResourceOpened(
            resource_id=str(res_id), workspace_id=str(res.workspace_id), user_id=str(user_id),
        ))
        logger.info("Resource opened: %s (user=%s)", res_id, user_id)
        return res

    async def update_position(self, res_id: UUID, user_id: UUID, page: int, scroll: float) -> None:
        """Update reading position. Contract I2: debounced 5s by caller."""
        self.state_repo.update_position(res_id, user_id, page, scroll)

        from shared.events_resource import ReadingProgressed
        await self._publish(ReadingProgressed(
            resource_id=str(res_id), user_id=str(user_id),
            position_page=page, position_scroll=scroll,
        ))

    async def get_reading_state(self, res_id: UUID, user_id: UUID) -> ReadingState | None:
        return self.state_repo.find_by_resource_and_user(res_id, user_id)

    async def close_resource(self, res_id: UUID, user_id: UUID) -> None:
        """Close a resource. Contract: Open → Closed."""
        res = self.res_repo.find_by_id(res_id)
        if not res:
            return
        res.close()
        self.res_repo.save(res)

        from shared.events_resource import ResourceClosed
        await self._publish(ResourceClosed(
            resource_id=str(res_id), workspace_id=str(res.workspace_id), user_id=str(user_id),
        ))
        logger.info("Resource closed: %s", res_id)

    async def complete_resource(self, res_id: UUID, user_id: UUID) -> None:
        """Mark resource as completed. Contract: Open → Completed."""
        res = self.res_repo.find_by_id(res_id)
        if not res:
            raise ValueError(f"Resource {res_id} not found")
        res.complete()
        self.res_repo.save(res)

        from shared.events_resource import ResourceCompleted
        await self._publish(ResourceCompleted(
            resource_id=str(res_id), workspace_id=str(res.workspace_id), user_id=str(user_id),
        ))
        logger.info("Resource completed: %s", res_id)

    async def create_highlight(self, res_id: UUID, user_id: UUID,
                               text: str, note: str = "",
                               page: int = 0, scroll: float = 0.0) -> Highlight:
        hl = Highlight(
            resource_id=res_id, user_id=user_id,
            text=text, note=note,
            position_page=page, position_scroll=scroll,
        )
        db = __import__('app.infrastructure.db.database', fromlist=['get_db']).get_db()
        db.execute(
            "INSERT INTO reading_annotations (id, user_id, material_id, text, note, color, intent) "
            "VALUES (%s, %s, %s, %s, %s, 'yellow', 'important_concept')",
            (str(hl.id), str(user_id), str(res_id), text, note),
        )

        from shared.events_resource import HighlightCreated
        await self._publish(HighlightCreated(
            highlight_id=str(hl.id), resource_id=str(res_id),
            user_id=str(user_id), text=text[:100],
        ))
        return hl

    async def get_resources(self, ws_id: UUID) -> list[Resource]:
        return self.res_repo.find_by_workspace(ws_id)
