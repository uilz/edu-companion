"""
题库解析器 — 对话→题库自动映射 + 建表维护
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional
from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)


def _ensure_tables():
    """确保 v7 题库相关表存在（幂等）"""
    from app.db.database import get_db
    db = get_db()
    possible_paths = [
        "scripts/v7_question_bank.sql",
        "backend/scripts/v7_question_bank.sql",
        os.path.join(os.path.dirname(__file__), "../../scripts/v7_question_bank.sql"),
    ]
    sql_path = None
    for p in possible_paths:
        if os.path.exists(p):
            sql_path = p
            break
    if not sql_path:
        logger.error("找不到建表 SQL 文件")
        return
    with open(sql_path) as f:
        sql = f.read()
    for statement in sql.split(";"):
        s = statement.strip()
        if s:
            try:
                db.execute(s)
            except Exception as e:
                logger.warning("建表异常: %s", e)
    _run_migrations(db)


def _run_migrations(db):
    migrations = [
        "ALTER TABLE v7_question_banks ADD COLUMN IF NOT EXISTS ref_node_id TEXT",
        "ALTER TABLE v7_question_banks ADD COLUMN IF NOT EXISTS ref_node_level VARCHAR(20)",
        "ALTER TABLE v7_question_banks ADD COLUMN IF NOT EXISTS auto_created BOOLEAN DEFAULT false",
        "ALTER TABLE v7_question_banks ADD COLUMN IF NOT EXISTS question_count INT DEFAULT 0",
        "ALTER TABLE v7_questions ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'",
        "ALTER TABLE v7_questions ADD COLUMN IF NOT EXISTS cognitive_node_ids TEXT[] DEFAULT '{}'",
        "ALTER TABLE v7_practice_attempts ADD COLUMN IF NOT EXISTS error_pattern VARCHAR(50)",
    ]
    for sql in migrations:
        try:
            db.execute(sql)
        except Exception:
            pass


def list_banks(user_id=DEFAULT_USER_ID):
    """获取用户所有题库"""
    _ensure_tables()
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT qb.*,
                  (SELECT COUNT(*) FROM v7_questions q WHERE q.bank_id = qb.id AND q.deleted_at IS NULL) as real_count
           FROM v7_question_banks qb
           WHERE qb.user_id = %s AND qb.deleted_at IS NULL
           ORDER BY qb.auto_created ASC, qb.updated_at DESC""",
        (user_id,),
    )
    return [_row_to_bank(r) for r in rows]


def get_bank(bank_id, user_id=DEFAULT_USER_ID):
    _ensure_tables()
    from app.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM v7_question_banks WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
        (bank_id, user_id),
    )
    return _row_to_bank(row) if row else None


def create_bank(user_id, name, description="", ref_node_id=None, ref_node_level=None, auto_created=False):
    _ensure_tables()
    from app.db.database import get_db
    db = get_db()
    now = datetime.now().isoformat()
    bank_id = _generate_bank_id(user_id, ref_node_id or name)
    db.execute(
        """INSERT INTO v7_question_banks
           (id, user_id, name, description, ref_node_id, ref_node_level, auto_created, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, description=EXCLUDED.description, updated_at=EXCLUDED.updated_at""",
        (bank_id, user_id, name, description, ref_node_id, ref_node_level, auto_created, now, now),
    )
    row = db.fetchone("SELECT * FROM v7_question_banks WHERE id = %s", (bank_id,))
    logger.info("题库已创建: %s (%s)", bank_id, name)
    return _row_to_bank(row)


def update_bank(bank_id, user_id, name=None, description=None):
    """更新题库基本信息"""
    from app.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM v7_question_banks WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
        (bank_id, user_id),
    )
    if not row:
        return None
    now = datetime.now().isoformat()
    updates = {}
    if name is not None:
        updates["name"] = name.strip()
    if description is not None:
        updates["description"] = description.strip()
    if not updates:
        return get_bank(bank_id, user_id)
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    updates["updated_at"] = now
    params = list(updates.values()) + [bank_id, user_id]
    db.execute(
        f"UPDATE v7_question_banks SET {set_clause}, updated_at = %s WHERE id = %s AND user_id = %s",
        tuple(params),
    )
    return get_bank(bank_id, user_id)


def delete_bank(bank_id, user_id=DEFAULT_USER_ID):
    _ensure_tables()
    from app.db.database import get_db
    db = get_db()
    now = datetime.now().isoformat()
    db.execute("UPDATE v7_question_banks SET deleted_at = %s WHERE id = %s AND user_id = %s", (now, bank_id, user_id))
    return db.fetchone("SELECT id FROM v7_question_banks WHERE id = %s AND deleted_at IS NULL", (bank_id,)) is None


def resolve_bank_for_conversation(conversation_id, user_id=DEFAULT_USER_ID, user_specified_bank_id=None):
    _ensure_tables()
    if user_specified_bank_id:
        return user_specified_bank_id
    from app.db.database import get_db
    db = get_db()
    conv = db.fetchone("SELECT source_partition_id, source_branch_id FROM conversations WHERE id = %s", (conversation_id,))
    if conv and conv.get("source_branch_id"):
        bank_id = f"bnk_{conv['source_branch_id']}"
        _ensure_bank(db, bank_id, user_id, conv["source_branch_id"])
        return bank_id
    if conv and conv.get("source_partition_id"):
        bank_id = f"bnk_{conv['source_partition_id']}"
        _ensure_bank(db, bank_id, user_id, conv["source_partition_id"])
        return bank_id
    default_id = f"bnk_{user_id}_default"
    _ensure_default_bank(db, default_id, user_id)
    return default_id


def resolve_bank_for_node(node_id, user_id=DEFAULT_USER_ID):
    _ensure_tables()
    from app.db.database import get_db
    from app.cognitive.storage import get_node
    db = get_db()
    node = get_node(node_id, user_id)
    if not node:
        return f"bnk_{user_id}_default"
    if node.level == "topic":
        bank_id = f"bnk_{node_id}"
        _ensure_bank(db, bank_id, user_id, node_id)
        return bank_id
    if node.level in ("concept", "atom") and node.parent:
        parent = get_node(node.parent, user_id)
        if parent:
            bank_id = f"bnk_{parent.id}"
            _ensure_bank(db, bank_id, user_id, parent.id)
            return bank_id
    bank_id = f"bnk_{node_id}"
    _ensure_bank(db, bank_id, user_id, node_id)
    return bank_id


def list_questions(bank_id, user_id=DEFAULT_USER_ID, page=1, page_size=50,
                   question_type=None, status=None, cognitive_node_id=None):
    _ensure_tables()
    from app.db.database import get_db
    db = get_db()
    conditions = ["q.bank_id = %s", "q.deleted_at IS NULL"]
    params = [bank_id]
    if question_type:
        conditions.append("q.question_type = %s"); params.append(question_type)
    if status:
        conditions.append("q.status = %s"); params.append(status)
    if cognitive_node_id:
        conditions.append("%s = ANY(q.cognitive_node_ids)"); params.append(cognitive_node_id)
    where = " AND ".join(conditions)
    offset = (page - 1) * page_size
    total = db.fetchone(f"SELECT COUNT(*) as cnt FROM v7_questions q WHERE {where}", tuple(params))
    total_count = total["cnt"] if total else 0
    rows = db.fetchall(
        f"SELECT q.* FROM v7_questions q WHERE {where} ORDER BY q.created_at DESC LIMIT %s OFFSET %s",
        tuple(params + [page_size, offset]),
    )
    return {
        "items": [_row_to_question(r) for r in rows],
        "total": total_count, "page": page, "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size if page_size > 0 else 0,
    }


def get_question(question_id, user_id=DEFAULT_USER_ID):
    _ensure_tables()
    from app.db.database import get_db
    db = get_db()
    row = db.fetchone("SELECT * FROM v7_questions WHERE id = %s AND deleted_at IS NULL", (question_id,))
    return _row_to_question(row, include_answer=True) if row else None


def _ensure_bank(db, bank_id, user_id, ref_node_id):
    if db.fetchone("SELECT id FROM v7_question_banks WHERE id = %s", (bank_id,)):
        return
    from app.cognitive.storage import get_node
    node = get_node(ref_node_id, user_id)
    label = node.label if node else ref_node_id
    level = node.level if node else ""
    now = datetime.now().isoformat()
    db.execute(
        "INSERT INTO v7_question_banks (id, user_id, name, description, ref_node_id, ref_node_level, "
        "auto_created, import_source, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
        (bank_id, user_id, f"{label}题库", f"自动为{level}「{label}」创建的题库",
         ref_node_id, level, True, "auto", now, now),
    )
    logger.info("自动创建题库: %s (%s)", bank_id, label)


def _ensure_default_bank(db, bank_id, user_id):
    now = datetime.now().isoformat()
    db.execute(
        "INSERT INTO v7_question_banks (id, user_id, name, description, auto_created, import_source, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
        (bank_id, user_id, "通用题库", "未分类题目的默认题库", True, "auto", now, now),
    )


def _generate_bank_id(user_id, hint):
    import re
    suffix = user_id[-8:] if len(user_id) > 8 else user_id
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "_", str(hint))[:20]
    return f"bnk_{suffix}_{slug}"


def _row_to_bank(row):
    return {
        "id": row["id"], "user_id": row["user_id"], "name": row["name"],
        "description": row.get("description", ""),
        "import_source": row.get("import_source", "manual"),
        "ref_node_id": row.get("ref_node_id"),
        "ref_node_level": row.get("ref_node_level"),
        "auto_created": bool(row.get("auto_created", False)),
        "question_count": row.get("real_count") or row.get("question_count", 0),
        "preferences": _safe_json(row.get("preferences"), {}),
        "metadata": _safe_json(row.get("metadata"), {}),
        "created_at": _safe_iso(row.get("created_at")),
        "updated_at": _safe_iso(row.get("updated_at")),
    }


def _row_to_question(row, include_answer=False):
    result = {
        "id": row["id"], "bank_id": row["bank_id"], "question_type": row["question_type"],
        "stem": row["stem"], "options": _safe_json(row.get("options"), []),
        "difficulty": row.get("difficulty", 3),
        "cognitive_node_ids": row.get("cognitive_node_ids") or [],
        "source": row.get("source", "manual"),
        "is_favorite": bool(row.get("is_favorite", False)),
        "is_slashed": bool(row.get("is_slashed", False)),
        "status": row.get("status", "active"),
        "created_at": _safe_iso(row.get("created_at")),
    }
    if include_answer:
        result["answer"] = _safe_json(row.get("answer"), [])
        result["analysis"] = row.get("analysis", "")
    return result


def _safe_json(val, default=None):
    if val is None: return default
    if isinstance(val, (list, dict)): return val
    if isinstance(val, str):
        try: return json.loads(val)
        except Exception: return default
    return default


def _safe_iso(val):
    if val is None: return None
    if hasattr(val, "isoformat"): return val.isoformat()
    return str(val)
