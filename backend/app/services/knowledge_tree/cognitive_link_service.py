"""
CognitiveLinkService — 树节点与认知节点关联

职责：
- 创建/删除/查询 tree_node 与 cognitive_node 的关联
- 发布 TreeNodeLinkedToCognitiveNode / TreeNodeUnlinkedFromCognitiveNode
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.schemas.knowledge_tree import TreeNodeCognitiveLink

logger = logging.getLogger(__name__)


def _now() -> float:
    return time.time()


def _ts(raw) -> float:
    if raw is None:
        return _now()
    if isinstance(raw, (int, float)):
        return float(raw)
    if hasattr(raw, "timestamp"):
        return raw.timestamp()
    return _now()


def _row_to_link(row: dict) -> TreeNodeCognitiveLink:
    return TreeNodeCognitiveLink(
        id=row["id"],
        tree_id=row["tree_id"],
        tree_node_id=row["tree_node_id"],
        cognitive_node_id=row["cognitive_node_id"],
        user_id=row["user_id"],
        link_role=row.get("link_role") or "primary",
        created_at=_ts(row.get("created_at")),
    )


def _publish(event_type: str, event):
    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        publish_event_safe(event)
    except Exception:
        logger.debug("%s 事件发布失败", event_type, exc_info=True)


class CognitiveLinkService:
    """树节点-认知节点关联服务。"""

    def create_link(
        self,
        user_id: str,
        tree_id: str,
        tree_node_id: str,
        cognitive_node_id: str,
        link_role: str = "primary",
    ) -> Optional[TreeNodeCognitiveLink]:
        """创建关联。"""
        link_id = f"tcl_{uuid4().hex[:12]}"
        db = get_db()
        try:
            db.execute(
                """INSERT INTO tree_node_cognitive_links
                   (id, tree_id, tree_node_id, cognitive_node_id, user_id, link_role, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
                (link_id, tree_id, tree_node_id, cognitive_node_id, user_id, link_role),
            )
        except Exception:
            logger.exception("创建树节点-认知节点关联失败")
            return None

        link = self.get_link(user_id, link_id)
        if link:
            from shared.events import TreeNodeLinkedToCognitiveNode
            _publish("TreeNodeLinkedToCognitiveNode", TreeNodeLinkedToCognitiveNode(
                user_id=user_id,
                source_module="knowledge_tree",
                tree_id=tree_id,
                tree_node_id=tree_node_id,
                cognitive_node_id=cognitive_node_id,
                link_role=link_role,
            ))
        return link

    def get_link(self, user_id: str, link_id: str) -> Optional[TreeNodeCognitiveLink]:
        """获取关联。"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM tree_node_cognitive_links WHERE id = %s AND user_id = %s",
            (link_id, user_id),
        )
        return _row_to_link(row) if row else None

    def list_links_by_tree_node(
        self, user_id: str, tree_node_id: str
    ) -> list[TreeNodeCognitiveLink]:
        """列出某树节点的所有关联。"""
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM tree_node_cognitive_links WHERE tree_node_id = %s AND user_id = %s",
            (tree_node_id, user_id),
        )
        return [_row_to_link(r) for r in rows]

    def list_links_by_cognitive_node(
        self, user_id: str, cognitive_node_id: str
    ) -> list[TreeNodeCognitiveLink]:
        """列出某认知节点关联的所有树节点。"""
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM tree_node_cognitive_links WHERE cognitive_node_id = %s AND user_id = %s",
            (cognitive_node_id, user_id),
        )
        return [_row_to_link(r) for r in rows]

    def list_links_by_tree(
        self, user_id: str, tree_id: str
    ) -> list[TreeNodeCognitiveLink]:
        """列出某棵树的所有关联。"""
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM tree_node_cognitive_links WHERE tree_id = %s AND user_id = %s",
            (tree_id, user_id),
        )
        return [_row_to_link(r) for r in rows]

    def delete_link(self, user_id: str, link_id: str) -> bool:
        """删除关联。"""
        link = self.get_link(user_id, link_id)
        if not link:
            return False

        db = get_db()
        rowcount = db.execute_with_rowcount(
            "DELETE FROM tree_node_cognitive_links WHERE id = %s AND user_id = %s",
            (link_id, user_id),
        )
        if rowcount > 0:
            from shared.events import TreeNodeUnlinkedFromCognitiveNode
            _publish("TreeNodeUnlinkedFromCognitiveNode", TreeNodeUnlinkedFromCognitiveNode(
                user_id=user_id,
                source_module="knowledge_tree",
                tree_id=link.tree_id,
                tree_node_id=link.tree_node_id,
                cognitive_node_id=link.cognitive_node_id,
            ))
        return rowcount > 0

    def delete_link_by_nodes(
        self, user_id: str, tree_node_id: str, cognitive_node_id: str
    ) -> bool:
        """通过树节点和认知节点 ID 删除关联。"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM tree_node_cognitive_links WHERE tree_node_id = %s AND cognitive_node_id = %s AND user_id = %s",
            (tree_node_id, cognitive_node_id, user_id),
        )
        if not row:
            return False
        return self.delete_link(user_id, row["id"])


cl_svc = CognitiveLinkService()
