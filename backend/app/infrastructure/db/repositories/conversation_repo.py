"""Conversation & Turn Repository — raw SQL via Database class."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from app.infrastructure.db.database import get_db
from app.domain.conversation.aggregates import Conversation, ConversationState, Turn, ContextSnapshot

_TABLE = "conv_conversations"


def _row_to_conv(row: dict) -> Conversation:
    return Conversation(
        id=row["id"], session_id=row["session_id"],
        state=ConversationState(row["state"]), title=row.get("title", ""),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _row_to_turn(row: dict) -> Turn:
    return Turn(
        id=row["id"], conversation_id=row["conversation_id"],
        seq=row.get("seq", 1), user_message=row.get("user_message", ""),
        ai_response=row.get("ai_response", ""),
        context_snapshot_id=row.get("context_snapshot_id"),
        orchestration=row.get("orchestration", ""),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
    )


class ConversationRepo:
    def find_by_id(self, conv_id: UUID) -> Conversation | None:
        db = get_db()
        row = db.fetchone(
            f"SELECT id, session_id, state, title, created_at, updated_at FROM {_TABLE} WHERE id = %s",
            (str(conv_id),),
        )
        return _row_to_conv(row) if row else None

    def find_active_by_session(self, session_id: UUID) -> Conversation | None:
        db = get_db()
        row = db.fetchone(
            f"SELECT id, session_id, state, title, created_at, updated_at FROM {_TABLE} WHERE session_id = %s AND state = 'active'",
            (str(session_id),),
        )
        return _row_to_conv(row) if row else None

    def find_by_session(self, session_id: UUID) -> list[Conversation]:
        db = get_db()
        rows = db.fetchall(
            f"SELECT id, session_id, state, title, created_at, updated_at FROM {_TABLE} WHERE session_id = %s ORDER BY created_at",
            (str(session_id),),
        )
        return [_row_to_conv(r) for r in rows]

    def save(self, conv: Conversation) -> None:
        db = get_db()
        db.upsert(_TABLE, {
            "id": str(conv.id), "session_id": str(conv.session_id),
            "state": conv.state.value, "title": conv.title,
            "updated_at": conv.updated_at.isoformat(),
        }, "id")

    def save_turn(self, turn: Turn) -> None:
        db = get_db()
        db.insert("turns", {
            "id": str(turn.id), "conversation_id": str(turn.conversation_id),
            "seq": turn.seq, "user_message": turn.user_message,
            "ai_response": turn.ai_response,
            "context_snapshot_id": str(turn.context_snapshot_id) if turn.context_snapshot_id else None,
            "orchestration": turn.orchestration,
        })

    def find_turns(self, conv_id: UUID) -> list[Turn]:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, conversation_id, seq, user_message, ai_response, "
            "context_snapshot_id, orchestration, created_at FROM turns "
            "WHERE conversation_id = %s ORDER BY seq",
            (str(conv_id),),
        )
        return [_row_to_turn(r) for r in rows]

    def get_next_seq(self, conv_id: UUID) -> int:
        db = get_db()
        row = db.fetchone(
            "SELECT COALESCE(MAX(seq), 0) + 1 as nxt FROM turns WHERE conversation_id = %s",
            (str(conv_id),),
        )
        return row["nxt"] if row else 1

    def save_snapshot(self, snap: ContextSnapshot) -> None:
        db = get_db()
        db.insert("context_snapshots", {
            "id": str(snap.id),
            "conversation_id": str(snap.conversation_id) if snap.conversation_id else None,
            "reading_page": snap.reading_page, "reading_scroll": snap.reading_scroll,
            "memory_tier": snap.memory_tier, "knowledge_concepts": snap.knowledge_concepts,
        })
