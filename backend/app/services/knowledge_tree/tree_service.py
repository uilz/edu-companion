"""
KnowledgeTreeService — 知识树容器 CRUD

职责：
- 创建/更新/删除/归档知识树
- 管理树的根节点引用
- 发布 TreeNodeCreated（根节点）等事件
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.schemas.knowledge_tree import KnowledgeTree

logger = logging.getLogger(__name__)


def _now() -> float:
    import time
    return time.time()


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
        return _now()
    if isinstance(raw, (int, float)):
        return float(raw)
    if hasattr(raw, "timestamp"):
        return raw.timestamp()
    return _now()


def _row_to_tree(row: dict) -> KnowledgeTree:
    return KnowledgeTree(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        description=row.get("description") or "",
        tree_type=row.get("tree_type") or "project",
        root_node_id=row.get("root_node_id"),
        default_view_mode=row.get("default_view_mode") or "tree",
        default_layout=row.get("default_layout") or "layered",
        tags=_json_list(row.get("tags")),
        meta=_json_list(row.get("meta")) if isinstance(row.get("meta"), list) else (json.loads(row["meta"]) if isinstance(row.get("meta"), str) else (row.get("meta") or {})),
        status=row.get("status") or "active",
        created_at=_ts(row.get("created_at")),
        updated_at=_ts(row.get("updated_at")),
        version=row.get("version", 0),
    )


class KnowledgeTreeService:
    """知识树容器服务。"""

    def create_tree(
        self,
        user_id: str,
        title: str = "我的知识树",
        tree_type: str = "project",
        description: str = "",
    ) -> KnowledgeTree:
        """创建知识树。"""
        tree_id = f"kt_{uuid4().hex[:12]}"
        db = get_db()
        db.execute(
            """INSERT INTO knowledge_trees
               (id, user_id, title, description, tree_type, default_view_mode, default_layout,
                tags, meta, status, version, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, 'tree', 'layered', '[]', '{}', 'active', 0, NOW(), NOW())""",
            (tree_id, user_id, title, description, tree_type),
        )
        return self.get_tree(user_id, tree_id)

    def get_tree(self, user_id: str, tree_id: str) -> Optional[KnowledgeTree]:
        """获取知识树。"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM knowledge_trees WHERE id = %s AND user_id = %s AND status != 'deleted'",
            (tree_id, user_id),
        )
        return _row_to_tree(row) if row else None

    def list_trees(self, user_id: str, status: str | None = None) -> list[KnowledgeTree]:
        """列出用户的知识树。"""
        db = get_db()
        if status:
            rows = db.fetchall(
                "SELECT * FROM knowledge_trees WHERE user_id = %s AND status = %s ORDER BY updated_at DESC",
                (user_id, status),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM knowledge_trees WHERE user_id = %s AND status != 'deleted' ORDER BY updated_at DESC",
                (user_id,),
            )
        return [_row_to_tree(r) for r in rows]

    def update_tree(
        self, user_id: str, tree_id: str, **fields
    ) -> Optional[KnowledgeTree]:
        """更新知识树元数据。"""
        allowed = {
            "title", "description", "tree_type", "root_node_id",
            "default_view_mode", "default_layout", "tags", "meta", "status",
        }
        updates = {}
        for k, v in fields.items():
            if k in allowed and v is not None:
                if k in ("tags", "meta"):
                    updates[k] = json.dumps(v, ensure_ascii=False)
                else:
                    updates[k] = v
        if not updates:
            return self.get_tree(user_id, tree_id)

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [tree_id, user_id]
        db = get_db()
        db.execute(
            f"UPDATE knowledge_trees SET {set_clause}, version = version + 1, updated_at = NOW() "
            "WHERE id = %s AND user_id = %s",
            values,
        )
        return self.get_tree(user_id, tree_id)

    def delete_tree(self, user_id: str, tree_id: str) -> bool:
        """软删除知识树（级联删除由外键处理）。"""
        db = get_db()
        rowcount = db.execute_with_rowcount(
            "UPDATE knowledge_trees SET status = 'deleted', updated_at = NOW() WHERE id = %s AND user_id = %s",
            (tree_id, user_id),
        )
        return rowcount > 0

    def set_root_node(self, user_id: str, tree_id: str, root_node_id: str) -> Optional[KnowledgeTree]:
        """设置根节点。"""
        return self.update_tree(user_id, tree_id, root_node_id=root_node_id)


kt_svc = KnowledgeTreeService()
