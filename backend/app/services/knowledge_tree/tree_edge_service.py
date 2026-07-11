"""
TreeEdgeService — 知识树边 CRUD

职责：
- 创建/删除树边
- 发布 TreeEdgeCreated / TreeEdgeDeleted
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.schemas.knowledge_tree import TreeEdge

logger = logging.getLogger(__name__)


def _now() -> float:
    return time.time()


def _json_dict(raw):
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _ts(raw) -> float:
    if raw is None:
        return _now()
    if isinstance(raw, (int, float)):
        return float(raw)
    if hasattr(raw, "timestamp"):
        return raw.timestamp()
    return _now()


def _row_to_edge(row: dict) -> TreeEdge:
    return TreeEdge(
        id=row["id"],
        tree_id=row["tree_id"],
        user_id=row["user_id"],
        source_node_id=row["source_node_id"],
        target_node_id=row["target_node_id"],
        edge_type=row.get("edge_type") or "parent_child",
        strength=float(row.get("strength", 1.0)),
        is_user_confirmed=row.get("is_user_confirmed", True),
        is_inferred=row.get("is_inferred", False),
        meta=_json_dict(row.get("meta")),
        created_at=_ts(row.get("created_at")),
    )


def _publish(event_type: str, event):
    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        publish_event_safe(event)
    except Exception:
        logger.debug("%s 事件发布失败", event_type, exc_info=True)


class TreeEdgeService:
    """知识树边服务。"""

    def create_edge(
        self,
        user_id: str,
        tree_id: str,
        source_node_id: str,
        target_node_id: str,
        edge_type: str = "parent_child",
        strength: float = 1.0,
        is_user_confirmed: bool = True,
        is_inferred: bool = False,
        meta: dict | None = None,
    ) -> Optional[TreeEdge]:
        """创建树边。"""
        edge_id = f"te_{uuid4().hex[:12]}"
        db = get_db()
        try:
            db.execute(
                """INSERT INTO tree_edges
                   (id, tree_id, user_id, source_node_id, target_node_id,
                    edge_type, strength, is_user_confirmed, is_inferred, meta, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (
                    edge_id, tree_id, user_id, source_node_id, target_node_id,
                    edge_type, strength, is_user_confirmed, is_inferred,
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
        except Exception:
            logger.exception("创建树边失败（可能违反唯一约束）")
            return None

        edge = self.get_edge(user_id, edge_id)
        if edge:
            from shared.events import TreeEdgeCreated
            _publish("TreeEdgeCreated", TreeEdgeCreated(
                user_id=user_id,
                source_module="knowledge_tree",
                tree_id=tree_id,
                edge_id=edge_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                edge_type=edge_type,
                strength=strength,
                is_inferred=is_inferred,
            ))
        return edge

    def get_edge(self, user_id: str, edge_id: str) -> Optional[TreeEdge]:
        """获取树边。"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM tree_edges WHERE id = %s AND user_id = %s",
            (edge_id, user_id),
        )
        return _row_to_edge(row) if row else None

    def list_edges(
        self,
        user_id: str,
        tree_id: str,
        source_node_id: str | None = None,
        target_node_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[TreeEdge]:
        """列出树边。"""
        db = get_db()
        params: list = [tree_id, user_id]
        sql = "SELECT * FROM tree_edges WHERE tree_id = %s AND user_id = %s"
        if source_node_id:
            sql += " AND source_node_id = %s"
            params.append(source_node_id)
        if target_node_id:
            sql += " AND target_node_id = %s"
            params.append(target_node_id)
        if edge_type:
            sql += " AND edge_type = %s"
            params.append(edge_type)
        sql += " ORDER BY created_at"
        rows = db.fetchall(sql, tuple(params))
        return [_row_to_edge(r) for r in rows]

    def delete_edge(self, user_id: str, edge_id: str) -> bool:
        """删除树边。"""
        edge = self.get_edge(user_id, edge_id)
        if not edge:
            return False

        db = get_db()
        rowcount = db.execute_with_rowcount(
            "DELETE FROM tree_edges WHERE id = %s AND user_id = %s",
            (edge_id, user_id),
        )
        if rowcount > 0:
            from shared.events import TreeEdgeDeleted
            _publish("TreeEdgeDeleted", TreeEdgeDeleted(
                user_id=user_id,
                source_module="knowledge_tree",
                tree_id=edge.tree_id,
                edge_id=edge_id,
            ))
        return rowcount > 0


te_svc = TreeEdgeService()
