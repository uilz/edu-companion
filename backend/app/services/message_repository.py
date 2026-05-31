"""
MessageRepository — 消息写入封装（Phase 3, v6.md）

提供 messages 表的同步/异步写入接口。
所有消息（用户+AI，流式+非流式）最终经由此写入。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def save_message(
    user_id: str,
    message_id: str,
    conversation_id: str,
    role: str,
    content: str,
    content_blocks: list,
    summary: str = "",
    token_count: int = 0,
) -> None:
    """写入 messages 表（INSERT ON CONFLICT UPDATE）

    幂等：同一 message_id 重复调用会覆盖 content/content_blocks，用于流式更新。
    自动生成 embedding（异步后台任务）。
    """
    from app.cognitive.storage import get_db

    db = get_db()

    # 序列化 content_blocks（兼容 pydantic model 和原始 dict）
    if isinstance(content_blocks, list):
        if content_blocks and hasattr(content_blocks[0], "model_dump"):
            blocks_json = json.dumps([b.model_dump(mode="json") for b in content_blocks])
        elif content_blocks and hasattr(content_blocks[0], "dict"):
            blocks_json = json.dumps([b.dict() for b in content_blocks])
        else:
            blocks_json = json.dumps(content_blocks)
    else:
        blocks_json = content_blocks

    db.execute(
        """
        INSERT INTO messages (id, conversation_id, user_id, role, content, content_blocks, summary, token_count, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (id) DO UPDATE SET
            content = EXCLUDED.content,
            content_blocks = EXCLUDED.content_blocks,
            summary = EXCLUDED.summary,
            token_count = EXCLUDED.token_count
        """,
        (
            message_id,
            conversation_id,
            user_id,
            role,
            content,
            blocks_json,
            summary,
            token_count,
        ),
    )

    # 自动生成 embedding
    if content and len(content.strip()) > 5:
        try:
            from app.services.embedding_engine import compute_embedding
            emb = compute_embedding(content[:2000])
            if emb:
                db.execute(
                    "UPDATE messages SET embedding = %s::vector WHERE id = %s",
                    (emb, message_id),
                )
        except Exception:
            pass


def update_message_embedding(message_id: str, embedding: list[float]) -> None:
    """更新消息 embedding（异步生成后回填）"""
    from app.cognitive.storage import get_db

    db = get_db()
    db.execute(
        "UPDATE messages SET embedding = %s WHERE id = %s",
        (embedding, message_id),
    )


def update_message_cognitive(
    message_id: str,
    cognitive_node_ids: list[str],
    cognitive_annotations: Optional[list[dict]] = None,
) -> None:
    """更新消息的认知关联（分类确认后回写）"""
    from app.cognitive.storage import get_db

    db = get_db()
    if cognitive_annotations:
        db.execute(
            "UPDATE messages SET cognitive_node_ids = %s, cognitive_annotations = %s WHERE id = %s",
            (cognitive_node_ids, json.dumps(cognitive_annotations), message_id),
        )
    else:
        db.execute(
            "UPDATE messages SET cognitive_node_ids = %s WHERE id = %s",
            (cognitive_node_ids, message_id),
        )


def get_message_conversation_id(message_id: str) -> str | None:
    """获取消息所属的 conversation_id"""
    from app.cognitive.storage import get_db
    db = get_db()
    row = db.fetchone("SELECT conversation_id FROM messages WHERE id = %s", (message_id,))
    return row["conversation_id"] if row else None


def search_learning_memory(
    user_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """基于 embedding 余弦相似度检索历史消息

    需要 pgvector 扩展 + ivfflat 索引。
    降级：如果向量检索不可用，返回空列表。
    """
    from app.cognitive.storage import get_db

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
