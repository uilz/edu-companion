"""
PostgreSQL 对话存储引擎 (v6.0 — DirectoryNode)

统一 UserData JSONB 存储, 使用 directory_nodes 取代旧 partitions/domains/topics/conversations。
所有字典存入 conversation_user_meta 表的 JSONB 列。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from app.infrastructure.db.database import Database
from app.schemas.conversation import (
    UserData, ResponseBlock, LinkNode, ContentBlock,
    FileRecord, BackgroundJob, KnowledgeGraph,
)
from app.schemas.directory_node import DirectoryNode, MessageNode
from shared.protocols.data_repository import DataRepository, AdminRepository

logger = logging.getLogger(__name__)


class PgStorageEngine(DataRepository, AdminRepository):
    """PostgreSQL 存储引擎 — DirectoryNode 版本"""

    def __init__(self) -> None:
        self._initialized = False

    # ── 初始化 ──

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        db = Database.get()
        backend_root = Path(__file__).resolve().parents[3]
        for sql_file in ["conversation_schema.sql", "directory_schema.sql"]:
            sql_path = backend_root / "app" / "db" / sql_file
            if sql_path.exists():
                try:
                    with open(sql_path) as f:
                        db.execute(f.read())
                    logger.info("Schema ensured: %s", sql_file)
                except Exception as e:
                    logger.warning("Schema init %s: %s", sql_file, e)
        self._initialized = True

    # ── JSON 序列化 ──

    @staticmethod
    def _j(obj) -> str:
        if obj is None:
            return "null"
        return json.dumps(obj, ensure_ascii=False, default=str)

    @staticmethod
    def _parse_json(raw, default=None):
        if raw is None or raw == "" or raw == {} or raw == []:
            return default if default is not None else {}
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else {}

    # ── ETag ──

    _etag_cache: dict[str, str] = {}

    def get_etag(self, user_id: str) -> str:
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
        self._ensure_schema()
        db = Database.get()
        meta = db.fetchone(
            "SELECT * FROM conversation_user_meta WHERE user_id = %s",
            (user_id,),
        )
        if not meta:
            return UserData(user_id=user_id)

        # directory_nodes
        directory_nodes: dict[str, DirectoryNode] = {}
        raw_dn = self._parse_json(meta.get("directory_nodes", {}), {})
        if isinstance(raw_dn, dict):
            for nid, ndata in raw_dn.items():
                if isinstance(ndata, dict):
                    try:
                        directory_nodes[nid] = DirectoryNode(**ndata)
                    except Exception as e:
                        logger.debug("Parse DirectoryNode %s: %s", nid, e)

        # nodes (MessageNode)
        nodes: dict[str, MessageNode] = {}
        raw_nodes = self._parse_json(meta.get("nodes", {}), {})
        if isinstance(raw_nodes, dict):
            for nid, ndata in raw_nodes.items():
                if isinstance(ndata, dict):
                    ndata = self._fix_node_content_blocks(ndata)
                    try:
                        nodes[nid] = MessageNode(**ndata)
                    except Exception as e:
                        logger.debug("Deser MessageNode %s: %s", nid, e)

        # response_blocks
        response_blocks: dict[str, ResponseBlock] = {}
        raw_rb = self._parse_json(meta.get("response_blocks", {}), {})
        if isinstance(raw_rb, dict):
            for rid, rdata in raw_rb.items():
                if isinstance(rdata, dict):
                    try:
                        response_blocks[rid] = ResponseBlock(**rdata)
                    except Exception:
                        pass

        # link_nodes
        link_nodes = self._parse_json_dict(LinkNode, meta.get("link_nodes", {}))
        files = self._parse_json_dict(FileRecord, meta.get("files", {}))
        background_jobs = self._parse_json_dict(BackgroundJob, meta.get("background_jobs", {}))

        # 其他字段
        event_log = self._parse_json(meta.get("event_log", []), [])
        secretary_prefs = self._parse_json(meta.get("secretary_prefs", {}), {})
        policy_memory = self._parse_json(meta.get("policy_memory", {}), {})

        knowledge_graphs = {}
        raw_kg = self._parse_json(meta.get("knowledge_graphs", {}))
        if isinstance(raw_kg, dict):
            for pid, kg_data in raw_kg.items():
                if isinstance(kg_data, dict):
                    try:
                        knowledge_graphs[pid] = KnowledgeGraph.model_validate(kg_data)
                    except Exception as e:
                        logger.warning("Skip broken KG %s: %s", pid, e)

        return UserData(
            user_id=user_id,
            role=meta.get("role", "student"),
            org_id=meta.get("org_id"),
            directory_nodes=directory_nodes,
            nodes=nodes,
            link_nodes=link_nodes,
            response_blocks=response_blocks,
            files=files,
            background_jobs=background_jobs,
            knowledge_graphs=knowledge_graphs,
            event_log=event_log,
            secretary_prefs=secretary_prefs,
            policy_memory=policy_memory,
        )

    # ── 保存 ──

    def save(self, user_id: str, data: UserData) -> None:
        self._ensure_schema()
        db = Database.get()
        type_adapter = TypeAdapter(list[ContentBlock])

        # directory_nodes
        dn_json = self._j({k: v.model_dump() for k, v in data.directory_nodes.items()})

        # nodes
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
                (user_id, role, org_id,
                 directory_nodes, nodes, link_nodes, response_blocks,
                 files, background_jobs,
                 knowledge_graphs, event_log,
                 secretary_prefs, policy_memory,
                 created_at, updated_at)
            VALUES (%s,%s,%s, %s,%s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
                role = EXCLUDED.role,
                org_id = EXCLUDED.org_id,
                directory_nodes = EXCLUDED.directory_nodes,
                nodes = EXCLUDED.nodes,
                link_nodes = EXCLUDED.link_nodes,
                response_blocks = EXCLUDED.response_blocks,
                files = EXCLUDED.files,
                background_jobs = EXCLUDED.background_jobs,
                knowledge_graphs = EXCLUDED.knowledge_graphs,
                event_log = EXCLUDED.event_log,
                secretary_prefs = EXCLUDED.secretary_prefs,
                policy_memory = EXCLUDED.policy_memory,
                updated_at = EXCLUDED.updated_at
            """,
            (
                user_id,
                data.role,
                data.org_id,
                dn_json,
                nodes_json,
                link_nodes_json,
                response_blocks_json,
                self._j({k: v.model_dump() for k, v in data.files.items()}),
                self._j({k: v.model_dump() for k, v in data.background_jobs.items()}),
                self._j({k: v.model_dump() for k, v in data.knowledge_graphs.items()}),
                self._j(data.event_log),
                self._j(data.secretary_prefs),
                self._j(data.policy_memory),
                time.time(),
                time.time(),
            ),
        )

    # ── 辅助 ──

    @staticmethod
    def _parse_json_dict(model_cls, raw: Any) -> dict:
        result = {}
        data = PgStorageEngine._parse_json(raw, {})
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict):
                    try:
                        result[key] = model_cls(**val)
                    except Exception as e:
                        logger.debug("Parse %s %s: %s", model_cls.__name__, key, e)
        return result

    @staticmethod
    def _fix_node_content_blocks(ndata: dict) -> dict:
        ndata.setdefault("children_ids", [])
        ndata.setdefault("links_to", [])
        ndata.setdefault("linked_from", [])
        ndata.setdefault("parent_id", None)
        if "content_blocks" not in ndata:
            ndata["content_blocks"] = []
        return ndata

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
        from pathlib import Path
        p = Path(json_path)
        if not p.exists():
            logger.warning("JSON file not found: %s", json_path)
            return
        with open(p, "r", encoding="utf-8") as f:
            data = UserData.model_validate_json(f.read())
        self.save(user_id, data)
        logger.info("Migrated %s from JSON to PG", user_id)


# 全局单例
pg_storage = PgStorageEngine()
