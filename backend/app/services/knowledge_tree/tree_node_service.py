"""
TreeNodeService — 知识树节点 CRUD + 移动 + 排序

职责：
- 创建/更新/删除/移动树节点
- 维护 children_order
- 发布 TreeNodeCreated / TreeNodeUpdated / TreeNodeMoved / TreeNodeDeleted
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.schemas.knowledge_tree import TreeNode

logger = logging.getLogger(__name__)


def _now() -> float:
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


def _row_to_node(row: dict) -> TreeNode:
    return TreeNode(
        id=row["id"],
        tree_id=row["tree_id"],
        user_id=row["user_id"],
        label=row["label"],
        node_type=row.get("node_type") or "concept",
        parent_id=row.get("parent_id"),
        children_order=_json_list(row.get("children_order")),
        order_index=row.get("order_index", 0),
        color=row.get("color") or "",
        emoji=row.get("emoji") or "",
        icon_url=row.get("icon_url") or "",
        position=_json_dict(row.get("position")),
        source_refs=_json_list(row.get("source_refs")),
        tags=_json_list(row.get("tags")),
        brief=row.get("brief") or "",
        meta=_json_dict(row.get("meta")),
        status=row.get("status") or "active",
        created_at=_ts(row.get("created_at")),
        updated_at=_ts(row.get("updated_at")),
        version=row.get("version", 0),
    )


def _publish(event_type: str, event):
    """发布事件，失败不阻塞主流程。"""
    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        publish_event_safe(event)
    except Exception:
        logger.debug("%s 事件发布失败", event_type, exc_info=True)


class TreeNodeService:
    """知识树节点服务。"""

    def create_node(
        self,
        user_id: str,
        tree_id: str,
        label: str,
        parent_id: str | None = None,
        node_type: str = "concept",
        order_index: int = 0,
        color: str = "",
        emoji: str = "",
        position: dict | None = None,
        brief: str = "",
        tags: list[str] | None = None,
    ) -> TreeNode:
        """创建树节点。"""
        node_id = f"tn_{uuid4().hex[:12]}"
        db = get_db()
        db.execute(
            """INSERT INTO tree_nodes
               (id, tree_id, user_id, label, node_type, parent_id, order_index,
                color, emoji, icon_url, position, children_order, source_refs, brief, tags, meta,
                status, version, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '', %s, '[]', '[]', %s, %s, '{}',
                       'active', 0, NOW(), NOW())""",
            (
                node_id, tree_id, user_id, label, node_type, parent_id, order_index,
                color, emoji, json.dumps(position or {}, ensure_ascii=False),
                brief, json.dumps(tags or [], ensure_ascii=False),
            ),
        )
        # 更新父节点的 children_order
        if parent_id:
            self._add_child_to_parent(user_id, parent_id, node_id)

        node = self.get_node(user_id, node_id)
        if node:
            from shared.events import TreeNodeCreated
            _publish("TreeNodeCreated", TreeNodeCreated(
                user_id=user_id,
                source_module="knowledge_tree",
                tree_id=tree_id,
                node_id=node_id,
                parent_id=parent_id or "",
                label=label,
                node_type=node_type,
            ))
        return node

    def get_node(self, user_id: str, node_id: str) -> Optional[TreeNode]:
        """获取树节点。"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM tree_nodes WHERE id = %s AND user_id = %s AND status != 'deleted'",
            (node_id, user_id),
        )
        return _row_to_node(row) if row else None

    def list_nodes(
        self,
        user_id: str,
        tree_id: str,
        parent_id: str | None = None,
        status: str | None = None,
    ) -> list[TreeNode]:
        """列出树节点。"""
        db = get_db()
        params: list = [tree_id, user_id]
        sql = "SELECT * FROM tree_nodes WHERE tree_id = %s AND user_id = %s"
        if parent_id is not None:
            sql += " AND parent_id IS NOT DISTINCT FROM %s"
            params.append(parent_id)
        if status:
            sql += " AND status = %s"
            params.append(status)
        else:
            sql += " AND status != 'deleted'"
        sql += " ORDER BY order_index, created_at"
        rows = db.fetchall(sql, tuple(params))
        return [_row_to_node(r) for r in rows]

    def get_subtree(self, user_id: str, root_node_id: str) -> dict[str, TreeNode]:
        """获取以 root_node_id 为根的整棵子树（BFS）。"""
        result: dict[str, TreeNode] = {}
        queue = [root_node_id]
        while queue:
            current_id = queue.pop(0)
            if current_id in result:
                continue
            node = self.get_node(user_id, current_id)
            if not node:
                continue
            result[current_id] = node
            for child_id in node.children_order:
                if child_id not in result:
                    queue.append(child_id)
        return result

    def update_node(
        self, user_id: str, node_id: str, **fields
    ) -> Optional[TreeNode]:
        """更新树节点字段。"""
        allowed = {
            "label", "node_type", "color", "emoji", "icon_url",
            "position", "brief", "tags", "meta", "status",
        }
        updates = {}
        changed_fields: list[str] = []
        old_node = self.get_node(user_id, node_id)
        if not old_node:
            return None

        for k, v in fields.items():
            if k in allowed and v is not None:
                changed_fields.append(k)
                if k in ("position", "tags", "meta"):
                    updates[k] = json.dumps(v, ensure_ascii=False)
                else:
                    updates[k] = v

        if not updates:
            return old_node

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [node_id, user_id]
        db = get_db()
        db.execute(
            f"UPDATE tree_nodes SET {set_clause}, version = version + 1, updated_at = NOW() "
            "WHERE id = %s AND user_id = %s",
            values,
        )

        node = self.get_node(user_id, node_id)
        if node:
            from shared.events import TreeNodeUpdated
            _publish("TreeNodeUpdated", TreeNodeUpdated(
                user_id=user_id,
                source_module="knowledge_tree",
                tree_id=node.tree_id,
                node_id=node_id,
                changed_fields=changed_fields,
                old_label=old_node.label,
                new_label=node.label,
            ))
        return node

    def move_node(
        self,
        user_id: str,
        node_id: str,
        new_parent_id: str | None = None,
        new_position: dict | None = None,
        new_order_index: int | None = None,
    ) -> Optional[TreeNode]:
        """移动树节点：改变父节点、位置或顺序。"""
        node = self.get_node(user_id, node_id)
        if not node:
            return None

        old_parent_id = node.parent_id
        tree_id = node.tree_id

        db = get_db()

        # 从旧父节点移除
        if old_parent_id:
            self._remove_child_from_parent(user_id, old_parent_id, node_id)

        # 更新节点
        updates: list[tuple[str, Any]] = [("parent_id", new_parent_id)]
        if new_position is not None:
            updates.append(("position", json.dumps(new_position, ensure_ascii=False)))
        if new_order_index is not None:
            updates.append(("order_index", new_order_index))

        set_clause = ", ".join(f"{k} = %s" for k, _ in updates)
        values = [v for _, v in updates] + [node_id, user_id]
        db.execute(
            f"UPDATE tree_nodes SET {set_clause}, version = version + 1, updated_at = NOW() "
            "WHERE id = %s AND user_id = %s",
            values,
        )

        # 添加到新父节点
        if new_parent_id:
            self._add_child_to_parent(user_id, new_parent_id, node_id)

        node = self.get_node(user_id, node_id)
        if node:
            from shared.events import TreeNodeMoved
            _publish("TreeNodeMoved", TreeNodeMoved(
                user_id=user_id,
                source_module="knowledge_tree",
                tree_id=tree_id,
                node_id=node_id,
                old_parent_id=old_parent_id or "",
                new_parent_id=new_parent_id or "",
                new_position=new_position or {},
            ))
        return node

    def reorder_children(
        self, user_id: str, parent_id: str, children_order: list[str]
    ) -> bool:
        """重新排序子节点。"""
        db = get_db()
        rowcount = db.execute_with_rowcount(
            "UPDATE tree_nodes SET children_order = %s, version = version + 1, updated_at = NOW() "
            "WHERE id = %s AND user_id = %s",
            (json.dumps(children_order, ensure_ascii=False), parent_id, user_id),
        )
        return rowcount > 0

    def delete_node(self, user_id: str, node_id: str) -> bool:
        """软删除树节点（级联删除子节点由外键处理）。"""
        node = self.get_node(user_id, node_id)
        if not node:
            return False

        tree_id = node.tree_id
        db = get_db()

        # 从父节点移除
        if node.parent_id:
            self._remove_child_from_parent(user_id, node.parent_id, node_id)

        # 软删除（子节点由 FK CASCADE 物理删除，但我们统一软删除）
        # 这里为了简单先物理标记，实际应递归软删除
        self._delete_recursive(user_id, node_id)

        from shared.events import TreeNodeDeleted
        _publish("TreeNodeDeleted", TreeNodeDeleted(
            user_id=user_id,
            source_module="knowledge_tree",
            tree_id=tree_id,
            node_id=node_id,
        ))
        return True

    def _delete_recursive(self, user_id: str, node_id: str) -> None:
        """递归软删除节点及其子孙。"""
        node = self.get_node(user_id, node_id)
        if not node:
            return
        for child_id in node.children_order:
            self._delete_recursive(user_id, child_id)
        db = get_db()
        db.execute(
            "UPDATE tree_nodes SET status = 'deleted', updated_at = NOW() WHERE id = %s AND user_id = %s",
            (node_id, user_id),
        )

    def _add_child_to_parent(self, user_id: str, parent_id: str, child_id: str) -> None:
        db = get_db()
        db.execute(
            """UPDATE tree_nodes
               SET children_order = children_order || %s::jsonb,
                   updated_at = NOW()
               WHERE id = %s AND user_id = %s
               AND NOT (children_order @> %s::jsonb)""",
            (json.dumps([child_id]), parent_id, user_id, json.dumps([child_id])),
        )

    def _remove_child_from_parent(self, user_id: str, parent_id: str, child_id: str) -> None:
        db = get_db()
        row = db.fetchone(
            "SELECT children_order FROM tree_nodes WHERE id = %s AND user_id = %s",
            (parent_id, user_id),
        )
        if not row:
            return
        order = _json_list(row.get("children_order"))
        if child_id not in order:
            return
        order.remove(child_id)
        db.execute(
            "UPDATE tree_nodes SET children_order = %s, updated_at = NOW() WHERE id = %s AND user_id = %s",
            (json.dumps(order, ensure_ascii=False), parent_id, user_id),
        )


tn_svc = TreeNodeService()
