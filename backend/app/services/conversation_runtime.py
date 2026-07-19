"""
ConversationRuntime — AI dialogue lifecycle service.

Per Contract /vision/contracts/conversation.html:
- Manages Conversation lifecycle: created → active ⇄ paused → closed
- Records Turns with context snapshots (I6: replayable)
- Records orchestration decisions (I8: mandatory post-response)
- Publishes events for subscribers
"""

from __future__ import annotations
import logging
from uuid import UUID
from app.domain.conversation.aggregates import Conversation, ConversationState, Turn, ContextSnapshot
from app.infrastructure.db.repositories.conversation_repo import ConversationRepo

logger = logging.getLogger(__name__)


class ConversationRuntime:
    def __init__(self, event_bus=None):
        self.repo = ConversationRepo()
        self._event_bus = event_bus

    async def _publish(self, event) -> None:
        if self._event_bus:
            try:
                await self._event_bus.publish(event)
            except Exception:
                logger.exception("Failed to publish %s", type(event).__name__)

    async def start_conversation(self, session_id: UUID, user_id: UUID,
                                  title: str = "") -> Conversation:
        """Start a new conversation within a session."""
        conv = Conversation(session_id=session_id, title=title)
        conv.activate()
        self.repo.save(conv)

        from shared.events_conversation import ConversationStarted
        await self._publish(ConversationStarted(
            conversation_id=str(conv.id), session_id=str(session_id),
            user_id=str(user_id), title=title,
        ))
        logger.info("Conversation started: %s in session %s", conv.id, session_id)
        return conv

    async def create_turn(self, conv_id: UUID, user_id: UUID,
                          user_message: str, ai_response: str,
                          reading_page: int = 0, reading_scroll: float = 0.0,
                          memory_tier: str = "", knowledge_concepts: str = "",
                          ) -> Turn:
        """Record a turn with context snapshot. Contract I1, I6."""
        conv = self.repo.find_by_id(conv_id)
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found")

        seq = self.repo.get_next_seq(conv_id)

        # Save context snapshot
        snap = ContextSnapshot(
            conversation_id=conv_id,
            reading_page=reading_page, reading_scroll=reading_scroll,
            memory_tier=memory_tier, knowledge_concepts=knowledge_concepts,
        )
        self.repo.save_snapshot(snap)

        # Save turn
        turn = Turn(
            conversation_id=conv_id,
            seq=seq,
            user_message=user_message,
            ai_response=ai_response,
            context_snapshot_id=snap.id,
        )
        self.repo.save_turn(turn)

        from shared.events_conversation import TurnCreated, ResponseComplete
        await self._publish(TurnCreated(
            turn_id=str(turn.id), conversation_id=str(conv_id),
            session_id=str(conv.session_id), user_id=str(user_id),
            seq=seq, user_message=user_message[:200],
        ))
        await self._publish(ResponseComplete(
            turn_id=str(turn.id), conversation_id=str(conv_id),
            session_id=str(conv.session_id), user_id=str(user_id),
            ai_response_length=len(ai_response),
        ))
        return turn

    async def record_orchestration(self, turn_id: UUID, conv_id: UUID,
                                    decision: str, artifact_type: str = "",
                                    artifact_id: str = "") -> None:
        """Record post-response orchestration decision. Contract I8."""
        import json
        orch = json.dumps({"decision": decision, "artifact_type": artifact_type, "artifact_id": artifact_id})

        from app.infrastructure.db.database import get_db
        db = get_db()
        db.execute(
            "UPDATE turns SET orchestration = %s WHERE id = %s",
            (orch, str(turn_id)),
        )

        conv = self.repo.find_by_id(conv_id)
        from shared.events_conversation import OrchestrationDecided
        await self._publish(OrchestrationDecided(
            turn_id=str(turn_id), conversation_id=str(conv_id),
            session_id=str(conv.session_id) if conv else "",
            decision=decision, artifact_type=artifact_type, artifact_id=artifact_id,
        ))

    async def pause_conversation(self, conv_id: UUID, user_id: UUID) -> None:
        conv = self.repo.find_by_id(conv_id)
        if not conv:
            return
        conv.pause()
        self.repo.save(conv)

        from shared.events_conversation import ConversationPaused
        await self._publish(ConversationPaused(
            conversation_id=str(conv_id), session_id=str(conv.session_id),
            user_id=str(user_id),
        ))

    async def close_conversation(self, conv_id: UUID, user_id: UUID) -> None:
        conv = self.repo.find_by_id(conv_id)
        if not conv:
            return
        conv.close()
        self.repo.save(conv)

        from shared.events_conversation import ConversationClosed
        await self._publish(ConversationClosed(
            conversation_id=str(conv_id), session_id=str(conv.session_id),
            user_id=str(user_id),
        ))

    async def get_turns(self, conv_id: UUID) -> list[Turn]:
        """Get all turns for a conversation. Contract I6: replayable."""
        return self.repo.find_turns(conv_id)
