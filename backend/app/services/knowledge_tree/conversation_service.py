"""
ConversationService — 会话 CRUD 服务

会话是连接导航树和知识树的独立实体。
"""
from __future__ import annotations
import json
import logging
import time
from typing import Optional
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.schemas.knowledge import Conversation as ConversationSchema

logger = logging.getLogger(__name__)


class ConversationService:
    """会话服务 — conversations 表 CRUD"""

    # ── CRUD ──

    def create_conversation(
        self, user_id: str, knowledge_node_ids: list[str] | None = None,
        summary_short: str = "",
    ) -> ConversationSchema:
        """创建新会话"""
        conv_id = f"conv_{uuid4().hex[:12]}"
        db = get_db()
        db.execute(
            """INSERT INTO conversations (id, user_id, knowledge_node_ids, summary_short, created_at, updated_at)
               VALUES (%s, %s, %s, %s, NOW(), NOW())""",
            (conv_id, user_id, json.dumps(knowledge_node_ids or []), summary_short),
        )
        return self.get_conversation(user_id, conv_id)

    def get_conversation(self, user_id: str, conv_id: str) -> Optional[ConversationSchema]:
        """获取会话"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM conversations WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            (conv_id, user_id),
        )
        return self._row_to_schema(row) if row else None

    def update_conversation(self, user_id: str, conv_id: str, **fields) -> Optional[ConversationSchema]:
        """更新会话字段"""
        db = get_db()
        allowed = {"summary_short", "summary_dirty", "knowledge_node_ids", "metadata"}
        updates = {}
        for k, v in fields.items():
            if k in allowed:
                if k == "knowledge_node_ids":
                    updates[k] = json.dumps(v)
                else:
                    updates[k] = v
        if not updates:
            return self.get_conversation(user_id, conv_id)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [conv_id, user_id]
        db.execute(
            f"UPDATE conversations SET {set_clause}, updated_at = NOW() WHERE id = %s AND user_id = %s",
            values,
        )
        return self.get_conversation(user_id, conv_id)

    def delete_conversation(self, user_id: str, conv_id: str) -> bool:
        """软删除会话"""
        db = get_db()
        db.execute(
            "UPDATE conversations SET deleted_at = NOW() WHERE id = %s AND user_id = %s",
            (conv_id, user_id),
        )
        return True

    def list_conversations(
        self, user_id: str, knowledge_node_id: str | None = None,
    ) -> list[ConversationSchema]:
        """列出会话。可选按知识点过滤。"""
        db = get_db()
        if knowledge_node_id:
            rows = db.fetchall(
                """SELECT * FROM conversations
                   WHERE user_id = %s AND deleted_at IS NULL
                   AND knowledge_node_ids @> %s::jsonb
                   ORDER BY updated_at DESC""",
                (user_id, json.dumps([knowledge_node_id])),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM conversations WHERE user_id = %s AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 100",
                (user_id,),
            )
        return [self._row_to_schema(r) for r in rows]

    def add_knowledge_node(self, user_id: str, conv_id: str, node_id: str) -> bool:
        """向会话添加知识点关联"""
        conv = self.get_conversation(user_id, conv_id)
        if not conv:
            return False
        if node_id in conv.knowledge_node_ids:
            return True
        conv.knowledge_node_ids.append(node_id)
        return self.update_conversation(user_id, conv_id, knowledge_node_ids=conv.knowledge_node_ids) is not None

    def remove_knowledge_node(self, user_id: str, conv_id: str, node_id: str) -> bool:
        """从会话移除知识点关联"""
        conv = self.get_conversation(user_id, conv_id)
        if not conv:
            return False
        conv.knowledge_node_ids = [n for n in conv.knowledge_node_ids if n != node_id]
        return self.update_conversation(user_id, conv_id, knowledge_node_ids=conv.knowledge_node_ids) is not None

    def add_message(self, user_id: str, conv_id: str, message_id: str) -> bool:
        """向会话追加消息 ID"""
        conv = self.get_conversation(user_id, conv_id)
        if not conv:
            return False
        if message_id in conv.message_ids:
            return True
        db = get_db()
        db.execute(
            "UPDATE conversations SET message_ids = message_ids || %s::jsonb, updated_at = NOW() WHERE id = %s AND user_id = %s",
            (json.dumps([message_id]), conv_id, user_id),
        )
        return True

    # ── 转换 ──

    def _row_to_schema(self, row: dict) -> ConversationSchema:
        def _json_list(raw):
            if raw is None:
                return []
            if isinstance(raw, list):
                return raw
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return []
            return []

        return ConversationSchema(
            id=row["id"],
            user_id=row["user_id"],
            message_ids=_json_list(row.get("message_ids")),
            knowledge_node_ids=_json_list(row.get("knowledge_node_ids")),
            summary_short=row.get("summary_short") or "",
            summary_dirty=row.get("summary_dirty", False),
            parent_conversation_id=row.get("parent_conversation_id") or "",
            sub_branch_ids=_json_list(row.get("sub_branch_ids")),
            depth=row.get("depth", 0),
            created_at=row["created_at"].timestamp() if hasattr(row["created_at"], "timestamp") else time.time(),
            updated_at=row["updated_at"].timestamp() if hasattr(row["updated_at"], "timestamp") else time.time(),
            metadata=json.loads(row.get("metadata", "{}")) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


conv_svc = ConversationService()