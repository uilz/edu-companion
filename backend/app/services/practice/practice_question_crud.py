"""
题目管理 CRUD
"""
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def add_question(bank_id, user_id, question_type, stem, answer,
                 options=None, analysis="", difficulty=3,
                 cognitive_node_ids=None, source="manual", metadata=None):
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_question_bank import _ensure_tables
    _ensure_tables()
    db = get_db()
    now = datetime.now().isoformat()
    count = db.fetchone("SELECT COUNT(*) as cnt FROM questions WHERE bank_id = %s", (bank_id,))
    seq = (count["cnt"] if count else 0) + 1
    qid = f"q_{bank_id}_{seq}"
    db.execute(
        "INSERT INTO questions (id, bank_id, user_id, question_type, stem, options, answer, explanation, "
        "difficulty, cognitive_node_ids, source, metadata, status, created_at, updated_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (qid, bank_id, user_id, question_type, stem,
         json.dumps(options or []), json.dumps(answer), analysis, difficulty,
         cognitive_node_ids or [], source, json.dumps(metadata or {}), "active", now, now),
    )
    db.execute("UPDATE question_banks SET question_count = question_count + 1, updated_at = %s WHERE id = %s", (now, bank_id))
    row = db.fetchone("SELECT * FROM questions WHERE id = %s", (qid,))
    return _row_to_question(row)


def update_question(question_id, user_id, **kwargs):
    from app.infrastructure.db.database import get_db
    db = get_db()
    # 前端/历史 API 使用 analysis，数据库存 explanation，统一映射
    if "analysis" in kwargs:
        kwargs["explanation"] = kwargs.pop("analysis")
    allowed = {"stem", "options", "answer", "explanation", "difficulty",
               "question_type", "cognitive_node_ids", "status", "metadata"}
    updates, params = [], []
    for k, v in kwargs.items():
        if k in allowed:
            if k in ("options", "answer", "metadata"):
                v = json.dumps(v) if isinstance(v, (list, dict)) else v
            updates.append(f"{k} = %s"); params.append(v)
    if not updates:
        return None
    now = datetime.now().isoformat()
    updates.append("updated_at = %s"); params.append(now); params.append(question_id)
    db.execute(f"UPDATE questions SET {', '.join(updates)} WHERE id = %s", tuple(params))
    row = db.fetchone("SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL", (question_id,))
    return _row_to_question(row) if row else None


def delete_question(question_id, user_id):
    from app.infrastructure.db.database import get_db
    db = get_db()
    now = datetime.now().isoformat()
    row = db.fetchone("SELECT bank_id FROM questions WHERE id = %s AND deleted_at IS NULL", (question_id,))
    if not row:
        return False
    db.execute("UPDATE questions SET deleted_at = %s WHERE id = %s", (now, question_id))
    db.execute("UPDATE question_banks SET question_count = GREATEST(0, question_count - 1), updated_at = %s WHERE id = %s",
               (now, row["bank_id"]))
    return True


def toggle_favorite(question_id, user_id):
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = db.fetchone(
        "SELECT id FROM question_user_flags WHERE question_id = %s AND user_id = %s AND flag_type = 'favorite'",
        (question_id, user_id))
    if existing:
        db.execute("DELETE FROM question_user_flags WHERE id = %s", (existing["id"],))
        db.execute("UPDATE questions SET is_favorite = false WHERE id = %s", (question_id,))
        return False
    db.execute(
        "INSERT INTO question_user_flags (id, user_id, question_id, flag_type) VALUES (%s, %s, %s, 'favorite')",
        (f"fav_{question_id}_{user_id[-6:]}", user_id, question_id))
    db.execute("UPDATE questions SET is_favorite = true WHERE id = %s", (question_id,))
    return True


