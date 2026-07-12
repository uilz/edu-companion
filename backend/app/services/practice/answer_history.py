"""答题历史服务

聚合 practice_attempts 与 questions，返回用户答题历史。
"""
from __future__ import annotations

import json as _json
from typing import Optional


def get_answer_history(
    user_id: str,
    question_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """获取用户答题历史，支持按题目/会话过滤。"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    conditions = ["a.user_id = %s"]
    params: list = [user_id]

    if question_id:
        conditions.append("a.question_id = %s")
        params.append(question_id)
    if session_id:
        conditions.append("a.session_id = %s")
        params.append(session_id)

    where = " AND ".join(conditions)

    total = db.fetchone(
        f"SELECT COUNT(*) as cnt FROM practice_attempts a WHERE {where}",
        tuple(params),
    )
    total_count = total["cnt"] if total else 0

    rows = db.fetchall(
        f"""SELECT a.id, a.session_id, a.question_id, a.user_answer,
                   a.is_correct, a.time_spent_seconds, a.is_wrong,
                   a.wrong_count, a.consecutive_correct, a.cognitive_node_ids,
                   a.created_at,
                   q.stem, q.options, q.question_type, q.difficulty, q.answer
            FROM practice_attempts a
            LEFT JOIN questions q ON a.question_id = q.id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT %s OFFSET %s""",
        tuple(params + [min(limit, 200), max(offset, 0)]),
    )

    items = []
    for r in rows:
        items.append({
            "attempt_id": r["id"],
            "session_id": r["session_id"],
            "question_id": r["question_id"],
            "user_answer": _json.loads(r["user_answer"]) if isinstance(r["user_answer"], str) else r["user_answer"],
            "is_correct": r["is_correct"],
            "time_spent_seconds": r.get("time_spent_seconds", 0),
            "is_wrong": r.get("is_wrong", False),
            "wrong_count": r.get("wrong_count", 0),
            "consecutive_correct": r.get("consecutive_correct", 0),
            "cognitive_node_ids": r.get("cognitive_node_ids") or [],
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            "question_stem": (r.get("stem") or "")[:120],
            "question_type": r.get("question_type", ""),
            "difficulty": r.get("difficulty", 3),
            "correct_answer": _json.loads(r["answer"]) if isinstance(r.get("answer"), str) else (r.get("answer") or []),
        })

    return {
        "items": items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }
