"""Planning — 计划项确认请求 (plan_item_confirmations) 领域服务"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.services.planning import _ensure_tables
from app.services.planning._converters import row_to_confirmation
from app.services.planning.items import create_plan_item, find_plan_item_by_request_id, get_plan_item

logger = logging.getLogger(__name__)


def find_confirmation_by_request_id(user_id: str, request_id: str) -> dict | None:
    """按 request_id 查询确认请求（幂等去重用）"""
    if not request_id:
        return None
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        row = db.fetchone(
            "SELECT * FROM plan_item_confirmations WHERE user_id = %s AND request_id = %s LIMIT 1",
            (user_id, request_id),
        )
    except Exception as e:
        logger.debug("按 request_id 查询 confirmation 失败: %s", e)
        return None
    return row_to_confirmation(row) if row else None


def find_confirmation_by_suggestion_id(user_id: str, suggestion_id: str) -> dict | None:
    """按 suggestion_id 查询确认请求（秘书中转幂等去重用）"""
    if not suggestion_id:
        return None
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        row = db.fetchone(
            "SELECT * FROM plan_item_confirmations WHERE user_id = %s AND suggestion_id = %s LIMIT 1",
            (user_id, suggestion_id),
        )
    except Exception as e:
        logger.debug("按 suggestion_id 查询 confirmation 失败: %s", e)
        return None
    return row_to_confirmation(row) if row else None


def count_pending_confirmations(user_id: str) -> int:
    """统计用户当前 pending 确认请求数量（秘书限流用）"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        row = db.fetchone(
            "SELECT COUNT(*) as c FROM plan_item_confirmations WHERE user_id = %s AND status = 'pending'",
            (user_id,),
        )
        return row["c"] if row else 0
    except Exception as e:
        logger.debug("统计 pending confirmation 失败: %s", e)
        return 0


def create_confirmation(user_id: str, body: dict) -> dict:
    """创建待确认计划项请求"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    cid = f"confirm_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    expires_at = body.get("expires_at")
    if expires_at is None:
        expires_at = datetime.now() + timedelta(days=7)
    metadata = body.get("metadata", {})
    db.execute(
        """INSERT INTO plan_item_confirmations
           (id, user_id, request_id, suggestion_id, source_module, target_type, target_ref_id,
            title, description, priority, estimated_minutes, linked_node_ids,
            proposed_scheduled_for, status, expires_at, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', %s, %s::jsonb)""",
        (
            cid, user_id,
            body["request_id"], body.get("suggestion_id"), body.get("source_module", "secretary"),
            body["target_type"], body["target_ref_id"],
            body["title"], body.get("description", ""),
            body.get("priority", 0), body.get("estimated_minutes", 10),
            json.dumps(body.get("linked_node_ids", []), ensure_ascii=False),
            body.get("proposed_scheduled_for"), expires_at,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    return find_confirmation_by_request_id(user_id, body["request_id"])  # type: ignore[return-value]


def list_confirmations(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    """列出计划项确认请求"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    conds = ["user_id=%s"]
    params: list = [user_id]
    if status:
        conds.append("status=%s")
        params.append(status)
    sql = (
        f"SELECT * FROM plan_item_confirmations WHERE {' AND '.join(conds)} "
        f"ORDER BY priority DESC, created_at DESC LIMIT %s"
    )
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    return [row_to_confirmation(r) for r in rows]


def get_confirmation(user_id: str, confirmation_id: str) -> dict | None:
    """获取单个确认请求"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_item_confirmations WHERE id=%s AND user_id=%s",
        (confirmation_id, user_id),
    )
    return row_to_confirmation(row) if row else None


def accept_confirmation(user_id: str, confirmation_id: str) -> dict:
    """接受确认请求并创建正式 plan item"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()

    confirmation = get_confirmation(user_id, confirmation_id)
    if not confirmation:
        raise ValueError("confirmation not found")

    existing = find_plan_item_by_request_id(user_id, confirmation["request_id"])
    if existing:
        if confirmation["status"] == "pending":
            db.execute(
                "UPDATE plan_item_confirmations SET status='accepted', accepted_at=NOW(), updated_at=NOW() WHERE id=%s",
                (confirmation_id,),
            )
        return existing

    if confirmation["status"] != "pending":
        raise ValueError(f"confirmation already {confirmation['status']}")

    item = create_plan_item(
        user_id=user_id,
        body={
            "source_module": confirmation["source_module"],
            "target_type": confirmation["target_type"],
            "target_ref_id": confirmation["target_ref_id"],
            "title": confirmation["title"],
            "description": confirmation["description"],
            "estimated_minutes": confirmation["estimated_minutes"],
            "linked_node_ids": confirmation["linked_node_ids"],
            "priority": confirmation["priority"],
            "scheduled_for": confirmation["proposed_scheduled_for"],
            "metadata": {
                "request_id": confirmation["request_id"],
                "suggestion_id": confirmation["suggestion_id"],
                "requested_by": "secretary",
                "requires_confirmation": True,
            },
        },
    )

    db.execute(
        "UPDATE plan_item_confirmations SET status='accepted', accepted_at=NOW(), updated_at=NOW() WHERE id=%s",
        (confirmation_id,),
    )
    return item


def dismiss_confirmation(user_id: str, confirmation_id: str) -> dict:
    """忽略确认请求"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()

    confirmation = get_confirmation(user_id, confirmation_id)
    if not confirmation:
        raise ValueError("confirmation not found")
    if confirmation["status"] != "pending":
        raise ValueError(f"confirmation already {confirmation['status']}")

    db.execute(
        "UPDATE plan_item_confirmations SET status='dismissed', dismissed_at=NOW(), updated_at=NOW() WHERE id=%s",
        (confirmation_id,),
    )
    return get_confirmation(user_id, confirmation_id)  # type: ignore[return-value]
