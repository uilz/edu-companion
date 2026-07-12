"""Planning — 计划项 (plan_items) 领域服务"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

from app.infrastructure.event_bus_utils import publish_event_safe
from app.services.planning import _ensure_tables
from app.services.planning._converters import row_to_plan_item
from shared.events import (
    PlanningSourceModule,
    PlanItemCompleted,
    PlanItemCreated,
    PlanItemExtended,
    PlanItemScheduled,
    PlanItemSkipped,
    PlanItemStarted,
)

logger = logging.getLogger(__name__)


def list_plan_items(
    user_id: str,
    plan_date: Optional[date] = None,
    status: Optional[str] = None,
    source_module: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    conds = ["user_id=%s"]
    params: list = [user_id]
    if plan_date is not None:
        conds.append("plan_date=%s")
        params.append(plan_date)
    if status:
        conds.append("status=%s")
        params.append(status)
    if source_module:
        conds.append("source_module=%s")
        params.append(source_module)
    sql = (
        f"SELECT * FROM plan_items WHERE {' AND '.join(conds)} "
        f"ORDER BY COALESCE(scheduled_for, '9999-12-31'::timestamptz), priority DESC, created_at DESC "
        f"LIMIT %s"
    )
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    return [row_to_plan_item(r) for r in rows]


def list_plan_items_by_node_ids(
    user_id: str,
    cognitive_node_ids: list[str],
    limit: int = 20,
) -> list[dict]:
    """按 linked_node_ids 重叠查询计划项。"""
    if not cognitive_node_ids:
        return []
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT * FROM plan_items
           WHERE user_id = %s AND linked_node_ids && %s::jsonb
           ORDER BY COALESCE(scheduled_for, '9999-12-31'::timestamptz), priority DESC, created_at DESC
           LIMIT %s""",
        (user_id, cognitive_node_ids, limit),
    )
    return [row_to_plan_item(r) for r in rows]


def get_plan_item(user_id: str, plan_item_id: str) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_items WHERE id=%s AND user_id=%s",
        (plan_item_id, user_id),
    )
    return row_to_plan_item(row) if row else None


