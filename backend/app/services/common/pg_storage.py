"""
PostgreSQL 对话存储引擎 (v5.0)

统一 UserData JSONB 存储。
所有 UserData 字段（partitions, conversations, nodes, response_blocks, link_nodes 等）
均存储在 conversation_user_meta 表的 JSONB 列中。

实现 DataRepository + AdminRepository 双 Port。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.db.database import Database
from app.schemas.conversation import (
    UserData, Partition, Conversation, TreeNode,
    ResponseBlock, LinkNode, ContentBlock, Domain, Topic, FileRecord,
    BackgroundJob, KnowledgeGraph,
)
from shared.protocols.data_repository import DataRepository, AdminRepository
from pydantic import TypeAdapter

logger = logging.getLogger(__name__)


class PgStorageEngine(DataRepository, AdminRepository):
    """PostgreSQL 存储引擎，统一 JSONB 存储。同时实现 DataRepository + AdminRepository。"""

    def __init__(self) -> None:
        self._initialized = False

    # ── 初始化与 schema 确保 ──

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        db = Database.get()
        # pg_storage.py 位于 app/services/common/，schema 在 app/db/conversation_schema.sql
        # 用 pathlib 解析到 backend 包根目录的稳定路径
        from pathlib import Path
        backend_root = Path(__file__).resolve().parents[3]  # .../backend
        sql_path = backend_root / "app" / "db" / "conversation_schema.sql"
        try:
            with open(sql_path) as f:
                db.execute(f.read())
            logger.info("conversation_user_meta schema ensured via %s", sql_path)
        except Exception as e:
            logger.warning("schema init failed (may already exist): %s", e)
        self._initialized = True

    # ── JSON 序列化辅助 ──

    @staticmethod
    def _j(obj) -> str:
        """安全 JSON 序列化"""
        if obj is None:
            return "null"
        return json.dumps(obj, ensure_ascii=False, default=str)

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
        """返回当前用户数据的 ETag (基于 updated_at)"""
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
        """从 PG 加载完整用户数据 (v5.0: 全部从 conversation_user_meta JSONB 读取)"""
        self._ensure_schema()
        db = Database.get()

        meta = db.fetchone(
            "SELECT * FROM conversation_user_meta WHERE user_id = %s",
            (user_id,),
        )

        if not meta:
            return UserData(user_id=user_id)

        # ── 从 meta JSONB 列还原所有集合 ──
        partitions = self._parse_json_dict(Partition, meta.get("partitions", {}))
        conversations = self._parse_json_dict(Conversation, meta.get("conversations", {}))
        link_nodes = self._parse_json_dict(LinkNode, meta.get("link_nodes", {}))
        domains = self._parse_json_dict(Domain, meta.get("domains", {}))
        topics = self._parse_json_dict(Topic, meta.get("topics", {}))
        files = self._parse_json_dict(FileRecord, meta.get("files", {}))
        background_jobs = self._parse_json_dict(BackgroundJob, meta.get("background_jobs", {}))

        # ── nodes 特殊处理（content_blocks 需要 ContentBlock 类型适配）──
        nodes: dict[str, TreeNode] = {}
        raw_nodes = self._parse_json(meta.get("nodes", {}), {})
        if isinstance(raw_nodes, dict):
            for nid, ndata in raw_nodes.items():
                if isinstance(ndata, dict):
                    ndata = self._fix_node_content_blocks(ndata)
                    nodes[nid] = TreeNode(**ndata)

        # ── response_blocks ──
        response_blocks: dict[str, ResponseBlock] = {}
        raw_rb = self._parse_json(meta.get("response_blocks", {}), {})
        if isinstance(raw_rb, dict):
            for rid, rdata in raw_rb.items():
                if isinstance(rdata, dict):
                    response_blocks[rid] = ResponseBlock(**rdata)

        # ── 其他字段 ──
        event_log = self._parse_json(meta.get("event_log", []), [])
        knowledge_graphs = {}
        raw_kg = self._parse_json(meta.get("knowledge_graphs", {}))
        if isinstance(raw_kg, dict):
            for pid, kg_data in raw_kg.items():
                if isinstance(kg_data, dict):
                    try:
                        knowledge_graphs[pid] = KnowledgeGraph.model_validate(kg_data)
                    except Exception as e:
                        logger.warning(f"跳过损坏的知识图谱 {pid}: {e}")

        secretary_prefs = self._parse_json(meta.get("secretary_prefs", {}), {})
        policy_memory = self._parse_json(meta.get("policy_memory", {}), {})

        return UserData(
            user_id=user_id,
            role=meta.get("role", "student"),
            org_id=meta.get("org_id"),
            active_partition_id=meta.get("active_partition_id"),
            partitions=partitions,
            conversations=conversations,
            nodes=nodes,
            link_nodes=link_nodes,
            response_blocks=response_blocks,
            domains=domains,
            topics=topics,
            files=files,
            background_jobs=background_jobs,
            knowledge_graphs=knowledge_graphs,
            event_log=event_log,
            secretary_prefs=secretary_prefs,
            policy_memory=policy_memory,
        )

    @staticmethod
    def _parse_json_dict(model_cls, raw: Any) -> dict:
        """解析 JSONB 为 Pydantic 模型字典"""
        result = {}
        data = PgStorageEngine._parse_json(raw, {})
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict):
                    try:
                        result[key] = model_cls(**val)
                    except Exception as e:
                        logger.debug(f"解析 {model_cls.__name__} 失败 {key}: {e}")
        return result

    @staticmethod
    def _fix_node_content_blocks(ndata: dict) -> dict:
        """修复 content_blocks 类型"""
        raw_cb = ndata.get("content_blocks", [])
        if raw_cb and isinstance(raw_cb, list):
            try:
                adapter = TypeAdapter(list[ContentBlock])
                ndata["content_blocks"] = adapter.validate_python(raw_cb)
            except Exception:
                ndata["content_blocks"] = []
        ndata.setdefault("children_ids", [])
        ndata.setdefault("links_to", [])
        ndata.setdefault("linked_from", [])
        ndata.setdefault("conversation_id", ndata.pop("branch_id", ""))
        return ndata

    # ── 保存 ──

    def save(self, user_id: str, data: UserData) -> None:
        """保存完整用户数据到 PG (v5.0: 全部写入 conversation_user_meta)"""
        self._ensure_schema()
        db = Database.get()

        type_adapter = TypeAdapter(list[ContentBlock])

        # 序列化所有集合为 JSONB
        partitions_json = self._j({k: v.model_dump() for k, v in data.partitions.items()})
        conversations_json = self._j({k: v.model_dump() for k, v in data.conversations.items()})

        nodes_dict = {}
        for nid, node in data.nodes.items():
            nd = node.model_dump()
            nd["content_blocks"] = type_adapter.dump_python(node.content_blocks)
            nodes_dict[nid] = nd
        nodes_json = self._j(nodes_dict)

        link_nodes_json = self._j({k: v.model_dump() for k, v in data.link_nodes.items()})
        response_blocks_json = self._j({k: v.model_dump() for k, v in data.response_blocks.items()})

        db.execute(
            """
            INSERT INTO conversation_user_meta
                (user_id, role, org_id, active_partition_id,
                 knowledge_graphs, event_log,
                 domains, topics, files, background_jobs,
                 secretary_prefs, policy_memory,
                 partitions, conversations, nodes, link_nodes, response_blocks,
                 created_at, updated_at)
            VALUES (%s,%s,%s,%s, %s,%s, %s,%s,%s,%s, %s,%s, %s,%s,%s,%s,%s, %s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
                role = EXCLUDED.role,
                org_id = EXCLUDED.org_id,
                active_partition_id = EXCLUDED.active_partition_id,
                knowledge_graphs = EXCLUDED.knowledge_graphs,
                event_log = EXCLUDED.event_log,
                domains = EXCLUDED.domains,
                topics = EXCLUDED.topics,
                files = EXCLUDED.files,
                background_jobs = EXCLUDED.background_jobs,
                secretary_prefs = EXCLUDED.secretary_prefs,
                policy_memory = EXCLUDED.policy_memory,
                partitions = EXCLUDED.partitions,
                conversations = EXCLUDED.conversations,
                nodes = EXCLUDED.nodes,
                link_nodes = EXCLUDED.link_nodes,
                response_blocks = EXCLUDED.response_blocks,
                updated_at = EXCLUDED.updated_at
            """,
            (
                user_id,
                data.role,
                data.org_id,
                data.active_partition_id,
                self._j({k: v.model_dump() for k, v in data.knowledge_graphs.items()}),
                self._j(data.event_log),
                self._j({k: v.model_dump() for k, v in data.domains.items()}),
                self._j({k: v.model_dump() for k, v in data.topics.items()}),
                self._j({k: v.model_dump() for k, v in data.files.items()}),
                self._j({k: v.model_dump() for k, v in data.background_jobs.items()}),
                self._j(data.secretary_prefs),
                self._j(data.policy_memory),
                partitions_json,
                conversations_json,
                nodes_json,
                link_nodes_json,
                response_blocks_json,
                time.time(),
                time.time(),
            ),
        )

    # ── AdminRepository ──

    def execute(self, sql: str, params: tuple = ()) -> None:
        db = Database.get()
        db.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        db = Database.get()
        return db.fetchone(sql, params)

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        db = Database.get()
        return db.fetchall(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        return self.fetchall(sql, params)

    def migrate_from_json(self, user_id: str, json_path: str) -> None:
        """从 JSON 文件迁移用户数据到 PostgreSQL（开发阶段用）"""
        from pathlib import Path
        p = Path(json_path)
        if not p.exists():
            logger.warning(f"JSON file not found: {json_path}")
            return
        with open(p, "r", encoding="utf-8") as f:
            data = UserData.model_validate_json(f.read())
        self.save(user_id, data)
        logger.info(f"Migrated {user_id} from JSON to PG")


# 全局单例
pg_storage = PgStorageEngine()
