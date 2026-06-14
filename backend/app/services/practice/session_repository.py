"""
SessionRepository — 练习会话持久化层

职责:
1. 会话记录的 CRUD (practice_sessions 表)
2. 会话题目关联操作 (session_questions 表)
3. 答题记录操作 (practice_attempts 表)
4. 统计数据读写

纯数据访问层，不含业务编排。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── 会话 CRUD ──


def insert_session(
    db,
    session_id: str,
    bank_id: str,
    user_id: str,
    node_ids: list[str],
    session_type: str,
    mode: str,
    question_count: int,
    config: dict,
    now: str,
) -> None:
    """插入会话记录"""
    db.execute(
        """INSERT INTO practice_sessions
           (id, user_id, bank_id, session_type, mode, question_count, node_ids,
            correct_count, wrong_count, score, status, config, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, 0, 'created', %s, %s, %s)""",
        (session_id, user_id, bank_id, session_type, mode, question_count,
         json.dumps(node_ids), json.dumps(config), now, now),
    )


def insert_session_questions(db, session_id: str, questions: list[dict], now: str) -> None:
    """批量插入会话题目关联"""
    for q in questions:
        db.execute(
            """INSERT INTO session_questions
               (session_id, question_id, question_type, bloom_level, difficulty,
                is_correct, user_answer, time_spent, hints_used, created_at)
               VALUES (%s, %s, %s, %s, %s, NULL, NULL, 0, 0, %s)""",
            (session_id, q["id"], q.get("question_type", "single"),
             q.get("bloom_level", "remember"), q.get("difficulty", 3), now),
        )


def get_session(db, session_id: str, user_id: str) -> Optional[dict]:
    """获取单个会话记录"""
    return db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )


def update_session_status(db, session_id: str, status: str, extra: dict = None) -> None:
    """更新会话状态"""
    from datetime import datetime
    now = datetime.now().isoformat()
    fields = {"status": status, "updated_at": now}
    if extra:
        fields.update(extra)

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [session_id]
    db.execute(
        f"UPDATE practice_sessions SET {set_clause} WHERE id = %s",
        tuple(values),
    )


def delete_session(db, session_id: str, user_id: str) -> bool:
    """硬删除会话及关联数据"""
    session = db.fetchone(
        "SELECT id FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return False
    db.execute("DELETE FROM practice_attempts WHERE session_id = %s", (session_id,))
    db.execute("DELETE FROM session_questions WHERE session_id = %s", (session_id,))
    db.execute("DELETE FROM practice_sessions WHERE id = %s", (session_id,))
    return True


def list_sessions(
    db,
    user_id: str,
    bank_id: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """列出用户会话"""
    conditions = ["ps.user_id = %s"]
    params = [user_id]

    if bank_id:
        conditions.append("ps.bank_id = %s")
        params.append(bank_id)
    if status:
        conditions.append("ps.status = %s")
        params.append(status)

    where = " AND ".join(conditions)
    return db.fetchall(
        f"""SELECT ps.*, qb.name as bank_name
            FROM practice_sessions ps
            LEFT JOIN question_banks qb ON qb.id = ps.bank_id
            WHERE {where}
            ORDER BY ps.created_at DESC LIMIT %s OFFSET %s""",
        tuple(params + [limit, offset]),
    )


# ── 会话题目操作 ──


def get_session_question(db, session_id: str, question_id: str) -> Optional[dict]:
    """获取会话题目关联"""
    return db.fetchone(
        "SELECT * FROM session_questions WHERE session_id = %s AND question_id = %s",
        (session_id, question_id),
    )


def update_session_question(
    db,
    session_id: str,
    question_id: str,
    is_correct: bool,
    user_answer: list,
    time_spent: int,
    hints_used: int,
    error_type: str = "",
    now: str = "",
) -> None:
    """更新会话题目记录（含答题结果）"""
    from datetime import datetime
    if not now:
        now = datetime.now().isoformat()
    db.execute(
        """UPDATE session_questions SET
           is_correct = %s, user_answer = %s, time_spent = %s,
           hints_used = %s, error_type = %s, answered_at = %s
           WHERE session_id = %s AND question_id = %s""",
        (is_correct, json.dumps(user_answer), time_spent, hints_used,
         error_type, now, session_id, question_id),
    )


# ── 答题记录 ──


def insert_attempt(
    db,
    session_id: str,
    question_id: str,
    user_id: str,
    is_correct: bool,
    user_answer: list,
    time_spent: int,
    hints_used: int,
    error_type: str = "",
    error_detail: str = "",
    analysis: str = "",
    now: str = "",
) -> str:
    """插入答题记录"""
    from datetime import datetime
    if not now:
        now = datetime.now().isoformat()
    attempt_id = f"att_{session_id}_{question_id}_{int(datetime.now().timestamp())}"
    db.execute(
        """INSERT INTO practice_attempts
           (id, session_id, question_id, user_id, is_correct, user_answer,
            time_spent, hints_used, error_type, error_detail, analysis, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (attempt_id, session_id, question_id, user_id, is_correct,
         json.dumps(user_answer), time_spent, hints_used, error_type,
         error_detail, analysis, now),
    )
    return attempt_id


# ── 会话统计 ──


def update_session_stats(db, session_id: str) -> dict:
    """从 session_questions 重新计算会话统计"""
    stats = db.fetchone(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct
           FROM session_questions WHERE session_id = %s""",
        (session_id,),
    )
    if not stats:
        return {"total": 0, "correct": 0, "wrong": 0, "score": 0.0}

    total = stats["total"] or 0
    correct = stats["correct"] or 0
    wrong = total - correct
    score = round((correct / max(total, 1)) * 100, 1)

    db.execute(
        "UPDATE practice_sessions SET correct_count = %s, wrong_count = %s, score = %s WHERE id = %s",
        (correct, wrong, score, session_id),
    )
    return {"total": total, "correct": correct, "wrong": wrong, "score": score}
