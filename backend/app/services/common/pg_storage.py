"""
PostgreSQL 对话存储引擎 (DirectoryNode)

统一 UserData JSONB 存储, 使用 directory_nodes 取代旧 partitions/domains/topics/conversations。
所有字典存入 conversation_user_meta 表的 JSONB 列。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.infrastructure.db.database import Database
from app.schemas.conversation import (
    UserData, ResponseBlock, LinkNode,
    FileRecord, KnowledgeGraph,
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

        # D18: nodes 从 messages 表读取
        from app.services.conversation.message_repository import get_message_repo
        msg_repo = get_message_repo()
        nodes = msg_repo.load_all(user_id)

        # D15: response_blocks 从 nodes.content_blocks 重建
        response_blocks: dict[str, ResponseBlock] = {}
        for nid, node in nodes.items():
            for cb in node.content_blocks:
                if isinstance(cb, dict) and cb.get("_response_block"):
                    try:
                        response_blocks[cb.get("_response_block_id", cb.get("id", ""))] = ResponseBlock(**{
                            "id": cb.get("_response_block_id", cb.get("id", "")),
                            "message_id": nid,
                            "dir_id": cb.get("dir_id", ""),
                            "conv_id": cb.get("conv_id", ""),
                            "type": cb.get("block_type", "text"),
                            "status": cb.get("status", "ready"),
                            "content": cb.get("content", {}),
                            "order": cb.get("order", 0),
                            "sources": cb.get("sources", []),
                            "created_at": cb.get("created_at", 0),
                            "updated_at": cb.get("updated_at", 0),
                        })
                    except Exception:
                        pass

        # link_nodes
        link_nodes = self._parse_json_dict(LinkNode, meta.get("link_nodes", {}))
        files = self._parse_json_dict(FileRecord, meta.get("files", {}))

        # D17: background_jobs 纯内存，不再从 DB 读取

        # 其他字段
        event_log = self._parse_json(meta.get("event_log", []), [])

        # D16: secretary_prefs / policy_memory 从 user_settings 统一表读取
        from app.infrastructure.db.user_settings_repo import get_user_settings_repo
        settings_repo = get_user_settings_repo()
        secretary_prefs = settings_repo.get_key(user_id, "secretary_prefs", {})
        policy_memory = settings_repo.get_key(user_id, "policy_memory", {})

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
            knowledge_graphs=knowledge_graphs,
            event_log=event_log,
            secretary_prefs=secretary_prefs,
            policy_memory=policy_memory,
        )

    # ── 保存 ──

    def save(self, user_id: str, data: UserData) -> None:
        self._ensure_schema()
        db = Database.get()

        # directory_nodes
        dn_json = self._j({k: v.model_dump() for k, v in data.directory_nodes.items()})

        # D18: nodes 写入 messages 独立表
        # D15: response_blocks 合并到 nodes.content_blocks 一起持久化
        from app.services.conversation.message_repository import get_message_repo
        msg_repo = get_message_repo()

        # 将 response_blocks 合并到对应消息的 content_blocks
        for block_id, block in data.response_blocks.items():
            msg_id = block.message_id
            if msg_id and msg_id in data.nodes:
                node = data.nodes[msg_id]
                # 移除旧的 response_block 条目
                node.content_blocks = [cb for cb in node.content_blocks
                                       if not (isinstance(cb, dict) and cb.get("_response_block"))]
                # 添加新的 response_block 条目
                node.content_blocks.append({
                    "_response_block": True,
                    "_response_block_id": block.id,
                    "status": block.status,
                    "block_type": block.type,
                    "content": block.content,
                    "order": block.order,
                    "sources": block.sources,
                    "dir_id": getattr(block, "dir_id", block.conv_id),
                    "conv_id": block.conv_id,
                    "created_at": block.created_at,
                    "updated_at": block.updated_at,
                })

        msg_repo.save_all(user_id, data.nodes)

        link_nodes_json = self._j({k: v.model_dump() for k, v in data.link_nodes.items()})

        db.execute(
            """
            INSERT INTO conversation_user_meta
                (user_id, role, org_id,
                 directory_nodes, link_nodes,
                 files,
                 knowledge_graphs, event_log,
                 created_at, updated_at)
            VALUES (%s,%s,%s, %s,%s, %s, %s,%s, %s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
                role = EXCLUDED.role,
                org_id = EXCLUDED.org_id,
                directory_nodes = EXCLUDED.directory_nodes,
                link_nodes = EXCLUDED.link_nodes,
                files = EXCLUDED.files,
                knowledge_graphs = EXCLUDED.knowledge_graphs,
                event_log = EXCLUDED.event_log,
                updated_at = EXCLUDED.updated_at
            """,
            (
                user_id,
                data.role,
                data.org_id,
                dn_json,
                link_nodes_json,
                self._j({k: v.model_dump() for k, v in data.files.items()}),
                self._j({k: v.model_dump() for k, v in data.knowledge_graphs.items()}),
                self._j(data.event_log),
                time.time(),
                time.time(),
            ),
        )

        # D16: secretary_prefs / policy_memory 写入 user_settings 统一表
        from app.infrastructure.db.user_settings_repo import get_user_settings_repo
        settings_repo = get_user_settings_repo()
        settings_repo.set_multiple(user_id, {
            "secretary_prefs": data.secretary_prefs,
            "policy_memory": data.policy_memory,
        })

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
