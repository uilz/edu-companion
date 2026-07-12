"""Planning — 视图方案 (plan_view_layouts) 领域服务"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from app.services.planning import _ensure_tables
from app.services.planning._converters import row_to_view_layout

logger = logging.getLogger(__name__)


def list_view_layouts(user_id: str) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM plan_view_layouts WHERE user_id=%s ORDER BY is_default DESC, created_at DESC",
        (user_id,),
    )
    return [row_to_view_layout(r) for r in rows]


def create_view_layout(user_id: str, body: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    lid = f"vlayout_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    if body.get("is_default"):
        db.execute(
            "UPDATE plan_view_layouts SET is_default=FALSE WHERE user_id=%s",
            (user_id,),
        )
    db.execute(
        """INSERT INTO plan_view_layouts
           (id, user_id, name, view_type, filters, layout, is_default)
           VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)""",
        (
            lid, user_id, body["name"], body["view_type"],
            json.dumps(body.get("filters") or {}, ensure_ascii=False),
            json.dumps(body.get("layout") or {}, ensure_ascii=False),
            body.get("is_default", False),
        ),
    )
    row = db.fetchone("SELECT * FROM plan_view_layouts WHERE id=%s", (lid,))
    return row_to_view_layout(row) if row else {"id": lid}


def get_view_layout(user_id: str, layout_id: str) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_view_layouts WHERE id=%s AND user_id=%s",
        (layout_id, user_id),
    )
    return row_to_view_layout(row) if row else None