def toggle_slash(question_id, user_id):
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = db.fetchone(
        "SELECT id FROM question_user_flags WHERE question_id = %s AND user_id = %s AND flag_type = 'slashed'",
        (question_id, user_id))
    if existing:
        db.execute("DELETE FROM question_user_flags WHERE id = %s", (existing["id"],))
        db.execute("UPDATE questions SET is_slashed = false WHERE id = %s", (question_id,))
        return False
    db.execute(
        "INSERT INTO question_user_flags (id, user_id, question_id, flag_type) VALUES (%s, %s, %s, 'slashed')",
        (f"sl_{question_id}_{user_id[-6:]}", user_id, question_id))
    db.execute("UPDATE questions SET is_slashed = true WHERE id = %s", (question_id,))
    return True


def batch_import_questions(bank_id, user_id, questions):
    saved = []
    for q in questions:
        # add_question 接受 analysis (不是 explanation)
        saved.append(add_question(
            bank_id=bank_id, user_id=user_id,
            question_type=q.get("question_type", "single"),
            stem=q.get("stem", ""), answer=q.get("answer", []),
            options=q.get("options"),
            analysis=q.get("analysis", "") or q.get("explanation", ""),
            difficulty=q.get("difficulty", 3),
            cognitive_node_ids=q.get("cognitive_node_ids"),
            source=q.get("source", "import"),
        ))
    return saved


def copy_questions_to_bank(target_bank_id, user_id, question_ids=None, source_bank_id=None):
    """复制题目到目标题库。支持指定题目ID列表或复制整个源题库。"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    target_questions = []
    if question_ids:
        for qid in question_ids:
            row = db.fetchone(
                "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
                (qid,),
            )
            if row:
                target_questions.append(row)
    elif source_bank_id:
        rows = db.fetchall(
            "SELECT * FROM questions WHERE bank_id = %s AND deleted_at IS NULL ORDER BY created_at ASC",
            (source_bank_id,),
        )
        target_questions = rows or []

    saved = []
    for q in target_questions:
        saved.append(add_question(
            bank_id=target_bank_id, user_id=user_id,
            question_type=q.get("question_type", "single"),
            stem=q.get("stem", ""),
            answer=q.get("answer", []),
            options=q.get("options"),
            analysis=q.get("explanation", "") or q.get("analysis", ""),
            difficulty=q.get("difficulty", 3),
            cognitive_node_ids=q.get("cognitive_node_ids"),
            source="copied",
            metadata={"copied_from": q["id"], "original_bank_id": q["bank_id"]},
        ))
    return saved


def reorder_questions_in_bank(bank_id, question_ids, user_id):
    """按 question_ids 顺序调整题库中的题目顺序（更新 updated_at 时间戳排序）"""
    from app.infrastructure.db.database import get_db
    from datetime import datetime
    db = get_db()
    now = datetime.now()
    for i, qid in enumerate(question_ids):
        ts = now.timestamp() + i
        dt = datetime.fromtimestamp(ts)
        db.execute(
            "UPDATE questions SET updated_at = %s WHERE id = %s AND bank_id = %s AND deleted_at IS NULL",
            (dt.isoformat(), qid, bank_id),
        )
    return True


def _row_to_question(row):
    from app.services.practice.practice_question_bank import _safe_json, _safe_iso
    return {
        "id": row["id"], "bank_id": row["bank_id"], "question_type": row["question_type"],
        "stem": row["stem"], "options": _safe_json(row.get("options"), []),
        "answer": _safe_json(row.get("answer"), []), "explanation": row.get("explanation", "") or row.get("analysis", ""),
        "difficulty": row.get("difficulty", 3),
        "cognitive_node_ids": row.get("cognitive_node_ids") or [],
        "source": row.get("source", "manual"),
        "is_favorite": bool(row.get("is_favorite", False)),
        "is_slashed": bool(row.get("is_slashed", False)),
        "status": row.get("status", "active"),
        "metadata": _safe_json(row.get("metadata"), {}),
        "created_at": _safe_iso(row.get("created_at")),
        "updated_at": _safe_iso(row.get("updated_at")),
    }
