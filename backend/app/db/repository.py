"""
数据仓库层 — 封装 SQLite 操作

将所有练习数据的内存操作替换为数据库读写。
"""

from __future__ import annotations
from shared.constants import DEFAULT_USER_ID
import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.db.database import get_db

logger = logging.getLogger(__name__)


# ── Question Repository ──

class QuestionRepo:
    """题库仓库"""

    @staticmethod
    async def save(question: dict) -> None:
        db = await get_db()
        data = {
            "question_id": question["question_id"],
            "skill_id": question.get("skill_id", ""),
            "subject": question.get("subject", ""),
            "bloom_level": question.get("bloom_level", "understand"),
            "text": question.get("text", ""),
            "options_json": question.get("options", []),
            "correct_answer": question.get("correct_answer", ""),
            "explanation": question.get("explanation", ""),
            "hints_json": question.get("hints", []),
            "difficulty": question.get("difficulty", 0.5),
            "answer_type": question.get("answer_type", "choice"),
            "source": question.get("source", "llm"),
            "tags_json": question.get("tags", []),
            "quality_score": question.get("quality_score", 0.5),
            "status": question.get("status", "active"),
            "created_at": question.get("created_at", datetime.now().isoformat()),
        }
        await db.insert("questions", data)

    @staticmethod
    async def find_by_skill(skill_id: str, limit: int = 50) -> list[dict]:
        db = await get_db()
        rows = await db.fetchall(
            "SELECT * FROM questions WHERE skill_id = ? AND status = 'active' LIMIT ?",
            (skill_id, limit),
        )
        return [_deserialize_question(r) for r in rows]

    @staticmethod
    async def find_by_id(question_id: str) -> Optional[dict]:
        db = await get_db()
        row = await db.fetchone("SELECT * FROM questions WHERE question_id = ?", (question_id,))
        return _deserialize_question(row) if row else None

    @staticmethod
    async def list_all(subject: str = "", skill_id: str = "", bloom_level: str = "", limit: int = 20) -> list[dict]:
        db = await get_db()
        conditions = ["status = 'active'"]
        params: list[Any] = []
        if subject:
            conditions.append("subject = ?")
            params.append(subject)
        if skill_id:
            conditions.append("skill_id = ?")
            params.append(skill_id)
        if bloom_level:
            conditions.append("bloom_level = ?")
            params.append(bloom_level)
        sql = f"SELECT * FROM questions WHERE {' AND '.join(conditions)} LIMIT ?"
        params.append(limit)
        rows = await db.fetchall(sql, tuple(params))
        return [_deserialize_question(r) for r in rows]

    @staticmethod
    async def get_skill_ids() -> list[str]:
        db = await get_db()
        rows = await db.fetchall("SELECT DISTINCT skill_id FROM questions WHERE status = 'active'")
        return [r["skill_id"] for r in rows]


def _deserialize_question(row: dict) -> dict:
    """将数据库行转换回前端期望的格式"""
    return {
        "question_id": row["question_id"],
        "skill_id": row["skill_id"],
        "subject": row["subject"],
        "bloom_level": row["bloom_level"],
        "text": row["text"],
        "options": _json_loads(row.get("options_json", "[]")),
        "correct_answer": row["correct_answer"],
        "explanation": row["explanation"],
        "hints": _json_loads(row.get("hints_json", "[]")),
        "difficulty": row["difficulty"],
        "answer_type": row["answer_type"],
        "source": row["source"],
        "tags": _json_loads(row.get("tags_json", "[]")),
        "quality_score": row["quality_score"],
        "usage_count": row.get("usage_count", 0),
        "avg_correct_rate": row.get("avg_correct_rate", 0.0),
        "status": row["status"],
        "created_at": row["created_at"],
    }


# ── Session Repository ──

class SessionRepo:
    """练习会话仓库"""

    @staticmethod
    async def save(session: dict) -> None:
        db = await get_db()
        data = {
            "session_id": session["session_id"],
            "user_id": session.get("user_id", DEFAULT_USER_ID),
            "planned_skills_json": session.get("planned_skills", []),
            "question_ids_json": session.get("question_ids", []),
            "current_index": session.get("current_index", 0),
            "correct_count": session.get("correct_count", 0),
            "total_hints_used": session.get("total_hints_used", 0),
            "estimated_minutes": session.get("estimated_minutes", 30),
            "mode": session.get("mode", "adaptive"),
            "status": session.get("status", "active"),
            "frustration_level": session.get("frustration_level", 0.0),
            "engagement_level": session.get("engagement_level", 0.5),
            "started_at": session.get("started_at", datetime.now().isoformat()),
            "completed_at": session.get("completed_at"),
        }
        await db.insert("practice_sessions", data)

    @staticmethod
    async def find_by_id(session_id: str) -> Optional[dict]:
        db = await get_db()
        return await db.fetchone("SELECT * FROM practice_sessions WHERE session_id = ?", (session_id,))

    @staticmethod
    async def list_by_user(user_id: str = DEFAULT_USER_ID, since: str = "") -> list[dict]:
        db = await get_db()
        if since:
            rows = await db.fetchall(
                "SELECT * FROM practice_sessions WHERE user_id = ? AND started_at >= ?",
                (user_id, since),
            )
        else:
            rows = await db.fetchall(
                "SELECT * FROM practice_sessions WHERE user_id = ?", (user_id,),
            )
        return [dict(r) for r in rows]

    @staticmethod
    async def update(session_id: str, data: dict) -> None:
        db = await get_db()
        await db.update("practice_sessions", data, "session_id = ?", (session_id,))


