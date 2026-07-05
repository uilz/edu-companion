"""Reading 标注服务 (annotations)

依据 docs/modules/reading/data-model.md §1 + ADR 0003
- 5 色标注 (yellow/blue/green/purple/orange)
- 5 种 intent (important_concept/data_fact/quotable/doubt/conflict)
- 每条标注存 material_id / chunk_id / start_offset / end_offset / linked_node_id
- 颜色 → 后续动作的映射

颜色 → 后续动作提示（依据 events.md §3.2）：
    yellow   important_concept  建议关联知识点或创建 FlashCard
    blue     data_fact          建议提取为数据卡片
    green    quotable           保留为原文引用
    purple   doubt              建议发起对话讨论 (ExplainCard)
    orange   conflict           建议对比分析
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.event_bus_utils import publish_event_safe

logger = logging.getLogger(__name__)


# ── 5 色 → 后续动作映射（前后端共享） ──

COLOR_INTENT_MAP: dict[str, str] = {
    "yellow": "important_concept",
    "blue": "data_fact",
    "green": "quotable",
    "purple": "doubt",
    "orange": "conflict",
}

# 颜色 → 后续动作提示 (前后端共享)
COLOR_FOLLOWUP: dict[str, dict[str, str]] = {
    "yellow": {
        "label": "重要概念",
        "intent": "important_concept",
        "suggestion": "建议关联知识点或创建 FlashCard",
        "next_action": "link_node_or_create_card",
    },
    "blue": {
        "label": "数据/事实",
        "intent": "data_fact",
        "suggestion": "建议提取为数据卡片",
        "next_action": "create_data_card",
    },
    "green": {
        "label": "可引用段落",
        "intent": "quotable",
        "suggestion": "保留为原文引用",
        "next_action": "keep_quote",
    },
    "purple": {
        "label": "疑问/反驳",
        "intent": "doubt",
        "suggestion": "建议发起对话讨论 (ExplainCard)",
        "next_action": "start_conversation",
    },
    "orange": {
        "label": "与其他内容冲突",
        "intent": "conflict",
        "suggestion": "建议对比分析",
        "next_action": "compare_analysis",
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str = "ra") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _ensure_tables() -> None:
    from app.services.reading import _ensure_tables as _et
    _et()


def _row_to_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    out = dict(row)
    for col in ("chapters_visited", "state_snapshot"):
        v = out.get(col)
        if isinstance(v, str):
            try:
                out[col] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                out[col] = [] if col != "state_snapshot" else {}
    return out


def _publish(event: Any) -> None:
    """发布事件到 EventBus — 委托给 publish_event_safe (fire-and-forget)"""
    publish_event_safe(event)


# ── 标注 CRUD ──


def create_annotation(
    user_id: str,
    material_id: str,
    color: str,
    intent: Optional[str] = None,
    chunk_id: str = "",
    start_offset: int = 0,
    end_offset: int = 0,
    text: str = "",
    note: str = "",
    linked_node_id: str = "",
) -> dict:
    """创建标注。

    必填: material_id, color
    可选: chunk_id, offsets, text, note, linked_node_id
    """
    _ensure_tables()
    if color not in COLOR_INTENT_MAP:
        raise ValueError(f"invalid color: {color} (must be one of {list(COLOR_INTENT_MAP)})")
    if intent is None:
        intent = COLOR_INTENT_MAP[color]
    if intent not in {v["intent"] for v in COLOR_FOLLOWUP.values()}:
        raise ValueError(f"invalid intent: {intent}")

    from app.infrastructure.db.database import get_db
    db = get_db()
    aid = _uid("ra")
    now = _now()
    db.execute(
        """
        INSERT INTO reading_annotations (
            id, user_id, material_id, chunk_id, start_offset, end_offset,
            color, intent, text, note, linked_node_id,
            is_processed, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
        """,
        (aid, user_id, material_id, chunk_id or None, start_offset, end_offset,
         color, intent, text, note, linked_node_id or None, now, now),
    )
    from shared.events import ReadingAnnotationCreated
    _publish(ReadingAnnotationCreated(
        user_id=user_id,
        annotation_id=aid,
        material_id=material_id,
        chunk_id=chunk_id,
        color=color,  # type: ignore[arg-type]
        intent=intent,  # type: ignore[arg-type]
        linked_node_id=linked_node_id or "",
        created_at=now,
    ))
    return get_annotation(user_id, aid) or {}


def get_annotation(user_id: str, annotation_id: str) -> dict | None:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM reading_annotations WHERE id = %s AND user_id = %s",
        (annotation_id, user_id),
    )
    return _row_to_dict(row)


def list_annotations(
    user_id: str,
    material_id: Optional[str] = None,
    color: Optional[str] = None,
    chunk_id: Optional[str] = None,
    linked_node_id: Optional[str] = None,
    is_processed: Optional[bool] = None,
    limit: int = 200,
) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    conds = ["user_id = %s"]
    params: list[Any] = [user_id]
    if material_id:
        conds.append("material_id = %s")
        params.append(material_id)
    if color:
        conds.append("color = %s")
        params.append(color)
    if chunk_id:
        conds.append("chunk_id = %s")
        params.append(chunk_id)
    if linked_node_id:
        conds.append("linked_node_id = %s")
        params.append(linked_node_id)
    if is_processed is not None:
        conds.append("is_processed = %s")
        params.append(is_processed)
    where = " AND ".join(conds)
    rows = db.fetchall(
        f"SELECT * FROM reading_annotations WHERE {where} "
        f"ORDER BY created_at DESC LIMIT %s",
        tuple(params) + (limit,),
    )
    return [_row_to_dict(r) for r in rows]  # type: ignore[misc]


def list_annotations_grouped_by_color(
    user_id: str,
    material_id: str,
) -> dict[str, list[dict]]:
    """按颜色分组的标注（侧栏使用）。"""
    annotations = list_annotations(user_id, material_id=material_id)
    grouped: dict[str, list[dict]] = {c: [] for c in COLOR_INTENT_MAP}
    for a in annotations:
        grouped.setdefault(a["color"], []).append(a)
    return grouped


def update_annotation(
    user_id: str,
    annotation_id: str,
    payload: dict,
) -> dict | None:
    """更新标注（白名单字段）。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = get_annotation(user_id, annotation_id)
    if not existing:
        return None
    allowed = {"text", "note", "color", "intent", "linked_node_id", "is_processed"}
    sets: list[str] = []
    params: list[Any] = []
    changed: list[str] = []
    for k in allowed:
        if k in payload and payload[k] is not None:
            v = payload[k]
            if v != existing.get(k):
                changed.append(k)
            sets.append(f"{k} = %s")
            params.append(v)
    if not sets:
        return existing
    sets.append("updated_at = %s")
    params.append(_now())
    params.extend([annotation_id, user_id])
    db.execute(
        f"UPDATE reading_annotations SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
        tuple(params),
    )
    from shared.events import ReadingAnnotationUpdated
    _publish(ReadingAnnotationUpdated(
        user_id=user_id, annotation_id=annotation_id,
        changed_fields=changed, updated_at=_now(),
    ))
    return get_annotation(user_id, annotation_id)


def delete_annotation(user_id: str, annotation_id: str) -> bool:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = get_annotation(user_id, annotation_id)
    if not existing:
        return False
    db.execute(
        "DELETE FROM reading_annotations WHERE id = %s AND user_id = %s",
        (annotation_id, user_id),
    )
    from shared.events import ReadingAnnotationDeleted
    _publish(ReadingAnnotationDeleted(
        user_id=user_id, annotation_id=annotation_id, deleted_at=_now(),
    ))
    return True


def mark_annotation_processed(
    user_id: str,
    annotation_id: str,
    target_module: Any,
    target_ref_id: str,
) -> dict | None:
    """标注被处理后标记 + 发布 ReadingAnnotationProcessed 事件。

    target_module 必须是 CrossModuleTarget 枚举
    """
    from shared.events import CrossModuleTarget, ReadingAnnotationProcessed
    if not isinstance(target_module, CrossModuleTarget):
        # 尝试用字符串转换
        target_module = CrossModuleTarget(str(target_module))
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    db.execute(
        "UPDATE reading_annotations SET is_processed = TRUE, updated_at = %s "
        "WHERE id = %s AND user_id = %s",
        (_now(), annotation_id, user_id),
    )
    _publish(ReadingAnnotationProcessed(
        user_id=user_id, annotation_id=annotation_id,
        target_module=target_module, target_ref_id=target_ref_id,
        processed_at=_now(),
    ))
    return get_annotation(user_id, annotation_id)
