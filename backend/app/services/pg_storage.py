"""
PostgreSQL 对话存储引擎 (v4.2 — Phase 6.5)

全字段 UserData 持久化，与 JSON 引擎接口兼容。
处理 v4 结构：Conversation 替代 Branch, 支持 domains/topics/files/background_jobs。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from app.db.database import Database
from app.schemas.conversation import (
    UserData, Partition, Conversation, TreeNode,
    ResponseBlock, LinkNode, ContentBlock, Domain, Topic, FileRecord,
    BackgroundJob, KnowledgeGraph,
)
from pydantic import TypeAdapter

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "conversation_schema.sql"


class PgStorageEngine:
    """PostgreSQL 存储引擎，v4.2 全字段兼容"""

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        db = Database.get()
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH) as f:
                sql = f.read()
            db.execute(sql)
        self._initialized = True

    # ── JSON 序列化辅助 ──

    @staticmethod
    def _j(obj) -> str:
        """安全 JSON 序列化"""
        if obj is None:
            return "{}"
        if isinstance(obj, (list, dict)):
            return json.dumps(obj, ensure_ascii=False, default=str)
        return str(obj)

    @staticmethod
    def _parse_json(raw, default=None):
        """JSON 字符串 → Python 对象，处理 None/空"""
        if raw is None or raw == "" or raw == {} or raw == []:
            return default if default is not None else {}
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else {}

    # ── ETag 支持 ──

    _etag_cache: dict[str, str] = {}

    def get_etag(self, user_id: str) -> str:
        """返回当前用户数据的 ETag (基于最新时间戳)"""
        db = Database.get()
        row = db.fetchone(
            "SELECT updated_at FROM conversation_user_meta WHERE user_id = %s",
            (user_id,),
        )
        ts = row["updated_at"] if row else "0"
        etag = f'W/"{user_id}:{ts}"'
        self._etag_cache[user_id] = etag
        return etag

    # ── 读取 ──

    def load(self, user_id: str) -> UserData:
        """从 PG 加载完整用户数据 (v4.2)"""
        self._ensure_schema()
        db = Database.get()

        meta = db.fetchone(
            "SELECT * FROM conversation_user_meta WHERE user_id = %s",
            (user_id,),
        )

        # ── 从 meta 读取所有 JSONB 字段 ──
        domains = {}
        topics = {}
        files = {}
        background_jobs = {}
        knowledge_states = {}
        practice_sessions = {}
        error_book = {}
        event_log = []
        knowledge_graphs = {}
        active_partition_id = None
        role = "student"
        org_id = None

        if meta:
            role = meta.get("role", "student")
            org_id = meta.get("org_id")
            active_partition_id = meta.get("active_partition_id")

            raw_domains = self._parse_json(meta.get("domains", {}))
            domains = {k: Domain(**v) for k, v in raw_domains.items() if isinstance(v, dict)}

            raw_topics = self._parse_json(meta.get("topics", {}))
            topics = {k: Topic(**v) for k, v in raw_topics.items() if isinstance(v, dict)}

            raw_files = self._parse_json(meta.get("files", {}), {})
            files = {}
            if isinstance(raw_files, dict):
                files = {k: FileRecord(**v) for k, v in raw_files.items() if isinstance(v, dict)}

            raw_jobs = self._parse_json(meta.get("background_jobs", {}), {})
            background_jobs = {}
            if isinstance(raw_jobs, dict):
                background_jobs = {k: BackgroundJob(**v) for k, v in raw_jobs.items() if isinstance(v, dict)}

            knowledge_states = self._parse_json(meta.get("knowledge_states", {}), {})
            practice_sessions = self._parse_json(meta.get("practice_sessions", {}), {})
            error_book = self._parse_json(meta.get("error_book", {}), {})
            event_log = self._parse_json(meta.get("event_log", []), [])

            raw_kg = self._parse_json(meta.get("knowledge_graphs", {}))
            knowledge_graphs = {}
            for pid, kg_data in raw_kg.items():
                if isinstance(kg_data, dict):
                    try:
                        knowledge_graphs[pid] = KnowledgeGraph.model_validate(kg_data)
                    except Exception as e:
                        logger.warning(f"跳过损坏的知识图谱 {pid}: {e}")

        # ── 加载分区 ──
        partitions = {}
        part_rows = db.fetchall(
            "SELECT * FROM conversation_partitions WHERE user_id = %s",
            (user_id,),
        )
        for r in part_rows:
            r = dict(r)
            # v4 Partition doesn't have active_branch_id/summary_branches
            r.pop("active_branch_id", None)
            r["tags"] = r.get("tags") or []
            partitions[r["id"]] = Partition(**r)

        # ── 加载对话 (v4 Conversation — 通过 topic_id 关联) ──
        conversations = {}
        all_part_ids = list(partitions.keys())
        all_topic_ids = list(topics.keys())
        search_ids = all_part_ids + all_topic_ids
        if search_ids:
            conv_rows = db.fetchall(
                "SELECT * FROM conversation_branches WHERE partition_id = ANY(%s)",
                (search_ids,),
            )
            for r in conv_rows:
                r = dict(r)
                # topic_id 列优先；无 topic_id 时 fallback 兼容旧数据
                r["topic_id"] = r.pop("topic_id", "") or r.pop("partition_id", "")
                r["path"] = r.get("path") or []
                conversations[r["id"]] = Conversation(**r)

        # ── 加载消息节点 ──
        nodes = {}
        search_ids = all_part_ids + all_topic_ids
        if search_ids:
            node_rows = db.fetchall(
                "SELECT * FROM conversation_nodes WHERE partition_id = ANY(%s)",
                (search_ids,),
            )
            for r in node_rows:
                r = dict(r)
                raw_cb = self._parse_json(r.get("content_blocks"), [])
                try:
                    adapter = TypeAdapter(list[ContentBlock])
                    r["content_blocks"] = adapter.validate_python(raw_cb)
                except Exception:
                    r["content_blocks"] = []
                r["children_ids"] = r.get("children_ids") or []
                r["links_to"] = r.get("links_to") or []
                r["linked_from"] = r.get("linked_from") or []
                r["conversation_id"] = r.pop("branch_id", "")  # table branch_id → v4 conversation_id
                nodes[r["id"]] = TreeNode(**r)

        # ── 加载响应块 ──
        response_blocks = {}
        if search_ids:
            rb_rows = db.fetchall(
                "SELECT * FROM conversation_response_blocks WHERE partition_id = ANY(%s)",
                (search_ids,),
            )
            for r in rb_rows:
                r = dict(r)
                r.setdefault("conversation_id", r.pop("branch_id", ""))
                r["content"] = self._parse_json(r.get("content"), {})
                response_blocks[r["id"]] = ResponseBlock(**r)

        # ── 加载链接节点 ──
        link_nodes = {}
        if search_ids:
            ln_rows = db.fetchall(
                "SELECT * FROM conversation_link_nodes WHERE source_partition_id = ANY(%s)",
                (search_ids,),
            )
            for r in ln_rows:
                r = dict(r)
                r.setdefault("source_conversation_id", r.pop("source_branch_id", ""))
                r.setdefault("target_conversation_id", r.pop("target_branch_id", ""))
                link_nodes[r["id"]] = LinkNode(**r)

        return UserData(
            user_id=user_id,
            role=role,
            org_id=org_id,
            partitions=partitions,
            domains=domains,
            topics=topics,
            conversations=conversations,
            nodes=nodes,
            link_nodes=link_nodes,
            files=files,
            active_partition_id=active_partition_id,
            response_blocks=response_blocks,
            background_jobs=background_jobs,
            knowledge_states=knowledge_states,
            practice_sessions=practice_sessions,
            error_book=error_book,
            knowledge_graphs=knowledge_graphs,
            event_log=event_log,
        )

    # ── 保存 ──

    def save(self, user_id: str, data: UserData) -> None:
        """保存完整用户数据到 PG (v4.2 全字段)"""
        self._ensure_schema()
        db = Database.get()

        # ── 用户元数据 ──
        db.execute(
            """
            INSERT INTO conversation_user_meta
                (user_id, role, org_id, active_partition_id,
                 knowledge_graphs, knowledge_states, practice_sessions,
                 error_book, event_log, domains, topics, files,
                 background_jobs, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
                role = EXCLUDED.role,
                org_id = EXCLUDED.org_id,
                active_partition_id = EXCLUDED.active_partition_id,
                knowledge_graphs = EXCLUDED.knowledge_graphs,
                knowledge_states = EXCLUDED.knowledge_states,
                practice_sessions = EXCLUDED.practice_sessions,
                error_book = EXCLUDED.error_book,
                event_log = EXCLUDED.event_log,
                domains = EXCLUDED.domains,
                topics = EXCLUDED.topics,
                files = EXCLUDED.files,
                background_jobs = EXCLUDED.background_jobs
            """,
            (
                user_id,
                data.role,
                data.org_id,
                data.active_partition_id,
                self._j({k: v.model_dump() for k, v in data.knowledge_graphs.items()}),
                self._j(data.knowledge_states),
                self._j(data.practice_sessions),
                self._j(data.error_book),
                self._j(data.event_log),
                self._j({k: v.model_dump() for k, v in data.domains.items()}),
                self._j({k: v.model_dump() for k, v in data.topics.items()}),
                self._j({k: v.model_dump() for k, v in data.files.items()}),
                self._j({k: v.model_dump() for k, v in data.background_jobs.items()}),
                time.time(),
            ),
        )

        # ── 分区 ──
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
                    context_summary=EXCLUDED.context_summary,
                    updated_at=EXCLUDED.updated_at,
                    last_active_at=EXCLUDED.last_active_at,
                    message_count=EXCLUDED.message_count,
                    total_tokens=EXCLUDED.total_tokens
                """,
                (
                    p.id, user_id, p.name, p.subject, p.direction,
                    p.emoji, p.color, p.root_id,
                    "",  # active_branch_id (deprecated in v4)
                    p.context_summary,
                    self._j({}),  # summary_branches (deprecated in v4)
                    p.tags or [], p.created_at, p.updated_at, p.last_active_at,
                    p.message_count, p.total_tokens,
                ),
            )

        # ── 对话 (v4 Conversation → conversation_branches 表) ──
        for b in data.conversations.values():
            # 从 Topic → Domain → Partition 追溯真实的 partition_id (FK 约束)
            partition_id_for_table = None
            topic = data.topics.get(b.topic_id)
            if topic:
                domain = data.domains.get(topic.domain_id)
                if domain:
                    partition_id_for_table = domain.partition_id
            if not partition_id_for_table:
                # fallback: 如果找不到，尝试用 b.topic_id 本身作为 partition_id
                # （兼容旧数据或孤儿分支场景）
                partition_id_for_table = b.topic_id
            db.execute(
                """
                INSERT INTO conversation_branches
                    (id, partition_id, topic_id, name, fork_point_id, path,
                     is_active, is_archived, summary, summary_dirty,
                     practice_sessions, practice_summary, created_at, last_message_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, is_active=EXCLUDED.is_active,
                    path=EXCLUDED.path,
                    summary=EXCLUDED.summary,
                    practice_sessions=EXCLUDED.practice_sessions,
                    practice_summary=EXCLUDED.practice_summary,
                    last_message_at=EXCLUDED.last_message_at
                """,
                (
                    b.id, partition_id_for_table, b.topic_id, b.name,
                    "",  # fork_point_id (deprecated in v4)
                    b.path or [], b.is_active, b.is_archived,
                    b.summary, b.summary_dirty, b.practice_sessions or [],
                    b.practice_summary or "",
                    b.created_at, b.last_message_at,
                ),
            )

        # ── 消息节点 ──
        type_adapter = TypeAdapter(list[ContentBlock])
        for n in data.nodes.values():
            cb_json = self._j(type_adapter.dump_python(n.content_blocks))
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
                    n.id, n.parent_id, n.children_ids or [], n.partition_id,
                    n.conversation_id, cb_json, n.text_summary, n.summary,
                    n.role, n.timestamp, n.token_count, n.is_deleted,
                    n.is_archived, n.has_modified_version,
                    n.links_to or [], n.linked_from or [],
                    self._j(getattr(n, 'metadata', {})),
                ),
            )

        # ── 响应块 ──
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
                    rb.id, rb.message_id, rb.partition_id, rb.conversation_id,
                    rb.type, rb.status, self._j(rb.content), rb.order,
                    rb.sources or [], rb.created_at, rb.updated_at,
                ),
            )

        # ── 链接节点 ──
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
                    ln.target_conversation_id, ln.source_partition_id,
                    ln.source_conversation_id, ln.preview_summary, ln.timestamp,
                ),
            )

        logger.info(f"Conversation data saved for user {user_id} ({len(data.nodes)} nodes)")

    # ── 迁移：JSON → PG ──

    def migrate_from_json(self, user_id: str, json_path: Path) -> None:
        if not json_path.exists():
            logger.warning(f"JSON file not found: {json_path}")
            return
        with open(json_path, "r", encoding="utf-8") as f:
            data = UserData.model_validate_json(f.read())
        self.save(user_id, data)
        logger.info(f"Migrated {user_id} from JSON to PG")


# 全局单例
pg_storage = PgStorageEngine()
