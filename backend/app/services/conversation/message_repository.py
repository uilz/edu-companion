"""
消息仓储 (messages 独立表)

取代 conversation_user_meta.nodes JSONB，消息持久化到 messages 关系表。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.schemas.directory_node import MessageNode

logger = logging.getLogger(__name__)


class MessageRepository:
    """消息持久化仓储 — 读写 messages 表"""

    def __init__(self):
        from app.infrastructure.db.database import get_db
        self._db = get_db()

    def ensure_table(self) -> None:
        """确保 messages 表存在（幂等）"""
        # 开发阶段：旧表 schema 落后时直接重建
        self._db.execute("""
            DO $$
            DECLARE
                col_exists boolean;
            BEGIN
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'messages' AND column_name = 'conv_id'
                ) INTO col_exists;
                IF NOT col_exists THEN
                    DROP TABLE IF EXISTS messages CASCADE;
                END IF;
            END $$;
        """)
        # 清理旧 schema 遗留的 conversation_id 列（远端 VM 有此列导致 NotNullViolation）
        self._db.execute("ALTER TABLE messages DROP COLUMN IF EXISTS conversation_id")

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id                  TEXT PRIMARY KEY,
                user_id             TEXT NOT NULL,
                conv_id     TEXT NOT NULL,
                role                TEXT NOT NULL,
                content             TEXT DEFAULT '',
                content_blocks      JSONB DEFAULT '[]',
                text_summary        TEXT DEFAULT '',
                knowledge_node_ids  JSONB DEFAULT '[]',
                parent_id           TEXT,
                children_ids        JSONB DEFAULT '[]',
                has_sub_branches    BOOLEAN DEFAULT FALSE,
                sub_branch_ids      JSONB DEFAULT '[]',
                sub_branch_summaries JSONB DEFAULT '[]',
                timestamp           TIMESTAMPTZ DEFAULT NOW(),
                token_count         INTEGER DEFAULT 0,
                version             INTEGER DEFAULT 1,
                is_deleted          BOOLEAN DEFAULT FALSE,
                agent_label         TEXT DEFAULT '',
                metadata            JSONB DEFAULT '{}'
            )
        """)
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_conversation ON messages(conv_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_user ON messages(user_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_parent ON messages(parent_id)"
        )

    # ── 装载全部 ──

    def load_all(self, user_id: str) -> dict[str, MessageNode]:
        """装载用户所有消息 → dict[str, MessageNode]"""
        self.ensure_table()
        rows = self._db.fetchall(
            "SELECT * FROM messages WHERE user_id = %s AND is_deleted = FALSE",
            (user_id,),
        )
        result: dict[str, MessageNode] = {}
        for row in rows:
            node = self._row_to_node(row)
            if node:
                result[node.id] = node
        return result

    def load_by_directory(self, user_id: str, directory_id: str) -> dict[str, MessageNode]:
        """装载某个目录下的所有消息"""
        self.ensure_table()
        rows = self._db.fetchall(
            "SELECT * FROM messages WHERE user_id = %s AND conv_id = %s AND is_deleted = FALSE",
            (user_id, directory_id),
        )
        result: dict[str, MessageNode] = {}
        for row in rows:
            node = self._row_to_node(row)
            if node:
                result[node.id] = node
        return result

    # ── 单条 CRUD ──

    def get(self, message_id: str) -> Optional[MessageNode]:
        """获取单条消息"""
        self.ensure_table()
        row = self._db.fetchone(
            "SELECT * FROM messages WHERE id = %s",
            (message_id,),
        )
        return self._row_to_node(row) if row else None

    def insert(self, node: MessageNode, user_id: str) -> None:
        """插入新消息"""
        self.ensure_table()
        self._db.execute(
            """INSERT INTO messages (id, user_id, conv_id, role, content,
               content_blocks, text_summary, knowledge_node_ids, parent_id, children_ids,
               has_sub_branches, sub_branch_ids, sub_branch_summaries,
               timestamp, token_count, version, is_deleted, agent_label, metadata)
               VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s,%s)""",
            self._node_to_params(node, user_id),
        )

    def update(self, node: MessageNode, user_id: str) -> None:
        """更新消息（upsert）"""
        self.ensure_table()
        self._db.execute(
            """INSERT INTO messages (id, user_id, conv_id, role, content,
               content_blocks, text_summary, knowledge_node_ids, parent_id, children_ids,
               has_sub_branches, sub_branch_ids, sub_branch_summaries,
               timestamp, token_count, version, is_deleted, agent_label, metadata)
               VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET
                   conv_id = EXCLUDED.conv_id,
                   role = EXCLUDED.role,
                   content = EXCLUDED.content,
                   content_blocks = EXCLUDED.content_blocks,
                   text_summary = EXCLUDED.text_summary,
                   knowledge_node_ids = EXCLUDED.knowledge_node_ids,
                   parent_id = EXCLUDED.parent_id,
                   children_ids = EXCLUDED.children_ids,
                   has_sub_branches = EXCLUDED.has_sub_branches,
                   sub_branch_ids = EXCLUDED.sub_branch_ids,
                   sub_branch_summaries = EXCLUDED.sub_branch_summaries,
                   timestamp = EXCLUDED.timestamp,
                   token_count = EXCLUDED.token_count,
                   version = EXCLUDED.version,
                   is_deleted = EXCLUDED.is_deleted,
                   agent_label = EXCLUDED.agent_label,
                   metadata = EXCLUDED.metadata""",
            self._node_to_params(node, user_id),
        )

    def delete(self, message_id: str) -> None:
        """软删除消息"""
        self._db.execute(
            "UPDATE messages SET is_deleted = TRUE WHERE id = %s",
            (message_id,),
        )

    def hard_delete(self, message_id: str) -> None:
        """硬删除消息"""
        self._db.execute(
            "DELETE FROM messages WHERE id = %s",
            (message_id,),
        )

    def delete_by_directory(self, directory_id: str) -> None:
        """删除目录下所有消息"""
        self._db.execute(
            "DELETE FROM messages WHERE conv_id = %s",
            (directory_id,),
        )

    # ── 批量操作 ──

    def save_all(self, user_id: str, nodes: dict[str, MessageNode]) -> None:
        """全量同步内存中的消息到 DB（upsert 批量）"""
        self.ensure_table()
        if not nodes:
            return
        ops = []
        for node in nodes.values():
            params = self._node_to_params(node, user_id)
            ops.append((
                """INSERT INTO messages (id, user_id, conv_id, role, content,
                   content_blocks, text_summary, knowledge_node_ids, parent_id, children_ids,
                   has_sub_branches, sub_branch_ids, sub_branch_summaries,
                   timestamp, token_count, version, is_deleted, agent_label, metadata)
                   VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       conv_id = EXCLUDED.conv_id,
                       role = EXCLUDED.role,
                       content = EXCLUDED.content,
                       content_blocks = EXCLUDED.content_blocks,
                       text_summary = EXCLUDED.text_summary,
                       knowledge_node_ids = EXCLUDED.knowledge_node_ids,
                       parent_id = EXCLUDED.parent_id,
                       children_ids = EXCLUDED.children_ids,
                       has_sub_branches = EXCLUDED.has_sub_branches,
                       sub_branch_ids = EXCLUDED.sub_branch_ids,
                       sub_branch_summaries = EXCLUDED.sub_branch_summaries,
                       timestamp = EXCLUDED.timestamp,
                       token_count = EXCLUDED.token_count,
                       version = EXCLUDED.version,
                       is_deleted = EXCLUDED.is_deleted,
                       agent_label = EXCLUDED.agent_label,
                       metadata = EXCLUDED.metadata""",
                params,
            ))
        self._db.execute_batch(ops)

    # ── 转换 ──

    @staticmethod
    def _row_to_node(row: dict) -> Optional[MessageNode]:
        """DB 行 → MessageNode"""
        if not row:
            return None
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}

        content_blocks = row.get("content_blocks") or []
        if isinstance(content_blocks, str):
            try:
                content_blocks = json.loads(content_blocks)
            except (json.JSONDecodeError, TypeError):
                content_blocks = []

        children_ids = row.get("children_ids") or []
        if isinstance(children_ids, str):
            try:
                children_ids = json.loads(children_ids)
            except (json.JSONDecodeError, TypeError):
                children_ids = []

        # DB column is conv_id, mapped to MessageNode.directory_id
        conv_id = row.get("conv_id", "")

        from datetime import datetime
        raw_ts = row.get("timestamp", 0)
        if isinstance(raw_ts, datetime):
            ts = raw_ts.timestamp()
        else:
            ts = raw_ts or 0

        return MessageNode(
            id=row["id"],
            directory_id=conv_id,
            parent_id=row.get("parent_id"),
            children_ids=children_ids,
            role=row.get("role", "user"),
            content=row.get("content", ""),
            content_blocks=content_blocks,
            text_summary=row.get("text_summary", ""),
            summary=meta.get("summary"),
            cross_partition=meta.get("cross_partition"),
            timestamp=ts,
            token_count=row.get("token_count", 0) or 0,
            version=row.get("version", 1) or 1,
            is_deleted=row.get("is_deleted", False) or False,
            is_archived=meta.get("is_archived", False),
            links_to=meta.get("links_to", []),
            linked_from=meta.get("linked_from", []),
            agent_label=row.get("agent_label", ""),
            has_sub_branches=row.get("has_sub_branches", meta.get("has_sub_branches", False)),
            sub_branch_ids=json.loads(row.get("sub_branch_ids", "[]")) if isinstance(row.get("sub_branch_ids"), str) else (row.get("sub_branch_ids") or meta.get("sub_branch_ids", [])),
            sub_branch_summaries=json.loads(row.get("sub_branch_summaries", "[]")) if isinstance(row.get("sub_branch_summaries"), str) else (row.get("sub_branch_summaries") or meta.get("sub_branch_summaries", [])),
            metadata=meta.get("metadata", {}),
        )

    @staticmethod
    def _node_to_params(node: MessageNode, user_id: str) -> tuple:
        """MessageNode → DB 参数元组"""
        meta = {
            "directory_id": node.directory_id,
            "summary": node.summary,
            "cross_partition": node.cross_partition,
            "is_archived": node.is_archived,
            "links_to": node.links_to,
            "linked_from": node.linked_from,
            "has_sub_branches": node.has_sub_branches,
            "sub_branch_ids": node.sub_branch_ids,
            "sub_branch_summaries": node.sub_branch_summaries,
            "metadata": node.metadata,
        }
        from datetime import datetime
        ts = datetime.fromtimestamp(node.timestamp) if isinstance(node.timestamp, (int, float)) else node.timestamp
        return (
            node.id,
            user_id,
            node.directory_id,  # stored as conv_id
            node.role,
            node.content,
            json.dumps(node.content_blocks, ensure_ascii=False),
            node.text_summary,
            json.dumps(meta.get("cognitive_node_ids", [])),  # knowledge_node_ids
            node.parent_id,
            json.dumps(node.children_ids, ensure_ascii=False),
            node.has_sub_branches,
            json.dumps(node.sub_branch_ids, ensure_ascii=False),
            json.dumps(node.sub_branch_summaries, ensure_ascii=False),
            ts,
            node.token_count,
            node.version,
            node.is_deleted,
            node.agent_label,
            json.dumps(meta, ensure_ascii=False),
        )


# ── 全局单例 ──

_msg_repo: Optional[MessageRepository] = None


def get_message_repo() -> MessageRepository:
    """获取 MessageRepository 单例"""
    global _msg_repo
    if _msg_repo is None:
        _msg_repo = MessageRepository()
    return _msg_repo


# ── 便捷函数 (D18: 通过 messages 表操作) ──

def update_message_cognitive(message_id: str, cognitive_node_ids: list[str], user_id: str) -> None:
    """更新消息的认知节点关联"""
    repo = get_message_repo()
    node = repo.get(message_id)
    if node:
        node.metadata["cognitive_node_ids"] = cognitive_node_ids
        repo.update(node, user_id)


def get_message_conv_id(message_id: str, user_id: str) -> str:
    """获取消息所属的 conv_id"""
    repo = get_message_repo()
    node = repo.get(message_id)
    if node:
        return node.directory_id
    return ""