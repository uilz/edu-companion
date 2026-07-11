"""Reading 对比阅读服务 (compare)

依据 docs/modules/reading/overview.md §8 + ADR 0003
- 左右分屏对比两个独立材料
- 同步滚动开关
- 对比分组存到 reading_comparisons
- 实际分屏数据从 file-management 拉取（不重建）
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.infrastructure.event_bus_utils import publish_event_safe

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return f"rc_{uuid.uuid4().hex[:12]}"


def _ensure_tables() -> None:
    from app.services.reading import _ensure_tables as _et
    _et()


def _publish(event) -> None:
    """发布事件 — 委托给 publish_event_safe (自动处理 sync/async 上下文)"""
    publish_event_safe(event)


# ── 对比分组 CRUD ──


def create_comparison(
    user_id: str,
    material_id_left: str,
    material_id_right: str,
    sync_scroll: bool = False,
) -> dict:
    """创建一个对比阅读分组。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    cid = _uid()
    now = _now()
    db.execute(
        """INSERT INTO reading_comparisons
           (id, user_id, material_id_left, material_id_right, sync_scroll, created_at)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (cid, user_id, material_id_left, material_id_right, sync_scroll, now),
    )
    from shared.events import ReadingComparisonCreated
    _publish(ReadingComparisonCreated(
        user_id=user_id,
        comparison_id=cid,
        material_id_left=material_id_left,
        material_id_right=material_id_right,
        sync_scroll=sync_scroll,
        created_at=now,
    ))
    return get_comparison(user_id, cid) or {}


def get_comparison(user_id: str, comparison_id: str) -> dict | None:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM reading_comparisons WHERE id = %s AND user_id = %s",
        (comparison_id, user_id),
    )
    return dict(row) if row else None


def list_comparisons(user_id: str, limit: int = 50) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT * FROM reading_comparisons
           WHERE user_id = %s
           ORDER BY created_at DESC LIMIT %s""",
        (user_id, limit),
    )
    return [dict(r) for r in rows]


# ── 对比分屏数据 (聚合标注 + 材料信息) ──


def build_compare_payload(
    user_id: str,
    material_id_left: str,
    material_id_right: str,
    sync_scroll: Optional[bool] = None,
) -> dict:
    """聚合分屏数据：左/右材料的标注 + 文本预览。"""
    from app.services.reading import annotations as ann_svc
    annotations_left = ann_svc.list_annotations(user_id, material_id=material_id_left)
    annotations_right = ann_svc.list_annotations(user_id, material_id=material_id_right)
    return {
        "material_id_left": material_id_left,
        "material_id_right": material_id_right,
        "sync_scroll": sync_scroll if sync_scroll is not None else False,
        "left": {
            "material_id": material_id_left,
            "annotations": annotations_left,
            "annotations_count": len(annotations_left),
            "by_color": _count_by_color(annotations_left),
        },
        "right": {
            "material_id": material_id_right,
            "annotations": annotations_right,
            "annotations_count": len(annotations_right),
            "by_color": _count_by_color(annotations_right),
        },
    }


def _count_by_color(annotations: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {
        "yellow": 0, "blue": 0, "green": 0, "purple": 0, "orange": 0,
    }
    for a in annotations:
        c = a.get("color")
        if c in out:
            out[c] += 1
    return out
