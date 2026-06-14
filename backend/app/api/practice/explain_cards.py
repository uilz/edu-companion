"""
解释卡片 CRUD REST API

卡片是用户选中文本后触发的浮动标注：
- 绑定到 message_id（所属消息），出现在选中文本区域旁
- 可拖动（posX / posY）
- 可递归折叠/删除
- 持久化到 explain_cards 表
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from shared.constants import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge/explain-cards", tags=["解释卡片"])


# ── 建表 ──

def _ensure_table():
    """确保 explain_cards 表存在"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS explain_cards (
            id              TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            message_id      TEXT NOT NULL,
            depth           INTEGER NOT NULL DEFAULT 1,
            parent_card_id  TEXT,
            selected_text   TEXT NOT NULL,
            source_message_text TEXT DEFAULT '',
            context_node_id TEXT,
            explanation     TEXT DEFAULT '',
            mastery         TEXT DEFAULT 'unknown',
            pos_x           REAL DEFAULT 0,
            pos_y           REAL DEFAULT 0,
            collapsed       INTEGER DEFAULT 0,
            conversation    TEXT DEFAULT '[]',
            created_at      TIMESTAMP DEFAULT NOW(),
            updated_at      TIMESTAMP DEFAULT NOW()
        )
    """)
    # Migration: add conversation column for existing databases
    try:
        db.execute("ALTER TABLE explain_cards ADD COLUMN conversation TEXT DEFAULT '[]'")
    except Exception:
        pass  # Column already exists
    # Migration: add width/height columns for resize persistence
    try:
        db.execute("ALTER TABLE explain_cards ADD COLUMN width REAL DEFAULT NULL")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE explain_cards ADD COLUMN height REAL DEFAULT NULL")
    except Exception:
        pass
    # Migration: add char_start for precise badge positioning (avoid indexOf ambiguity)
    try:
        db.execute("ALTER TABLE explain_cards ADD COLUMN char_start INTEGER DEFAULT NULL")
    except Exception:
        pass


# ── 数据模型 ──

def _row_to_dict(r: dict) -> dict:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "conversation_id": r["conversation_id"],
        "message_id": r["message_id"],
        "depth": int(r["depth"]),
        "parent_card_id": r["parent_card_id"],
        "selected_text": r["selected_text"],
        "source_message_text": r["source_message_text"] or "",
        "context_node_id": r["context_node_id"],
        "explanation": r["explanation"] or "",
        "mastery": r["mastery"] or "unknown",
        "pos_x": float(r["pos_x"] or 0),
        "pos_y": float(r["pos_y"] or 0),
        "collapsed": bool(r["collapsed"]),
        "conversation": json.loads(r["conversation"]) if r.get("conversation") else [],
        "width": float(r["width"]) if r.get("width") else None,
        "height": float(r["height"]) if r.get("height") else None,
        "char_start": int(r["char_start"]) if r.get("char_start") is not None else None,
        "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
        "updated_at": r["updated_at"].isoformat() if hasattr(r["updated_at"], "isoformat") else str(r["updated_at"]),
    }


# ── 工具：获取所有子孙卡片 ID ──

def _get_descendant_ids(card_id: str) -> list[str]:
    """递归获取所有子孙卡片 ID"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT id FROM explain_cards WHERE parent_card_id = %s",
        (card_id,),
    )
    ids = [r["id"] for r in rows]
    for cid in ids:
        ids.extend(_get_descendant_ids(cid))
    return ids


# ════════════════════════════════════════
#  API
# ════════════════════════════════════════


@router.get("", summary="获取对话的解释卡片列表")
async def list_cards(
    conversation_id: str = Query(...),
    user_id: str = Query(default=None),
):
    """获取指定对话的所有解释卡片（含 explanation 缓存），按 created_at 升序"""
    _ensure_table()
    uid = get_user_id(user_id)
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM explain_cards WHERE user_id = %s AND conversation_id = %s ORDER BY created_at ASC",
        (uid, conversation_id),
    )
    return [_row_to_dict(r) for r in rows]


@router.post("", summary="创建解释卡片")
async def create_card(body: dict, user_id: str = Query(default=None)):
    """
    创建解释卡片
    
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
    _ensure_table()
    uid = get_user_id(user_id)
    from app.infrastructure.db.database import get_db
    db = get_db()

    card_id = f"explain_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uid}"

    db.execute(
        """INSERT INTO explain_cards
           (id, user_id, conversation_id, message_id, depth, parent_card_id,
            selected_text, source_message_text, context_node_id, pos_x, pos_y, char_start, conversation)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            card_id,
            uid,
            body.get("conversation_id", ""),
            body.get("message_id", ""),
            int(body.get("depth", 1)),
            body.get("parent_card_id") or None,
            body.get("selected_text", ""),
            body.get("source_message_text", ""),
            body.get("context_node_id") or None,
            float(body.get("pos_x", 0)),
            float(body.get("pos_y", 0)),
            body.get("char_start") if body.get("char_start") is not None else None,
            json.dumps(body.get("conversation", [])),
        ),
    )
    logger.info("解释卡片已创建: %s (depth=%s, msg=%s)", card_id, body.get("depth"), body.get("message_id"))

    # 返回完整行
    row = db.fetchone("SELECT * FROM explain_cards WHERE id = %s", (card_id,))
    return _row_to_dict(row)


@router.patch("/{card_id}", summary="更新解释卡片")
async def update_card(card_id: str, body: dict, user_id: str = Query(default=None)):
    """更新解释卡片字段（explanation, mastery, pos_x, pos_y, collapsed 等）"""
    _ensure_table()
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 检查是否存在
    existing = db.fetchone("SELECT id FROM explain_cards WHERE id = %s", (card_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="解释卡片不存在")

    updatable = {
        "explanation": str,
        "mastery": str,
        "pos_x": float,
        "pos_y": float,
        "collapsed": bool,
        "conversation": lambda v: json.dumps(v) if isinstance(v, list) else str(v),
        "width": float,
        "height": float,
    }

    updates: list[str] = []
    params: list[Any] = []

    for field, cast in updatable.items():
        if field in body:
            val = cast(body[field])
            if field == "collapsed":
                updates.append(f"collapsed = %s::int")
                params.append(1 if val else 0)
            else:
                updates.append(f"{field} = %s")
                params.append(val)

    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    updates.append("updated_at = NOW()")
    params.append(card_id)

    db.execute(f"UPDATE explain_cards SET {', '.join(updates)} WHERE id = %s", tuple(params))
    logger.info("解释卡片已更新: %s (fields=%s)", card_id, [f.split("=")[0].strip() for f in updates[:-1]])

    # 返回更新后的完整行
    row = db.fetchone("SELECT * FROM explain_cards WHERE id = %s", (card_id,))
    return _row_to_dict(row)


@router.delete("/{card_id}", summary="删除解释卡片及子孙")
async def delete_card(card_id: str, user_id: str = Query(default=None)):
    """级联删除指定卡片及其所有子孙卡片"""
    _ensure_table()
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 收集所有要删除的 ID
    all_ids = [card_id] + _get_descendant_ids(card_id)

    placeholders = ", ".join(f"%s" for _ in all_ids)
    db.execute(f"DELETE FROM explain_cards WHERE id IN ({placeholders})", tuple(all_ids))

    logger.info("解释卡片已删除（含子孙）: %s (共 %d 张)", card_id, len(all_ids))
    return {"deleted": card_id, "cascade_count": len(all_ids), "ids": all_ids}
