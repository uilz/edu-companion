"""Reading 笔记服务 (notes)

依据 docs/modules/reading/overview.md §5 + ADR 0003
**关键决策**：**不**新建 reading_notes 表，笔记 = FlashCard 反思型。

笔记三段式 → FlashCard 字段映射：
    我的问题     → front_text      (正面)
    关键论述     → back_context    (反面附加)
    我的回应     → back_text       (反面)
    关联材料     → source_ref.material_id
    关联段落     → source_ref.chunk_id_range
    关联知识点   → linked_node_ids
    来源         → source='reading_note'  (cross_module_source='reading')
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.event_bus_utils import publish_event_safe

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_tables() -> None:
    from app.services.reading import _ensure_tables as _et
    _et()


def _publish(event: Any) -> None:
    """发布事件 — 委托给 publish_event_safe (自动处理 sync/async 上下文)"""
    publish_event_safe(event)


def _resolve_flashcard_service():
    """延迟获取 FlashCardService 单例。"""
    from app.api.flashcard.service import get_flashcard_service
    try:
        from app.application.di import container
        return get_flashcard_service(event_bus=container.event_bus)
    except Exception:
        return get_flashcard_service(event_bus=None)


def create_reading_note(
    user_id: str,
    material_id: str,
    front_text: str,
    back_text: str = "",
    back_context: str = "",
    linked_node_ids: Optional[list[str]] = None,
    chunk_id: str = "",
    chunk_id_range: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    language: str = "",
    session_id: str = "",
) -> dict:
    """创建阅读笔记 = 创建 FlashCard 反思型。

    Args:
        user_id: 用户 ID
        material_id: 关联材料 ID
        front_text: 我的问题（正面）
        back_text: 我的回应（反面）
        back_context: 关键论述（反面附加）
        linked_node_ids: 关联的 CognitiveNode IDs
        chunk_id: 当前段落（写入 source_ref.chunk_id）
        chunk_id_range: 段落范围 [start_chunk, end_chunk]
        tags: 标签
        language: 语言
        session_id: 阅读会话 ID（用于更新 reading_sessions.notes_created）
    """
    if not front_text or not front_text.strip():
        raise ValueError("front_text 不能为空（笔记的'我的问题'部分）")
    _ensure_tables()
    linked_nodes = list(linked_node_ids or [])
    if not linked_nodes:
        raise ValueError("至少关联一个 CognitiveNode (linked_node_ids)")
    source_ref: dict[str, Any] = {
        "module": "reading",
        "id": material_id,
        "sub_id": chunk_id or "",
        "chunk_id_range": chunk_id_range or ([chunk_id] if chunk_id else []),
        "title": "",
    }
    fc_service = _resolve_flashcard_service()
    # card_type=7 是反思型 (依据 flashcard/data-model.md §5.1)
    payload = {
        "type": 7,
        # source 保留 reading_note (子类型), cross_module_source='reading' (源模块)
        # 依据 P0-3 拆分: 内部归类 vs 跨模块引用来源
        "source": "reading_note",
        "cross_module_source": "reading",
        "front_text": front_text,
        "back_text": back_text or "",
        "back_context": back_context or "",
        "language": language or "",
        "source_ref": source_ref,
        "linked_node_ids": linked_nodes,
        "tags": tags or ["reading_note"],
    }
    card = fc_service.create_card(user_id, payload)

    # 发布 ReadingNoteCreated 事件
    from shared.events import ReadingNoteCreated
    _publish(ReadingNoteCreated(
        user_id=user_id,
        material_id=material_id,
        card_id=card["id"],
        source="reading_note",
        cross_module_source="reading",
        created_at=_now(),
    ))

    # 更新 reading_sessions.notes_created (如果提供 session_id)
    if session_id:
        try:
            from app.services.reading.sessions import update_session_activity
            update_session_activity(
                user_id, session_id,
                notes_delta=1,
                node_linked=linked_nodes[0] if linked_nodes else None,
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("更新会话 notes_created 失败: %s", e)

    return card


def list_reading_notes(
    user_id: str,
    material_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """列出阅读笔记（=FlashCard source='reading_note' 列表）。"""
    fc_service = _resolve_flashcard_service()
    res = fc_service.list_cards(user_id, source="reading_note", limit=limit)
    cards = res.get("cards", [])
    if material_id:
        cards = [
            c for c in cards
            if isinstance(c.get("source_ref"), dict)
            and c["source_ref"].get("id") == material_id
        ]
    return cards


def get_reading_note(user_id: str, card_id: str) -> dict | None:
    """获取单条阅读笔记。"""
    fc_service = _resolve_flashcard_service()
    card = fc_service.get_card(user_id, card_id)
    if not card:
        return None
    if card.get("source") != "reading_note":
        return None
    return card
