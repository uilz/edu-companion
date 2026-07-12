"""Planning — 周期回顾 (plan_periodic_reviews) 领域服务"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from app.infrastructure.event_bus_utils import publish_event_safe
from app.services.planning import _ensure_tables
from app.services.planning._converters import row_to_review
from shared.events import PlanPeriodicReviewGenerated

logger = logging.getLogger(__name__)


def list_reviews(user_id: str, limit: int = 20) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM plan_periodic_reviews WHERE user_id=%s ORDER BY period_start DESC LIMIT %s",
        (user_id, limit),
    )
    return [row_to_review(r) for r in rows]


def generate_review(user_id: str, body: dict) -> dict:
    """生成周期回顾（聚合 plan_items / brief / goal 数据）"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rid = f"review_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    period_type = body["period_type"]
    period_start = body["period_start"]
    period_end = body["period_end"]
    items_count = db.fetchone(
        """SELECT COUNT(*) as c, SUM(estimated_minutes) as m, SUM(actual_minutes) as am
           FROM plan_items
           WHERE user_id=%s AND plan_date BETWEEN %s AND %s""",
        (user_id, period_start, period_end),
    )
    completed_count = db.fetchone(
        """SELECT COUNT(*) as c FROM plan_items
           WHERE user_id=%s AND plan_date BETWEEN %s AND %s AND status='completed'""",
        (user_id, period_start, period_end),
    )
    by_module = db.fetchall(
        """SELECT source_module, COUNT(*) as c, SUM(actual_minutes) as m
           FROM plan_items
           WHERE user_id=%s AND plan_date BETWEEN %s AND %s
           GROUP BY source_module""",
        (user_id, period_start, period_end),
    )
    summary = {
        "items_total": items_count["c"] if items_count else 0,
        "items_completed": completed_count["c"] if completed_count else 0,
        "estimated_minutes": items_count["m"] if items_count else 0,
        "actual_minutes": items_count["am"] if items_count else 0,
        "by_module": [
            {"source_module": r["source_module"], "count": r["c"], "minutes": r["m"] or 0}
            for r in by_module
        ],
    }
    db.execute(
        """INSERT INTO plan_periodic_reviews
           (id, user_id, period_type, period_start, period_end, summary_data, user_note)
           VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)""",
        (rid, user_id, period_type, period_start, period_end,
         json.dumps(summary, ensure_ascii=False), body.get("user_note", "")),
    )
    publish_event_safe(PlanPeriodicReviewGenerated(
        user_id=user_id,
        review_id=rid,
        period_type=period_type,
        period_start=str(period_start),
        period_end=str(period_end),
        summary_data=summary,
    ))
    row = db.fetchone("SELECT * FROM plan_periodic_reviews WHERE id=%s", (rid,))
    return row_to_review(row) if row else {"id": rid, "summary_data": summary}
