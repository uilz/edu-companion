"""
MessageService — 消息 CRUD 服务

消息独立存储于 PG 表 messages。
"""
from __future__ import annotations
import json
import logging
import time
from typing import Optional
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.schemas.knowledge import Message as MessageSchema

logger = logging.getLogger(__name__)


class MessageService:
    """消息服务 — messages 表 CRUD"""

    def create_message(
        self, user_id: str, conversation_id: str, role: str,
        content: str = "", content_blocks: list[dict] | None = None,
        text_summary: str = "", parent_id: str | None = None,
        knowledge_node_ids: list[str] | None = None,
    ) -> MessageSchema:
        """创建消息"""
        msg_id = f"msg_{uuid4().hex[:12]}"
        db = get_db()
        db.execute(
            """INSERT INTO messages (id, user_id, conversation_id, role, content, content_blocks,
               text_summary, parent_id, knowledge_node_ids, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (
                msg_id, user_id, conversation_id, role, content,
                json.dumps(content_blocks or []), text_summary, parent_id,
                json.dumps(knowledge_node_ids or []),
            ),
        )
        # 更新父消息的 children_ids
        if parent_id:
            db.execute(
                """UPDATE messages SET children_ids = children_ids || %s::jsonb
                   WHERE id = %s AND user_id = %s
                   AND NOT (children_ids @> %s::jsonb)""",
                (json.dumps([msg_id]), parent_id, user_id, json.dumps([msg_id])),
            )
        return self.get_message(user_id, msg_id)

    def get_message(self, user_id: str, msg_id: str) -> Optional[MessageSchema]:
        """获取消息"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM messages WHERE id = %s AND user_id = %s AND is_deleted = false",
            (msg_id, user_id),
        )
        return self._row_to_schema(row) if row else None

    def update_message(self, user_id: str, msg_id: str, **fields) -> Optional[MessageSchema]:
        """更新消息"""
        db = get_db()
        allowed = {"content", "content_blocks", "text_summary", "knowledge_node_ids", "metadata"}
        updates = {}
        for k, v in fields.items():
            if k in allowed:
                if k in ("content_blocks", "knowledge_node_ids"):
                    updates[k] = json.dumps(v)
                else:
                    updates[k] = v
        if not updates:
            return self.get_message(user_id, msg_id)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [msg_id, user_id]
        db.execute(
            f"UPDATE messages SET {set_clause} WHERE id = %s AND user_id = %s",
            values,
        )
        return self.get_message(user_id, msg_id)

    def delete_message(self, user_id: str, msg_id: str) -> bool:
        """软删除消息 (级联删除子消息)"""
        msg = self.get_message(user_id, msg_id)
        if not msg:
            return False
        # 递归删除子消息
        for child_id in msg.children_ids:
            self.delete_message(user_id, child_id)
        db = get_db()
        db.execute(
            "UPDATE messages SET is_deleted = true WHERE id = %s AND user_id = %s",
            (msg_id, user_id),
        )
        return True

    def list_messages(
        self, user_id: str, conversation_id: str,
        limit: int = 50, offset: int = 0,
    ) -> list[MessageSchema]:
        """列出会话消息"""
        db = get_db()
        rows = db.fetchall(
            """SELECT * FROM messages
               WHERE user_id = %s AND conversation_id = %s AND is_deleted = false
               ORDER BY timestamp ASC LIMIT %s OFFSET %s""",
            (user_id, conversation_id, limit, offset),
        )
        return [self._row_to_schema(r) for r in rows]

    def get_message_tree(self, user_id: str, conversation_id: str) -> list[MessageSchema]:
        """获取会话的消息树 (按 parent_id 构建)"""
        messages = self.list_messages(user_id, conversation_id, limit=500)
        # 按树结构排序
        msg_map = {m.id: m for m in messages}
        root = [m for m in messages if m.parent_id is None or m.parent_id not in msg_map]
        result = []

        def dfs(node: MessageSchema):
            result.append(node)
            for child_id in node.children_ids:
                if child_id in msg_map:
                    dfs(msg_map[child_id])

        root.sort(key=lambda m: m.timestamp)
        for r in root:
            dfs(r)
        return result

    def add_knowledge_node(self, user_id: str, msg_id: str, node_id: str) -> bool:
        """向消息添加知识点关联"""
        msg = self.get_message(user_id, msg_id)
        if not msg:
            return False
        if node_id in msg.knowledge_node_ids:
            return True
        msg.knowledge_node_ids.append(node_id)
        return self.update_message(user_id, msg_id, knowledge_node_ids=msg.knowledge_node_ids) is not None

    def create_sub_branch(
        self, user_id: str, source_msg_id: str, child_conv_id: str,
        quoted_text: str = "",
    ) -> bool:
        """在源消息上标记子支"""
        msg = self.get_message(user_id, source_msg_id)
        if not msg:
            return False
        db = get_db()
        if child_conv_id not in msg.sub_branch_ids:
            msg.sub_branch_ids.append(child_conv_id)
        db.execute(
            "UPDATE messages SET has_sub_branches = true, sub_branch_ids = %s, "
            "sub_branch_summaries = sub_branch_summaries || %s::jsonb WHERE id = %s AND user_id = %s",
            (
                json.dumps(msg.sub_branch_ids),
                json.dumps([{"conversation_id": child_conv_id, "quoted_text": quoted_text, "summary": ""}]),
                source_msg_id, user_id,
            ),
        )
        return True

    # ── 转换 ──

    def _row_to_schema(self, row: dict) -> MessageSchema:
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

        def _ts(raw) -> float:
            if raw is None:
                return time.time()
            if isinstance(raw, (int, float)):
                return float(raw)
            if hasattr(raw, "timestamp"):
                return raw.timestamp()
            return time.time()

        return MessageSchema(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row.get("role", "user"),
            content=row.get("content") or "",
            content_blocks=_json_list(row.get("content_blocks")),
            text_summary=row.get("text_summary") or "",
            knowledge_node_ids=_json_list(row.get("knowledge_node_ids")),
            parent_id=row.get("parent_id"),
            children_ids=_json_list(row.get("children_ids")),
            has_sub_branches=row.get("has_sub_branches", False),
            sub_branch_ids=_json_list(row.get("sub_branch_ids")),
            sub_branch_summaries=_json_list(row.get("sub_branch_summaries")),
            version=row.get("version", 1),
            is_deleted=row.get("is_deleted", False),
            timestamp=_ts(row.get("timestamp")),
            token_count=row.get("token_count", 0),
            agent_label=row.get("agent_label") or "",
            metadata=json.loads(row.get("metadata", "{}")) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


msg_svc = MessageService()