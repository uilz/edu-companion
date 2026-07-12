"""Planning — 目标 (plan_goals) 领域服务"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.infrastructure.event_bus_utils import publish_event_safe
from app.services.planning import _ensure_tables
from app.services.planning._converters import row_to_goal
from shared.events import PlanGoalCreated

logger = logging.getLogger(__name__)


def list_goals(user_id: str, status: Optional[str] = None) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    conds = ["user_id=%s"]
    params: list = [user_id]
    if status:
        conds.append("status=%s")
        params.append(status)
    rows = db.fetchall(
        f"SELECT * FROM plan_goals WHERE {' AND '.join(conds)} ORDER BY deadline ASC NULLS LAST",
        tuple(params),
    )
    return [row_to_goal(r) for r in rows]


def create_goal(user_id: str, body: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    gid = f"plangoal_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    db.execute(
        """INSERT INTO plan_goals
           (id, user_id, title, description, target_module, target_metric, target_value, deadline)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            gid, user_id,
            body["title"], body.get("description", ""),
            body["target_module"], body["target_metric"], body["target_value"],
            body.get("deadline"),
        ),
    )
    publish_event_safe(PlanGoalCreated(
        user_id=user_id,
        goal_id=gid,
        title=body["title"],
        target_module=body["target_module"],
        target_metric=body["target_metric"],
        target_value=body["target_value"],
        deadline=str(body.get("deadline") or ""),
    ))
    return get_goal(user_id, gid)  # type: ignore[return-value]


def get_goal(user_id: str, goal_id: str) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_goals WHERE id=%s AND user_id=%s",
        (goal_id, user_id),
    )
    return row_to_goal(row) if row else None


def update_goal(user_id: str, goal_id: str, body: dict) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    sets: list[str] = []
    params: list = []
    for k in ("title", "description", "target_value", "current_value", "deadline", "status"):
        v = body.get(k)
        if v is None:
            continue
        sets.append(f"{k}=%s")
        params.append(v)
    if not sets:
        return get_goal(user_id, goal_id)
    sets.append("updated_at=NOW()")
    params.extend([goal_id, user_id])
    db.execute(
        f"UPDATE plan_goals SET {', '.join(sets)} WHERE id=%s AND user_id=%s",
        tuple(params),
    )
    return get_goal(user_id, goal_id)