def create_plan_item(user_id: str, body: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    pid = f"plan_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    plan_date = body.get("plan_date")
    if plan_date is None and body.get("scheduled_for"):
        plan_date = body["scheduled_for"].date() if isinstance(body["scheduled_for"], datetime) else None
    if isinstance(plan_date, str):
        try:
            plan_date = date.fromisoformat(plan_date)
        except ValueError:
            plan_date = None
    metadata = body.get("metadata", {})
    db.execute(
        """INSERT INTO plan_items
           (id, user_id, source_module, target_type, target_ref_id, title, description,
            estimated_minutes, linked_node_ids, priority, status, scheduled_for, plan_date, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', %s, %s, %s::jsonb)""",
        (
            pid, user_id,
            body["source_module"], body["target_type"], body["target_ref_id"],
            body["title"], body.get("description", ""),
            body.get("estimated_minutes", 0),
            json.dumps(body.get("linked_node_ids", []), ensure_ascii=False),
            body.get("priority", 0),
            body.get("scheduled_for"),
            plan_date,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    publish_event_safe(PlanItemCreated(
        user_id=user_id,
        plan_item_id=pid,
        source_module=body["source_module"],
        target_type=body["target_type"],
        target_ref_id=body["target_ref_id"],
        title=body["title"],
    ))

    return get_plan_item(user_id, pid)  # type: ignore[return-value]


def find_plan_item_by_request_id(user_id: str, request_id: str) -> dict | None:
    """按秘书请求 ID 查询已创建的计划项（幂等去重用）"""
    if not request_id:
        return None
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        row = db.fetchone(
            "SELECT * FROM plan_items WHERE user_id = %s AND metadata->>'request_id' = %s LIMIT 1",
            (user_id, request_id),
        )
    except Exception as e:
        logger.debug("按 request_id 查询 plan_item 失败: %s", e)
        return None
    return row_to_plan_item(row) if row else None


def update_plan_item(user_id: str, plan_item_id: str, body: dict) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    sets: list[str] = []
    params: list = []
    for k in ("title", "description", "estimated_minutes", "priority", "status",
              "scheduled_for", "plan_date", "started_at", "skipped_at", "completed_at"):
        v = body.get(k)
        if v is None:
            continue
        sets.append(f"{k}=%s")
        params.append(v)
    if not sets:
        return get_plan_item(user_id, plan_item_id)
    sets.append("updated_at=NOW()")
    params.extend([plan_item_id, user_id])
    db.execute(
        f"UPDATE plan_items SET {', '.join(sets)} WHERE id=%s AND user_id=%s",
        tuple(params),
    )
    item = get_plan_item(user_id, plan_item_id)

    # 如果显式安排了 scheduled_for，发布 PlanItemScheduled 事件
    if item and body.get("scheduled_for") is not None:
        try:
            publish_event_safe(PlanItemScheduled(
                user_id=user_id,
                plan_item_id=plan_item_id,
                source_module=item["source_module"],
                scheduled_for=body["scheduled_for"],
                plan_date=str(body.get("plan_date") or date.today()),
                is_mood_rule_affected=item.get("is_mood_rule_affected", False),
            ))
        except Exception as e:
            logger.debug("PlanItemScheduled 事件发布失败: %s", e)
    return item


def start_plan_item(user_id: str, plan_item_id: str) -> Optional[dict]:
    """标记开始：status=in_progress, started_at=NOW()"""
    _ensure_tables()
    item = update_plan_item(user_id, plan_item_id, {
        "status": "in_progress",
        "started_at": datetime.now(),
    })
    if item:
        try:
            publish_event_safe(PlanItemStarted(
                user_id=user_id,
                plan_item_id=plan_item_id,
                source_module=item["source_module"],
                started_at=datetime.now(),
            ))
        except Exception as e:
            logger.debug("PlanItemStarted 事件发布失败: %s", e)
    return item


def skip_plan_item(user_id: str, plan_item_id: str) -> Optional[dict]:
    """标记跳过：status=skipped, skipped_at=NOW()"""
    _ensure_tables()
    item = update_plan_item(user_id, plan_item_id, {
        "status": "skipped",
        "skipped_at": datetime.now(),
    })
    if item:
        try:
            publish_event_safe(PlanItemSkipped(
                user_id=user_id,
                plan_item_id=plan_item_id,
                source_module=item["source_module"],
                skipped_at=datetime.now(),
            ))
        except Exception as e:
            logger.debug("PlanItemSkipped 事件发布失败: %s", e)
    return item


def extend_plan_item(user_id: str, plan_item_id: str, extra_minutes: int) -> Optional[dict]:
    """延长：estimated_minutes += extra, status=extended"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    db.execute(
        """UPDATE plan_items
           SET estimated_minutes = COALESCE(estimated_minutes, 0) + %s,
               status = 'extended',
               updated_at = NOW()
           WHERE id = %s AND user_id = %s""",
        (extra_minutes, plan_item_id, user_id),
    )
    item = get_plan_item(user_id, plan_item_id)
    if item:
        try:
            publish_event_safe(PlanItemExtended(
                user_id=user_id,
                plan_item_id=plan_item_id,
                source_module=item["source_module"],
                extended_minutes=extra_minutes,
            ))
        except Exception as e:
            logger.debug("PlanItemExtended 事件发布失败: %s", e)
    return item


def complete_plan_item(user_id: str, plan_item_id: str, body: dict) -> dict:
    """标记完成：写入 plan_items + 写偏差 + 发布 PlanItemCompleted"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_items WHERE id=%s AND user_id=%s",
        (plan_item_id, user_id),
    )
    if not row:
        raise ValueError("plan_item not found")

    actual_minutes = int(body.get("actual_minutes") or 0)
    now = datetime.now()
    planned_minutes = row.get("estimated_minutes") or 0

    db.execute(
        """UPDATE plan_items SET status='completed', completed_at=%s,
           actual_minutes=%s, updated_at=NOW() WHERE id=%s""",
        (now, actual_minutes, plan_item_id),
    )

    deviation_minutes = (actual_minutes or 0) - (planned_minutes or 0)
    dev_type = "timeout" if deviation_minutes > 0 else "early_complete" if deviation_minutes < 0 else "timeout"
    try:
        db.execute(
            """INSERT INTO plan_deviations
               (id, plan_item_id, user_id, deviation_type, planned_minutes, actual_minutes, deviation_minutes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (f"dev_{plan_item_id}_{int(now.timestamp())}", plan_item_id, user_id,
             dev_type, planned_minutes, actual_minutes, deviation_minutes),
        )
    except Exception as e:
        logger.debug("plan_deviations 写入失败: %s", e)

    linked = row.get("linked_node_ids") or []
    if isinstance(linked, str):
        try:
            linked = json.loads(linked)
        except (json.JSONDecodeError, TypeError):
            linked = []
    publish_event_safe(PlanItemCompleted(
        user_id=user_id,
        plan_item_id=plan_item_id,
        source_module=row.get("source_module", PlanningSourceModule.MANUAL.value),
        target_type=row.get("target_type", ""),
        target_ref_id=row.get("target_ref_id", ""),
        actual_minutes=actual_minutes,
        linked_node_ids=linked or [],
        completed_at=now,
    ))

    return get_plan_item(user_id, plan_item_id)  # type: ignore[return-value]


def delete_plan_item(user_id: str, plan_item_id: str) -> bool:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone("SELECT id FROM plan_items WHERE id=%s AND user_id=%s", (plan_item_id, user_id))
    if not row:
        return False
    db.execute("DELETE FROM plan_items WHERE id=%s", (plan_item_id,))
    return True
