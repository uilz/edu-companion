"""
解释卡片 CRUD REST API (D14: 嵌入 messages 表)

卡片是用户选中文本后触发的浮动标注：
- 绑定到 message_id（所属消息），出现在选中文本区域旁
- 可拖动（posX / posY）
- 可递归折叠/删除
- D14: 砍 explain_cards 独立表，卡片数据存入 messages.metadata.explain_cards JSONB 数组
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from shared.constants import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-tree/explain-cards", tags=["解释卡片"])


# ── 数据模型 ──

def _card_to_dict(card: dict) -> dict:
    """ensure card dict has all expected fields"""
    return {
        "id": card.get("id", ""),
        "user_id": card.get("user_id", ""),
        "conversation_id": card.get("conversation_id", ""),
        "message_id": card.get("message_id", ""),
        "depth": int(card.get("depth", 1)),
        "parent_card_id": card.get("parent_card_id"),
        "selected_text": card.get("selected_text", ""),
        "source_message_text": card.get("source_message_text", ""),
        "context_node_id": card.get("context_node_id"),
        "explanation": card.get("explanation", ""),
        "mastery": card.get("mastery", "unknown"),
        "pos_x": float(card.get("pos_x", 0)),
        "pos_y": float(card.get("pos_y", 0)),
        "collapsed": bool(card.get("collapsed", False)),
        "conversation": card.get("conversation", []) if isinstance(card.get("conversation"), list) else [],
        "width": float(card["width"]) if card.get("width") else None,
        "height": float(card["height"]) if card.get("height") else None,
        "char_start": int(card["char_start"]) if card.get("char_start") is not None else None,
        "created_at": card.get("created_at", ""),
        "updated_at": card.get("updated_at", ""),
    }


# ── 内部工具 ──

def _get_cards_from_msg(message_id: str) -> list[dict]:
    """从消息的 metadata.explain_cards 读取所有卡片"""
    from app.services.conversation.message_repository import get_message_repo
    node = get_message_repo().get(message_id)
    if not node or not node.metadata:
        return []
    cards = node.metadata.get("explain_cards", [])
    if isinstance(cards, list):
        return cards
    return []


def _save_cards_to_msg(message_id: str, user_id: str, cards: list[dict]) -> None:
    """将卡片列表保存到消息的 metadata.explain_cards"""
    from app.services.conversation.message_repository import get_message_repo
    repo = get_message_repo()
    node = repo.get(message_id)
    if node:
        if not node.metadata:
            node.metadata = {}
        node.metadata["explain_cards"] = cards
        repo.update(node, user_id)


def _get_descendant_card_ids(message_id: str, card_id: str) -> list[str]:
    """递归获取所有子孙卡片 ID（从消息内嵌卡片中查找）"""
    cards = _get_cards_from_msg(message_id)
    ids = []
    for card in cards:
        if card.get("parent_card_id") == card_id:
            ids.append(card["id"])
            ids.extend(_get_descendant_card_ids(message_id, card["id"]))
    return ids


# ════════════════════════════════════════
#  API
# ════════════════════════════════════════


@router.get("", summary="获取对话的解释卡片列表")
async def list_cards(
    conversation_id: str = Query(...),
    user_id: str = Query(default=None),
):
    """
    D14: 从 messages 表的 metadata.explain_cards 读取。
    遍历该对话下的所有消息，收集所有嵌入卡片。
    """
    uid = get_user_id(user_id)
    from app.services.conversation.message_repository import get_message_repo
    repo = get_message_repo()
    all_messages = repo.load_by_directory(uid, conversation_id)

    all_cards = []
    for node in all_messages.values():
        cards = node.metadata.get("explain_cards", []) if node.metadata else []
        if isinstance(cards, list):
            for card in cards:
                if card.get("conversation_id") == conversation_id:
                    all_cards.append(_card_to_dict(card))

    all_cards.sort(key=lambda c: c.get("created_at", ""))
    return all_cards


@router.post("", summary="创建解释卡片")
async def create_card(body: dict, user_id: str = Query(default=None)):
    """
    创建解释卡片

    D14: 写入 messages.metadata.explain_cards 数组。

    请求体:
    {
        "conversation_id": "...",
        "message_id": "...",
        "depth": 1,
        "parent_card_id": null,
        "selected_text": "...",
        "source_message_text": "...",
        "context_node_id": null,
        "pos_x": 0,
        "pos_y": 0
    }
    """
    uid = get_user_id(user_id)
    message_id = body.get("message_id", "")
    if not message_id:
        raise HTTPException(status_code=400, detail="缺少 message_id")

    card_id = f"explain_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uid}"
    now = datetime.now().isoformat()

    card = {
        "id": card_id,
        "user_id": uid,
        "conversation_id": body.get("conversation_id", ""),
        "message_id": message_id,
        "depth": int(body.get("depth", 1)),
        "parent_card_id": body.get("parent_card_id") or None,
        "selected_text": body.get("selected_text", ""),
        "source_message_text": body.get("source_message_text", ""),
        "context_node_id": body.get("context_node_id") or None,
        "explanation": "",
        "mastery": "unknown",
        "pos_x": float(body.get("pos_x", 0)),
        "pos_y": float(body.get("pos_y", 0)),
        "collapsed": False,
        "conversation": body.get("conversation", []),
        "width": None,
        "height": None,
        "char_start": body.get("char_start") if body.get("char_start") is not None else None,
        "created_at": now,
        "updated_at": now,
    }

    # 追加到消息的 metadata.explain_cards
    cards = _get_cards_from_msg(message_id)
    cards.append(card)
    _save_cards_to_msg(message_id, uid, cards)

    logger.info("解释卡片已创建: %s (depth=%s, msg=%s)", card_id, body.get("depth"), message_id)
    return _card_to_dict(card)


@router.patch("/{card_id}", summary="更新解释卡片")
async def update_card(card_id: str, body: dict, user_id: str = Query(default=None)):
    """
    更新解释卡片字段（explanation, mastery, pos_x, pos_y, collapsed 等）

    D14: 从 messages.metadata.explain_cards 读取并更新。
    """
    uid = get_user_id(user_id)
    from app.services.conversation.message_repository import get_message_repo
    repo = get_message_repo()

    # 在所有消息中搜索该卡片
    all_messages = repo.load_all(uid)
    found_card = None
    found_msg_id = None
    found_cards = None

    for msg_id, node in all_messages.items():
        cards = node.metadata.get("explain_cards", []) if node.metadata else []
        for i, card in enumerate(cards):
            if card.get("id") == card_id:
                found_card = card
                found_msg_id = msg_id
                found_cards = cards
                break
        if found_card:
            break

    if not found_card:
        raise HTTPException(status_code=404, detail="解释卡片不存在")

    # 更新字段
    updatable = ["explanation", "mastery", "pos_x", "pos_y", "collapsed",
                  "conversation", "width", "height"]
    for field in updatable:
        if field in body:
            if field == "pos_x" or field == "pos_y":
                found_card[field] = float(body[field])
            elif field == "collapsed":
                found_card[field] = bool(body[field])
            elif field == "width" or field == "height":
                found_card[field] = float(body[field]) if body[field] is not None else None
            else:
                found_card[field] = body[field]

    found_card["updated_at"] = datetime.now().isoformat()

    _save_cards_to_msg(found_msg_id, uid, found_cards)
    logger.info("解释卡片已更新: %s", card_id)
    return _card_to_dict(found_card)


@router.delete("/{card_id}", summary="删除解释卡片及子孙")
async def delete_card(card_id: str, user_id: str = Query(default=None)):
    """
    级联删除指定卡片及其所有子孙卡片

    D14: 从 messages.metadata.explain_cards 中移除。
    """
    uid = get_user_id(user_id)
    from app.services.conversation.message_repository import get_message_repo
    repo = get_message_repo()

    # 在所有消息中搜索该卡片
    all_messages = repo.load_all(uid)
    found_msg_id = None
    found_cards = None

    for msg_id, node in all_messages.items():
        cards = node.metadata.get("explain_cards", []) if node.metadata else []
        for card in cards:
            if card.get("id") == card_id:
                found_msg_id = msg_id
                found_cards = cards
                break
        if found_msg_id:
            break

    if not found_msg_id:
        raise HTTPException(status_code=404, detail="解释卡片不存在")

    # 收集所有要删除的 ID（含子孙）
    all_ids = [card_id] + _get_descendant_card_ids(found_msg_id, card_id)
    ids_set = set(all_ids)

    # 从卡片列表中移除
    remaining = [c for c in found_cards if c.get("id") not in ids_set]
    _save_cards_to_msg(found_msg_id, uid, remaining)

    logger.info("解释卡片已删除（含子孙）: %s (共 %d 张)", card_id, len(all_ids))
    return {"deleted": card_id, "cascade_count": len(all_ids), "ids": all_ids}