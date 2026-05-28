"""ConversationNodeLink 存储层 — conversation_node_links 表 CRUD"""
from __future__ import annotations

import logging
from uuid import uuid4

from app.db.database import get_db

logger = logging.getLogger(__name__)


def upsert_link(
    conversation_id: str,
    node_id: str,
    is_primary: bool = False,
    added_by: str = "system",
) -> dict:
    """插入或更新一条会话-node 关联"""
    db = get_db()
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    lid = str(uuid4())
    db.execute("""
        INSERT INTO conversation_node_links
            (id, conversation_id, node_id, added_by, is_primary, added_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (conversation_id, node_id)
        DO UPDATE SET is_primary = EXCLUDED.is_primary
    """, (lid, conversation_id, node_id, added_by, is_primary, now_iso))
    return {"id": lid, "conversation_id": conversation_id, "node_id": node_id,
            "is_primary": is_primary, "added_by": added_by}


def get_links_for_conversation(conversation_id: str) -> list[dict]:
    """获取会话的所有关联 topic"""
    db = get_db()
    rows = db.fetchall(
        """SELECT l.*, n.label as node_label, n.path_id, n.level
           FROM conversation_node_links l
           LEFT JOIN cognitive_nodes n ON l.node_id = n.id
           WHERE l.conversation_id = %s
           ORDER BY l.is_primary DESC, l.added_at""",
        (conversation_id,),
    )
    return rows


def get_conversations_for_node(node_id: str) -> list[dict]:
    """获取关联到某节点的所有会话"""
    db = get_db()
    rows = db.fetchall(
        """SELECT l.*, c.title as conversation_title
           FROM conversation_node_links l
           LEFT JOIN conversations c ON l.conversation_id = c.id
           WHERE l.node_id = %s""",
        (node_id,),
    )
    return rows


def set_primary_link(conversation_id: str, link_id: str) -> None:
    """设某一关联为主归属（其他关联自动设非主）"""
    db = get_db()
    db.execute(
        "UPDATE conversation_node_links SET is_primary = false "
        "WHERE conversation_id = %s",
        (conversation_id,),
    )
    db.execute(
        "UPDATE conversation_node_links SET is_primary = true WHERE id = %s",
        (link_id,),
    )


def remove_link(link_id: str) -> bool:
    """移除关联，返回是否移除成功"""
    db = get_db()
    db.execute("DELETE FROM conversation_node_links WHERE id = %s", (link_id,))
    return True


def count_links_for_conversation(conversation_id: str) -> int:
    """统计会话的关联数"""
    db = get_db()
    row = db.fetchone(
        "SELECT COUNT(*) as cnt FROM conversation_node_links WHERE conversation_id = %s",
        (conversation_id,),
    )
    return row["cnt"] if row else 0
