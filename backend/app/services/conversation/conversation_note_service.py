"""对话笔记服务 — Phase 3 对话壳与闪卡整合

职责：
- 对话笔记的 CRUD
- 发布 ConversationNoteCreatedAsFlashcard 事件
- 订阅 FlashCardUpdated 事件，反向同步内容字段

设计要点：
- 笔记是闪卡的"源内容视图"，内容字段（front_text/back_text/back_context/tags/linked_node_ids）
  由笔记侧所有；FSRS 参数由闪卡侧所有。
- 反向同步时只更新内容字段，不触碰闪卡记忆参数。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.db.database import get_db
from app.infrastructure.event_bus_utils import publish_event_safe
from shared.events import (
    ConversationNoteCreatedAsFlashcard,
    FlashCardUpdated,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str = "cn") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def _parse_json(raw: Any, default: Any = None) -> Any:
    if raw is None or raw == "" or raw == {} or raw == []:
        return default if default is not None else {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def _row_to_note(row: dict) -> dict:
    """数据库行 → 笔记 dict"""
    if row is None:
        return None
    out = dict(row)
    for col in ("tags", "linked_node_ids", "source_ref", "field_versions"):
        out[col] = _parse_json(out.get(col), {} if col == "source_ref" else [])
    return out


# ── 公开 API ──


def create_note(
    user_id: str,
    conv_id: str,
    source_message_id: str,
    front_text: str,
    back_text: str = "",
    back_context: str = "",
    language: str = "",
    linked_node_ids: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    auto_create_flashcard: bool = True,
) -> dict:
    """创建对话笔记，并可选择自动发布事件创建闪卡。

    Args:
        auto_create_flashcard: 为 True 时立即发布 ConversationNoteCreatedAsFlashcard。
    """
    if not front_text or not front_text.strip():
        raise ValueError("front_text 不能为空")

    db = get_db()
    note_id = _uid("note")
    now = _now()
    linked_nodes = list(linked_node_ids or [])
    tag_list = list(tags or [])

    source_ref = {
        "module": "conversation",
        "id": conv_id,
        "sub_id": source_message_id,
        "metadata": {"note_id": note_id, "message_role": "assistant"},
    }

    db.execute(
        """INSERT INTO conversation_notes
           (id, user_id, conv_id, source_message_id, front_text, back_text, back_context,
            language, tags, linked_node_ids, source_ref, flashcard_id, status,
            field_versions, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            note_id, user_id, conv_id, source_message_id,
            front_text.strip(), back_text or "", back_context or "",
            language or "", _json(tag_list), _json(linked_nodes),
            _json(source_ref), None, "draft", _json({}), now, now,
        ),
    )

    note = _row_to_note(db.fetchone(
        "SELECT * FROM conversation_notes WHERE id = %s", (note_id,)
    ))

    if auto_create_flashcard:
        publish_event_safe(ConversationNoteCreatedAsFlashcard(
            user_id=user_id,
            conv_id=conv_id,
            note_id=note_id,
            source_message_id=source_message_id,
            front_text=front_text.strip(),
            back_text=back_text or "",
            linked_node_ids=linked_nodes,
            source_ref=source_ref,
            created_at=now,
        ))

    return note


def update_note(
    user_id: str,
    note_id: str,
    front_text: Optional[str] = None,
    back_text: Optional[str] = None,
    back_context: Optional[str] = None,
    language: Optional[str] = None,
    linked_node_ids: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """更新笔记内容字段，并 bump field_versions。"""
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM conversation_notes WHERE id = %s AND user_id = %s",
        (note_id, user_id),
    )
    if not row:
        raise ValueError(f"Note not found: {note_id}")

    updates: dict[str, Any] = {}
    if front_text is not None:
        updates["front_text"] = front_text.strip()
    if back_text is not None:
        updates["back_text"] = back_text
    if back_context is not None:
        updates["back_context"] = back_context
    if language is not None:
        updates["language"] = language
    if linked_node_ids is not None:
        updates["linked_node_ids"] = _json(list(linked_node_ids))
    if tags is not None:
        updates["tags"] = _json(list(tags))

    if not updates:
        return _row_to_note(row)

    updates["updated_at"] = _now().isoformat()

    # bump field_versions
    field_versions = _parse_json(row.get("field_versions"), {})
    for field in updates:
        if field in ("front_text", "back_text", "back_context", "language", "linked_node_ids", "tags"):
            field_versions[field] = int(field_versions.get(field, 0)) + 1
    updates["field_versions"] = _json(field_versions)

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [note_id, user_id]
    db.execute(
        f"UPDATE conversation_notes SET {set_clause} WHERE id = %s AND user_id = %s",
        values,
    )

    return _row_to_note(db.fetchone(
        "SELECT * FROM conversation_notes WHERE id = %s", (note_id,)
    ))


