"""闪卡壳 — 对话笔记事件处理器

订阅 ConversationNoteCreatedAsFlashcard，自动创建反思型闪卡（type=7），
并回填 conversation_notes.flashcard_id 以建立 1:1 关联。
"""
from __future__ import annotations

import logging
from typing import Any

from shared.events import ConversationNoteCreatedAsFlashcard, DomainEvent

logger = logging.getLogger(__name__)


class ConversationNoteFlashcardHandler:
    """处理对话笔记 → 闪卡的创建链路。"""

    def __init__(self) -> None:
        self._bus: Any = None
        self._subscribed = False

    def subscribe(self, bus: Any) -> None:
        """订阅 EventBus/PersistentEventBus。"""
        if self._subscribed:
            return
        self._bus = bus
        from app.infrastructure.event_bus import EventBus
        from app.infrastructure.persistent_event_bus import PersistentEventBus
        if not isinstance(bus, (EventBus, PersistentEventBus)):
            logger.warning("传入对象不是 EventBus 实例 (%s)，跳过订阅", type(bus).__module__)
            return
        bus.subscribe("ConversationNoteCreatedAsFlashcard", self._on_note_created_as_flashcard)
        self._subscribed = True
        logger.info("📡 闪卡壳已订阅 ConversationNoteCreatedAsFlashcard")

    def unsubscribe(self) -> None:
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("ConversationNoteCreatedAsFlashcard", self._on_note_created_as_flashcard)
        self._subscribed = False

    async def _on_note_created_as_flashcard(self, event: DomainEvent) -> None:
        if not isinstance(event, ConversationNoteCreatedAsFlashcard):
            return
        try:
            await self._create_flashcard_from_note(event)
        except Exception:
            logger.exception("从对话笔记创建闪卡失败: note=%s", event.note_id)

    async def _create_flashcard_from_note(self, event: ConversationNoteCreatedAsFlashcard) -> dict | None:
        from app.api.flashcard.service import get_flashcard_service

        svc = get_flashcard_service(event_bus=self._bus)
        source_ref = event.source_ref or {}
        # 确保 source_ref 包含 note_id 等必要元数据
        metadata = dict(source_ref.get("metadata", {}))
        metadata.setdefault("note_id", event.note_id)
        source_ref.setdefault("module", "conversation")
        source_ref.setdefault("id", event.conv_id)
        source_ref.setdefault("sub_id", event.source_message_id)
        source_ref["metadata"] = metadata

        payload = {
            "type": 7,  # 反思型
            "source": "conversation",
            "cross_module_source": "conversation",
            "front_text": event.front_text,
            "back_text": event.back_text,
            "back_context": "",
            "language": "",
            "linked_node_ids": event.linked_node_ids,
            "source_ref": source_ref,
            "tags": ["对话笔记"],
        }
        card = svc.create_card(event.user_id, payload)
        card_id = card.get("id")

        # 回填 conversation_notes.flashcard_id
        try:
            from app.services.conversation.conversation_note_service import link_flashcard
            link_flashcard(event.user_id, event.note_id, card_id)
        except Exception:
            logger.exception("回填 flashcard_id 失败: note=%s card=%s", event.note_id, card_id)

        logger.info("📝 从对话笔记创建闪卡: note=%s card=%s", event.note_id, card_id)
        return card


# 全局单例
conversation_note_flashcard_handler = ConversationNoteFlashcardHandler()
