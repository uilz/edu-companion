"""
SessionRepository — 练习会话持久化层 v2

职责:
1. 会话记录的 CRUD (practice_sessions 表) → 返回 PracticeSession Pydantic
2. 会话题目关联操作 (session_questions 表, 无状态)
3. 答题记录操作 (practice_attempts 表)
4. 统计数据 — 从 practice_attempts 聚合 (非 session_questions)

纯数据访问层，不含业务编排。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from app.schemas.practice import PracticeSession, SessionQuestion

logger = logging.getLogger(__name__)


# ── 会话 CRUD ──


def _safe_iso(val):
    """将 datetime 或时间值转为 ISO 字符串（防止 Pydantic str 字段收到 datetime 对象报错）"""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _row_to_session(row: dict) -> PracticeSession:
    """将 DB 行转为 PracticeSession Pydantic 对象"""
    if not row:
        return None
    return PracticeSession(
        id=row.get("id", ""),
        user_id=row.get("user_id", ""),
        bank_id=row.get("bank_id"),
        session_type=row.get("session_type", "practice"),
        mode=row.get("mode", "adaptive"),
        config=json.loads(row.get("config")) if row.get("config") and isinstance(row.get("config"), str) else (row.get("config") or {}),
        status=row.get("status", "created"),
        total_count=row.get("total_count") or 0,
        correct_count=row.get("correct_count") or 0,
        wrong_count=row.get("wrong_count") or 0,
        score=row.get("score"),
        cognitive_node_ids=row.get("cognitive_node_ids") or [],
        conversation_id=row.get("conversation_id"),
        started_at=_safe_iso(row.get("started_at")),
        finished_at=_safe_iso(row.get("finished_at")),
        duration_seconds=row.get("duration_seconds"),
        created_at=_safe_iso(row.get("created_at", "")),
    )


def insert_session(
    db,
    session_id: str,
    bank_id: str,
    user_id: str,
    node_ids: list[str],
    session_type: str,
    mode: str,
    total_count: int,
    config: dict,
    now: str,
) -> None:
    """插入会话记录"""
    db.execute(
        """INSERT INTO practice_sessions
           (id, user_id, bank_id, session_type, mode, total_count, cognitive_node_ids,
            correct_count, wrong_count, score, status, config, started_at, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, 0, 'created', %s, %s, %s)""",
        (session_id, user_id, bank_id, session_type, mode, total_count,
         node_ids, json.dumps(config), now, now),
    )


def insert_session_questions(db, session_id: str, questions: list[dict], now: str) -> None:
    """批量插入会话题目关联 (无状态, D9)"""
    for i, q in enumerate(questions):
        db.execute(
            """INSERT INTO session_questions
               (id, session_id, question_id, sort_order, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (f"sq_{session_id}_{q['id']}", session_id, q["id"],
             q.get("sort_order", i),
             now),
        )


def get_session(db, session_id: str, user_id: str) -> Optional[PracticeSession]:
    """获取单个会话记录 → PracticeSession 对象"""
    row = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    return _row_to_session(row) if row else None


def update_session_status(db, session_id: str, status: str, extra: dict = None) -> None:
    """更新会话状态"""
    from datetime import datetime
    now = datetime.now().isoformat()
    fields = {"status": status}
    if extra:
        fields.update(extra)
    if status == "completed":
        fields["finished_at"] = now

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
    session_type: str = None,
    mode: str = None,
    date_from: str = None,
    date_to: str = None,
    score_min: float = None,
    score_max: float = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PracticeSession], int]:
    """列出用户会话 → (list[PracticeSession], total_count)"""
    conditions = ["ps.user_id = %s"]
    params = [user_id]

    if bank_id:
        conditions.append("ps.bank_id = %s")
        params.append(bank_id)
    if status:
        conditions.append("ps.status = %s")
        params.append(status)
    if session_type:
        conditions.append("ps.session_type = %s")
        params.append(session_type)
    if mode:
        conditions.append("ps.mode = %s")
        params.append(mode)
    if date_from:
        conditions.append("ps.created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("ps.created_at <= %s")
        params.append(date_to)

    # 分数过滤：JOIN practice_attempts，按会话分组取正确率
    having_clause = ""
    having_params = []
    if score_min is not None or score_max is not None:
        having_parts = []
        if score_min is not None:
            having_parts.append("COUNT(CASE WHEN pa.is_correct THEN 1 END)::float / NULLIF(COUNT(*), 0) >= %s")
            having_params.append(score_min)
        if score_max is not None:
            having_parts.append("COUNT(CASE WHEN pa.is_correct THEN 1 END)::float / NULLIF(COUNT(*), 0) <= %s")
            having_params.append(score_max)
        if having_parts:
            having_clause = " HAVING " + " AND ".join(having_parts)

    where = " AND ".join(conditions)

    # 计数（不涉及分数过滤时用简单计数）
    if having_clause:
        total = 0
    else:
        count_row = db.fetchone(
            f"SELECT COUNT(*) as cnt FROM practice_sessions ps WHERE {where}",
            tuple(params),
        )
        total = count_row["cnt"] if count_row else 0
        # 如果分数过滤，则从查询结果计数
        total = total

    rows = db.fetchall(
        f"""SELECT ps.*
            FROM practice_sessions ps
            WHERE {where}
            ORDER BY ps.created_at DESC LIMIT %s OFFSET %s""",
        tuple(params + [limit, offset]),
    )
    return [_row_to_session(r) for r in rows], total


# ── 会话题目操作 ──


def get_session_question(db, session_id: str, question_id: str) -> Optional[dict]:
    """获取会话题目关联 (仅排序元数据, D9)"""
    return db.fetchone(
        "SELECT * FROM session_questions WHERE session_id = %s AND question_id = %s",
        (session_id, question_id),
    )


def get_session_questions(db, session_id: str) -> list[dict]:
    """获取会话所有题目 (按排序)"""
    return db.fetchall(
        "SELECT * FROM session_questions WHERE session_id = %s ORDER BY sort_order ASC",
        (session_id,),
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
    error_pattern: str = "",
    error_analysis: dict = None,
    now: str = "",
) -> str:
    """插入答题记录 (D9: 唯一记录源, session_questions 不再存状态)"""
    from datetime import datetime
    if not now:
        now = datetime.now().isoformat()
    attempt_id = f"att_{session_id}_{question_id}_{int(datetime.now().timestamp())}"
    db.execute(
        """INSERT INTO practice_attempts
           (id, session_id, question_id, user_id, is_correct, user_answer,
            time_spent_seconds, is_wrong, wrong_count, consecutive_correct,
            error_pattern, error_analysis, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (attempt_id, session_id, question_id, user_id, is_correct,
         json.dumps(user_answer), time_spent,
         not is_correct, 1 if not is_correct else 0, 0 if not is_correct else 1,
         error_pattern, json.dumps(error_analysis or {}), now),
    )
    return attempt_id


# ── 会话统计 ──


def update_session_stats(db, session_id: str) -> dict:
    """从 practice_attempts 重新计算会话统计 (D9)"""
    stats = db.fetchone(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct
           FROM practice_attempts WHERE session_id = %s""",
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