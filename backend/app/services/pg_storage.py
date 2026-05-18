"""
PostgreSQL 对话存储引擎 (v3.0)

替代 JSON 文件存储，线程安全 + 连接池。
与 StorageEngine 接口兼容。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from app.db.database import Database
from app.schemas.conversation import (
    UserData,
    Partition,
    Branch,
    TreeNode,
    ResponseBlock,
    LinkNode,
    ContentBlock,
    FileRecord,
)
from pydantic import TypeAdapter

logger = logging.getLogger(__name__)

# SQL  schema 路径
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "conversation_schema.sql"


class PgStorageEngine:
    """PostgreSQL 存储引擎，与 StorageEngine 接口兼容"""

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_schema(self) -> None:
        """初始化表结构（幂等）"""
        if self._initialized:
            return
        db = Database.get()
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH) as f:
                sql = f.read()
            db.execute(sql)
        self._initialized = True

    # ── 读取 ──

    def load(self, user_id: str) -> UserData:
        """从 PG 加载完整用户数据"""
        self._ensure_schema()
        db = Database.get()

        # 加载用户元数据
        meta = db.fetchone(
            "SELECT * FROM conversation_user_meta WHERE user_id = %s",
            (user_id,),
        )
        if not meta:
            return UserData(user_id=user_id)

        # 加载分区
        partitions = {}
        part_rows = db.fetchall(
            "SELECT * FROM conversation_partitions WHERE user_id = %s",
            (user_id,),
        )
        for r in part_rows:
            r = dict(r)
            r["summary_branches"] = r.get("summary_branches") or {}
            partitions[r["id"]] = Partition(**r)

        # 加载分支
        branches = {}
        branch_rows = db.fetchall(
            "SELECT * FROM conversation_branches WHERE partition_id = ANY(%s)",
            ([p["id"] for p in part_rows],),
        )
        for r in branch_rows:
            r = dict(r)
            branches[r["id"]] = Branch(**r)

        # 加载节点
        nodes = {}
        all_part_ids = list(partitions.keys())
        if all_part_ids:
            node_rows = db.fetchall(
                "SELECT * FROM conversation_nodes WHERE partition_id = ANY(%s)",
                (all_part_ids,),
            )
            for r in node_rows:
                r = dict(r)
                # 反序列化 content_blocks (Union类型)
                raw_cb = r.get("content_blocks", [])
                if isinstance(raw_cb, str):
                    raw_cb = json.loads(raw_cb)
                adapter = TypeAdapter(list[ContentBlock])  # type: ignore
                r["content_blocks"] = adapter.validate_python(raw_cb)
                nodes[r["id"]] = TreeNode(**r)

        # 加载响应块
        response_blocks = {}
        if all_part_ids:
            rb_rows = db.fetchall(
                "SELECT * FROM conversation_response_blocks WHERE partition_id = ANY(%s)",
                (all_part_ids,),
            )
            for r in rb_rows:
                r = dict(r)
                response_blocks[r["id"]] = ResponseBlock(**r)

        # 加载链接节点
        link_nodes = {}
        if all_part_ids:
            ln_rows = db.fetchall(
                "SELECT * FROM conversation_link_nodes WHERE source_partition_id = ANY(%s)",
                (all_part_ids,),
            )
            for r in ln_rows:
                r = dict(r)
                link_nodes[r["id"]] = LinkNode(**r)

        return UserData(
            user_id=user_id,
            role=meta.get("role", "student"),
            org_id=meta.get("org_id"),
            partitions=partitions,
            branches=branches,
            nodes=nodes,
            link_nodes=link_nodes,
            active_partition_id=meta.get("active_partition_id"),
            response_blocks=response_blocks,
        )

    # ── 保存 ──

    def save(self, user_id: str, data: UserData) -> None:
        """保存完整用户数据到 PG（差分写入）"""
        self._ensure_schema()
        db = Database.get()

        # 保存/更新用户元数据
        db.execute(
            """
            INSERT INTO conversation_user_meta (user_id, role, org_id, active_partition_id, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                role = EXCLUDED.role,
                org_id = EXCLUDED.org_id,
                active_partition_id = EXCLUDED.active_partition_id
            """,
            (user_id, data.role, data.org_id, data.active_partition_id, time.time()),
        )

        # 保存分区
        for p in data.partitions.values():
            db.execute(
                """
                INSERT INTO conversation_partitions
                    (id, user_id, name, subject, direction, emoji, color, root_id,
                     active_branch_id, context_summary, summary_branches, tags,
                     created_at, updated_at, last_active_at, message_count, total_tokens)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, subject=EXCLUDED.subject,
                    active_branch_id=EXCLUDED.active_branch_id,
                    context_summary=EXCLUDED.context_summary,
                    summary_branches=EXCLUDED.summary_branches,
                    updated_at=EXCLUDED.updated_at,
                    last_active_at=EXCLUDED.last_active_at,
                    message_count=EXCLUDED.message_count,
                    total_tokens=EXCLUDED.total_tokens
                """,
                (
                    p.id, user_id, p.name, p.subject, p.direction,
                    p.emoji, p.color, p.root_id,
                    p.active_branch_id, p.context_summary,
                    json.dumps(p.summary_branches, ensure_ascii=False),
                    p.tags, p.created_at, p.updated_at, p.last_active_at,
                    p.message_count, p.total_tokens,
                ),
            )

        # 保存分支
        for b in data.branches.values():
            db.execute(
                """
                INSERT INTO conversation_branches
                    (id, partition_id, name, fork_point_id, path, is_active,
                     is_archived, summary, summary_dirty, practice_sessions,
                     practice_summary, created_at, last_message_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, is_active=EXCLUDED.is_active,
                    summary=EXCLUDED.summary,
                    practice_sessions=EXCLUDED.practice_sessions,
                    practice_summary=EXCLUDED.practice_summary,
                    last_message_at=EXCLUDED.last_message_at
                """,
                (
                    b.id, b.partition_id, b.name, b.fork_point_id,
                    b.path, b.is_active, b.is_archived, b.summary,
                    b.summary_dirty, b.practice_sessions, b.practice_summary,
                    b.created_at, b.last_message_at,
                ),
            )

        # 保存节点
        cb_adapter = TypeAdapter(list[ContentBlock])  # type: ignore
        for n in data.nodes.values():
            cb_json = json.dumps(
                cb_adapter.dump_python(n.content_blocks),
                ensure_ascii=False,
            )
            db.execute(
                """
                INSERT INTO conversation_nodes
                    (id, parent_id, children_ids, partition_id, branch_id,
                     content_blocks, text_summary, summary, role, timestamp,
                     token_count, is_deleted, is_archived, has_modified_version,
                     links_to, linked_from, metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    content_blocks=EXCLUDED.content_blocks,
                    text_summary=EXCLUDED.text_summary,
                    summary=EXCLUDED.summary,
                    is_deleted=EXCLUDED.is_deleted,
                    has_modified_version=EXCLUDED.has_modified_version,
                    metadata=EXCLUDED.metadata
                """,
                (
                    n.id, n.parent_id, n.children_ids, n.partition_id,
                    n.branch_id, cb_json, n.text_summary, n.summary, n.role,
                    n.timestamp, n.token_count, n.is_deleted, n.is_archived,
                    n.has_modified_version, n.links_to, n.linked_from,
                    json.dumps(getattr(n, 'metadata', {}), ensure_ascii=False),
                ),
            )

        # 保存响应块
        for rb in data.response_blocks.values():
            db.execute(
                """
                INSERT INTO conversation_response_blocks
                    (id, message_id, partition_id, branch_id, type, status,
                     content, "order", sources, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    status=EXCLUDED.status,
                    content=EXCLUDED.content,
                    sources=EXCLUDED.sources,
                    updated_at=EXCLUDED.updated_at
                """,
                (
                    rb.id, rb.message_id, rb.partition_id, rb.branch_id,
                    rb.type, rb.status, json.dumps(rb.content, ensure_ascii=False),
                    rb.order, rb.sources or [], rb.created_at, rb.updated_at,
                ),
            )

        # 保存链接节点
        for ln in data.link_nodes.values():
            db.execute(
                """
                INSERT INTO conversation_link_nodes
                    (id, target_message_id, target_partition_id, target_branch_id,
                     source_partition_id, source_branch_id, preview_summary, timestamp)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    ln.id, ln.target_message_id, ln.target_partition_id,
                    ln.target_branch_id, ln.source_partition_id,
                    ln.source_branch_id, ln.preview_summary, ln.timestamp,
                ),
            )

        logger.info("Conversation data saved for user %s", user_id)

    # ── 迁移：JSON → PG ──

    def migrate_from_json(self, user_id: str, json_path: Path) -> None:
        """从 JSON 文件迁移数据到 PG"""
        if not json_path.exists():
            logger.warning("JSON file not found: %s", json_path)
            return

        with open(json_path, "r", encoding="utf-8") as f:
            data = UserData.model_validate_json(f.read())

        self.save(user_id, data)
        logger.info("Migrated %s from JSON to PG", user_id)


# 全局单例
pg_storage = PgStorageEngine()