# ── Attempt Repository ──

class AttemptRepo:
    """答题记录仓库"""

    @staticmethod
    async def save(attempt: dict) -> None:
        db = await get_db()
        data = {
            "attempt_id": attempt["attempt_id"],
            "user_id": attempt.get("user_id", DEFAULT_USER_ID),
            "question_id": attempt["question_id"],
            "session_id": attempt.get("session_id"),
            "user_answer": attempt.get("user_answer", ""),
            "is_correct": 1 if attempt.get("is_correct") else 0,
            "time_spent_seconds": attempt.get("time_spent_seconds", 0.0),
            "hints_used": attempt.get("hints_used", 0),
            "hint_levels_json": attempt.get("hint_levels", []),
            "explanation_text": attempt.get("explanation_text"),
            "explanation_score": attempt.get("explanation_score"),
            "bloom_level_attempted": attempt.get("bloom_level_attempted", "understand"),
            "knowledge_before_json": attempt.get("knowledge_before", {}),
            "knowledge_after_json": attempt.get("knowledge_after", {}),
            "started_at": attempt.get("started_at", datetime.now().isoformat()),
            "submitted_at": attempt.get("submitted_at", datetime.now().isoformat()),
        }
        # 错误分析
        if attempt.get("error_analysis"):
            ea = attempt["error_analysis"]
            data["error_type"] = ea.get("error_type", {}).get("value") if isinstance(ea.get("error_type"), object) else str(ea.get("error_type", ""))
            data["error_subtype"] = ea.get("error_subtype", "")
            data["misconception"] = ea.get("misconception")
            data["error_severity"] = ea.get("severity", 0.0)
            data["error_suggestion"] = ea.get("suggestion", "")
        await db.insert("attempts", data)

    @staticmethod
    async def list_by_session(session_id: str) -> list[dict]:
        db = await get_db()
        rows = await db.fetchall(
            "SELECT * FROM attempts WHERE session_id = ? ORDER BY submitted_at",
            (session_id,),
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def list_all(user_id: str = DEFAULT_USER_ID, since: str = "") -> list[dict]:
        db = await get_db()
        if since:
            rows = await db.fetchall(
                "SELECT * FROM attempts WHERE user_id = ? AND submitted_at >= ? ORDER BY submitted_at",
                (user_id, since),
            )
        else:
            rows = await db.fetchall(
                "SELECT * FROM attempts WHERE user_id = ? ORDER BY submitted_at",
                (user_id,),
            )
        return [dict(r) for r in rows]


# ── Error Book Repository ──

class ErrorBookRepo:
    """错题本仓库"""

    @staticmethod
    async def save(entry: dict) -> None:
        db = await get_db()
        data = {
            "entry_id": entry["entry_id"],
            "user_id": entry.get("user_id", DEFAULT_USER_ID),
            "question_id": entry["question_id"],
            "skill_id": entry.get("skill_id", ""),
            "error_type": str(entry.get("error_type", "")),
            "misconception": entry.get("misconception"),
            "user_answer": entry.get("user_answer", ""),
            "correct_answer": entry.get("correct_answer", ""),
            "question_text": entry.get("question_text", ""),
            "review_count": entry.get("review_count", 0),
            "next_review": entry.get("next_review", datetime.now().isoformat()),
            "is_resolved": 1 if entry.get("is_resolved") else 0,
            "referenced_materials_json": entry.get("referenced_materials", []),
            "created_at": entry.get("created_at", datetime.now().isoformat()),
        }
        await db.insert("error_book", data)

    @staticmethod
    async def list_by_user(user_id: str = DEFAULT_USER_ID) -> list[dict]:
        db = await get_db()
        rows = await db.fetchall(
            "SELECT * FROM error_book WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def update_entry(entry_id: str, data: dict) -> None:
        db = await get_db()
        await db.update("error_book", data, "entry_id = ?", (entry_id,))


def _json_loads(val: Any) -> Any:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val if val else []
