"""Reading 偏好服务 (prefs)

依据 docs/modules/reading/data-model.md §4 + ADR 0003
- 阅读模式偏好 (精读/略读/回顾)
- 是否高亮已掌握/薄弱知识点
- 回顾提醒默认天数 (7/30/90)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_tables() -> None:
    from app.services.reading import _ensure_tables as _et
    _et()


def _row_to_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    out = dict(row)
    days = out.get("review_reminder_days")
    if isinstance(days, str):
        try:
            out["review_reminder_days"] = json.loads(days)
        except (json.JSONDecodeError, TypeError):
            out["review_reminder_days"] = [7, 30, 90]
    return out


DEFAULT_PREFS = {
    "default_mode": "intensive",
    "highlight_mastered": True,
    "highlight_weak": True,
    "auto_open_sidebar": True,
    "sync_scroll_default": False,
    "review_reminder_days": [7, 30, 90],
}


def get_prefs(user_id: str) -> dict:
    """获取用户阅读偏好（不存在则使用默认）。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM reading_prefs WHERE user_id = %s",
        (user_id,),
    )
    if row:
        return _row_to_dict(row) or {**DEFAULT_PREFS}
    return {**DEFAULT_PREFS, "user_id": user_id}


def upsert_prefs(user_id: str, payload: dict) -> dict:
    """更新或初始化阅读偏好。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    current = get_prefs(user_id)
    merged = {**current, **payload}
    days = merged.get("review_reminder_days") or DEFAULT_PREFS["review_reminder_days"]
    if not isinstance(days, list):
        days = DEFAULT_PREFS["review_reminder_days"]
    db.execute(
        """
        INSERT INTO reading_prefs (
            user_id, default_mode, highlight_mastered, highlight_weak,
            auto_open_sidebar, sync_scroll_default, review_reminder_days,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            default_mode = EXCLUDED.default_mode,
            highlight_mastered = EXCLUDED.highlight_mastered,
            highlight_weak = EXCLUDED.highlight_weak,
            auto_open_sidebar = EXCLUDED.auto_open_sidebar,
            sync_scroll_default = EXCLUDED.sync_scroll_default,
            review_reminder_days = EXCLUDED.review_reminder_days,
            updated_at = EXCLUDED.updated_at
        """,
        (
            user_id,
            merged.get("default_mode", "intensive"),
            bool(merged.get("highlight_mastered", True)),
            bool(merged.get("highlight_weak", True)),
            bool(merged.get("auto_open_sidebar", True)),
            bool(merged.get("sync_scroll_default", False)),
            json.dumps(days, ensure_ascii=False),
            current.get("created_at") or _now(),
            _now(),
        ),
    )
    return get_prefs(user_id)
