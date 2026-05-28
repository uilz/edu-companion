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

logger = logging.getLogger("infra.db")


# ═══════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════

class Database:
    """PostgreSQL 连接管理 — 用现有 db/database.py"""

    def __init__(self):
        # 复用已有 Database 实现
        from app.db.database import get_db
        self._db = get_db()

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        return self._db.fetchone(sql, params)

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return self._db.fetchall(sql, params)

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._db.execute(sql, params)

    def upsert(self, table: str, data: dict, pk_col: str) -> None:
        self._db.upsert(table, data, pk_col)


_db = Database()


# ═══════════════════════════════════════════════════════════
# Question 仓储
# ═══════════════════════════════════════════════════════════

class PostgresQuestionRepo(QuestionRepository):

    async def save(self, question: dict) -> str:
        qid = question.get("question_id", str(uuid4()))
        question["question_id"] = qid
        _db.upsert("questions", question, "question_id")
        return qid

    async def find_by_id(self, question_id: str) -> dict | None:
        row = _db.fetchone(
            "SELECT * FROM questions WHERE question_id=%s", (question_id,)
        )
        return dict(row) if row else None

    async def find_by_skill(self, skill_id: str, limit: int = 20) -> list:
        rows = _db.fetchall(
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
        _db.upsert("practice_sessions", {
            "session_id": sid,
            "user_id": user_id,
            "question_ids_json": question_ids,
            "status": "active",
        }, "session_id")
        return sid

    async def find_by_id(self, session_id: str) -> dict | None:
        row = _db.fetchone(
            "SELECT * FROM practice_sessions WHERE session_id=%s", (session_id,)
        )
        return dict(row) if row else None

    async def update_status(self, session_id: str, status: str) -> None:
        _db.execute(
            "UPDATE practice_sessions SET status=%s WHERE session_id=%s",
            (status, session_id)
        )

    async def list_by_user(self, user_id: str, limit: int = 20) -> list:
        rows = _db.fetchall(
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
        _db.upsert("error_book", entry, "entry_id")
        return eid

    async def find_unresolved(self, user_id: str, limit: int = 20) -> list:
        rows = _db.fetchall(
            "SELECT * FROM error_book WHERE user_id=%s AND is_resolved=FALSE "
            "ORDER BY created_at DESC LIMIT %s",
            (user_id, limit)
        )
        return [dict(r) for r in rows]

    async def mark_resolved(self, entry_id: str) -> None:
        _db.execute(
            "UPDATE error_book SET is_resolved=TRUE WHERE entry_id=%s",
            (entry_id,)
        )
