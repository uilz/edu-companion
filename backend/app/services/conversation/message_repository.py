"""
Message Repository — 消息索引层（v5.0）

消息主存储已迁移到 UserData.nodes。
本模块仅提供：
1. 认知标注更新 → 写入 UserData.nodes[node_id].metadata
2. 消息所属会话查询 → 来自 UserData.nodes
3. 向量语义搜索 → 基于 messages 表（异步同步的只读索引）
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def update_message_cognitive(
    message_id: str,
    cognitive_node_ids: list[str],
    cognitive_annotations: Optional[list[dict]] = None,
) -> None:
    """更新消息的认知关联，写入 UserData.nodes.metadata

    替代旧版直接写 messages 表的方式。
    """
    from app.services.common import get_data_repo
    from shared.constants import DEFAULT_USER_ID

    data = get_data_repo().load(DEFAULT_USER_ID)
    node = data.nodes.get(message_id)
    if not node:
        logger.warning("消息 %s 不存在于 UserData.nodes", message_id)
        return

    meta = node.metadata or {}
    meta["cognitive_node_ids"] = cognitive_node_ids
    if cognitive_annotations:
        meta["cognitive_annotations"] = cognitive_annotations
    node.metadata = meta

    data.nodes[message_id] = node
    get_data_repo().save(DEFAULT_USER_ID, data)
    logger.debug("认知标注已更新到 node %s: %s", message_id, cognitive_node_ids)


def get_message_conversation_id(message_id: str) -> str | None:
    """获取消息所属的 conversation_id，来自 UserData.nodes"""
    from app.services.common import get_data_repo
    from shared.constants import DEFAULT_USER_ID

    data = get_data_repo().load(DEFAULT_USER_ID)
    node = data.nodes.get(message_id)
    if not node:
        return None
    return node.conversation_id or None


def search_learning_memory(
    user_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """基于 embedding 余弦相似度检索历史消息

    依赖 messages 表（异步同步的只读向量索引）。
    需要 pgvector 扩展 + ivfflat 索引。
    降级：如果向量检索不可用，返回空列表。
    """
    from app.db.database import get_db

    db = get_db()
    try:
        rows = db.fetchall(
            """
            SELECT id, content, summary, cognitive_node_ids, role, created_at,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM messages
            WHERE user_id = %s AND role = 'assistant' AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, user_id, query_embedding, top_k),
        )
        return [
            {
                "id": r["id"],
                "content": r["content"],
                "summary": r["summary"],
                "cognitive_node_ids": r.get("cognitive_node_ids", []),
                "role": r["role"],
                "similarity": float(r["similarity"]) if r.get("similarity") else 0,
                "created_at": r.get("created_at"),
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("向量检索不可用: %s", e)
        return []