def delete_note(user_id: str, note_id: str) -> bool:
    """删除对话笔记。若已关联闪卡，不级联删除闪卡（保留学习材料）。"""
    db = get_db()
    return db.execute_with_rowcount(
        "DELETE FROM conversation_notes WHERE id = %s AND user_id = %s",
        (note_id, user_id),
    ) > 0


def get_note(user_id: str, note_id: str) -> dict | None:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM conversation_notes WHERE id = %s AND user_id = %s",
        (note_id, user_id),
    )
    return _row_to_note(row)


def list_notes_by_conv(user_id: str, conv_id: str) -> list[dict]:
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM conversation_notes WHERE user_id = %s AND conv_id = %s ORDER BY created_at DESC",
        (user_id, conv_id),
    )
    return [_row_to_note(r) for r in rows]


def link_flashcard(user_id: str, note_id: str, flashcard_id: str) -> dict:
    """闪卡创建后回填 flashcard_id，并把状态改为 synced。"""
    db = get_db()
    db.execute(
        """UPDATE conversation_notes
           SET flashcard_id = %s, status = 'synced', updated_at = %s
           WHERE id = %s AND user_id = %s""",
        (flashcard_id, _now().isoformat(), note_id, user_id),
    )
    return get_note(user_id, note_id)


# ── 事件订阅 ──


async def on_flashcard_updated(event: FlashCardUpdated) -> None:
    """订阅 FlashCardUpdated，反向同步内容字段回 conversation_notes。

    只更新内容字段；FSRS 参数、status、is_resolved 等由闪卡侧维护。
    若笔记侧更新时间 >= 闪卡事件时间，跳过（源优先）。
    """
    try:
        card_id = getattr(event, "card_id", "")
        user_id = getattr(event, "user_id", "")
        changed_fields = getattr(event, "changed_fields", []) or []

        content_fields = {"front_text", "back_text", "back_context", "language", "tags", "linked_node_ids"}
        to_sync = [f for f in changed_fields if f in content_fields]
        if not to_sync or not card_id or not user_id:
            return

        # 从闪卡表读取最新内容字段值
        from app.api.flashcard.service import get_flashcard_service
        svc = get_flashcard_service()
        card = svc.get_card(user_id, card_id)
        if not card:
            return

        db = get_db()
        note = db.fetchone(
            "SELECT * FROM conversation_notes WHERE flashcard_id = %s AND user_id = %s",
            (card_id, user_id),
        )
        if not note:
            return

        # 源优先：若笔记更新时间不早于闪卡事件时间，跳过
        note_updated = note.get("updated_at")
        event_occurred = getattr(event, "updated_at", None) or getattr(event, "occurred_at", None)
        if note_updated and event_occurred:
            # 统一为 timezone-aware 再比较（DB 可能返回 naive）
            if note_updated.tzinfo is None:
                note_updated = note_updated.replace(tzinfo=timezone.utc)
            if event_occurred.tzinfo is None:
                event_occurred = event_occurred.replace(tzinfo=timezone.utc)
            if note_updated >= event_occurred:
                logger.debug("跳过反向同步：笔记源更新更新 (note=%s)", note["id"])
                return

        updates: dict[str, Any] = {}
        for field in to_sync:
            val = card.get(field)
            if val is None:
                continue
            if field in ("tags", "linked_node_ids"):
                updates[field] = _json(list(val))
            else:
                updates[field] = val

        if not updates:
            return

        updates["updated_at"] = _now().isoformat()
        field_versions = _parse_json(note.get("field_versions"), {})
        for field in to_sync:
            field_versions[field] = int(field_versions.get(field, 0)) + 1
        updates["field_versions"] = _json(field_versions)

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [note["id"], user_id]
        db.execute(
            f"UPDATE conversation_notes SET {set_clause} WHERE id = %s AND user_id = %s",
            values,
        )
        logger.info("反向同步闪卡内容到笔记: note=%s card=%s fields=%s", note["id"], card_id, to_sync)
    except Exception:
        logger.exception("FlashCardUpdated 反向同步失败")
