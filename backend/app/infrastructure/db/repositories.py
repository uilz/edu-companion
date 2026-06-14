"""
PostgreSQL 仓储实现 — 实现 shared.protocols 中定义的 Repository 协议
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from shared.protocols import (
    QuestionRepository,
    SessionRepository,
    ErrorBookRepository,
)

logger = logging.getLogger("app.db.repositories")


# ── 内部数据库访问 ──

def _get_db():
    from app.infrastructure.db.database import get_db
    return get_db()


# ═══════════════════════════════════════════════════════════
# Question 仓储
# ═══════════════════════════════════════════════════════════

class PostgresQuestionRepo(QuestionRepository):

    async def save(self, question: dict) -> str:
        qid = question.get("question_id", str(uuid4()))
        question["question_id"] = qid
        _get_db().upsert("questions", question, "question_id")
        return qid

    async def find_by_id(self, question_id: str) -> dict | None:
        row = _get_db().fetchone(
            "SELECT * FROM questions WHERE question_id=%s", (question_id,)
        )
        return dict(row) if row else None

    async def find_by_skill(self, skill_id: str, limit: int = 20) -> list:
        rows = _get_db().fetchall(
            "SELECT * FROM questions WHERE skill_id=%s LIMIT %s",
            (skill_id, limit)
        )
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════
# Session 仓储
# ═══════════════════════════════════════════════════════════

class PostgresSessionRepo(SessionRepository):

    async def create(self, user_id: str, question_ids: list[str]) -> str:
        sid = str(uuid4())
        _get_db().upsert("practice_sessions", {
            "session_id": sid,
            "user_id": user_id,
            "question_ids_json": question_ids,
            "status": "active",
        }, "session_id")
        return sid

    async def find_by_id(self, session_id: str) -> dict | None:
        row = _get_db().fetchone(
            "SELECT * FROM practice_sessions WHERE session_id=%s", (session_id,)
        )
        return dict(row) if row else None

    async def update_status(self, session_id: str, status: str) -> None:
        _get_db().execute(
            "UPDATE practice_sessions SET status=%s WHERE session_id=%s",
            (status, session_id)
        )

    async def list_by_user(self, user_id: str, limit: int = 20) -> list:
        rows = _get_db().fetchall(
            "SELECT * FROM practice_sessions WHERE user_id=%s ORDER BY started_at DESC LIMIT %s",
            (user_id, limit)
        )
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════
# ErrorBook 仓储
# ═══════════════════════════════════════════════════════════

class PostgresErrorBookRepo(ErrorBookRepository):

    async def add(self, entry: dict) -> str:
        eid = entry.get("entry_id", str(uuid4()))
        entry["entry_id"] = eid
        _get_db().upsert("error_book", entry, "entry_id")
        return eid

    async def find_unresolved(self, user_id: str, limit: int = 20) -> list:
        rows = _get_db().fetchall(
            "SELECT * FROM error_book WHERE user_id=%s AND is_resolved=FALSE "
            "ORDER BY created_at DESC LIMIT %s",
            (user_id, limit)
        )
        return [dict(r) for r in rows]

    async def mark_resolved(self, entry_id: str) -> None:
        _get_db().execute(
            "UPDATE error_book SET is_resolved=TRUE WHERE entry_id=%s",
            (entry_id,)
        )
