"""
NavigationService — 导航树 CRUD 服务

导航树是纯文件系统，用户自由组织文件夹和会话引用。
"""
from __future__ import annotations
import json
import logging
import time
from typing import Optional
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.schemas.knowledge import NavigationNode as NavigationNodeSchema

logger = logging.getLogger(__name__)

ROOT_NAME = "我的知识库"


class NavigationService:
    """导航树服务 — navigation_nodes 表 CRUD"""

    # ── 根节点 ──

    def _ensure_root(self, user_id: str) -> NavigationNodeSchema:
        """确保存在根导航节点"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM navigation_nodes WHERE user_id = %s AND parent_id IS NULL AND deleted_at IS NULL",
            (user_id,),
        )
        if row:
            return self._row_to_schema(row)
        root_id = f"nav_root_{user_id}"
        db.execute(
            """INSERT INTO navigation_nodes (id, user_id, parent_id, node_type, kind, name, path)
               VALUES (%s, %s, NULL, 'dir', 'general', %s, %s)
               ON CONFLICT (id) DO NOTHING""",
            (root_id, user_id, ROOT_NAME, json.dumps([])),
        )
        return self.get_node(user_id, root_id)

    def _ensure_temp_dir(self, user_id: str) -> NavigationNodeSchema:
        """确保存在临时目录"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM navigation_nodes WHERE user_id = %s AND kind = 'temp' AND deleted_at IS NULL",
            (user_id,),
        )
        if row:
            return self._row_to_schema(row)
        root = self._ensure_root(user_id)
        return self.create_dir(user_id, root.id, "💬 临时", kind="temp")

    # ── CRUD ──

    def create_dir(
        self, user_id: str, parent_id: str, name: str,
        kind: str = "general", knowledge_area_id: str | None = None,
    ) -> NavigationNodeSchema:
        """创建目录节点"""
        parent = self.get_node(user_id, parent_id)
        if not parent:
            raise ValueError(f"父目录 {parent_id} 不存在")
        nav_id = f"nav_{uuid4().hex[:12]}"
        path = parent.path + [parent.id]
        db = get_db()
        db.execute(
            """INSERT INTO navigation_nodes (id, user_id, parent_id, node_type, kind, name, path, knowledge_area_id)
               VALUES (%s, %s, %s, 'dir', %s, %s, %s, %s)""",
            (nav_id, user_id, parent_id, kind, name, json.dumps(path), knowledge_area_id),
        )
        # 更新父节点的 children_order
        self._add_child_to_parent(user_id, parent_id, nav_id)
        return self.get_node(user_id, nav_id)

    def create_conv_ref(
        self, user_id: str, parent_id: str, conv_id: str,
        name: str = "", kind: str = "general",
    ) -> NavigationNodeSchema:
        """创建会话引用节点 (指向 Conversation)"""
        parent = self.get_node(user_id, parent_id)
        if not parent:
            raise ValueError(f"父目录 {parent_id} 不存在")
        nav_id = f"nav_{uuid4().hex[:12]}"
        path = parent.path + [parent.id]
        db = get_db()
        db.execute(
            """INSERT INTO navigation_nodes (id, user_id, parent_id, node_type, kind, name, path, conv_id)
               VALUES (%s, %s, %s, 'conv', %s, %s, %s, %s)""",
            (nav_id, user_id, parent_id, kind, name or "新对话", json.dumps(path), conv_id),
        )
        self._add_child_to_parent(user_id, parent_id, nav_id)
        return self.get_node(user_id, nav_id)

    def get_node(self, user_id: str, node_id: str) -> Optional[NavigationNodeSchema]:
        """获取导航节点"""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM navigation_nodes WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            (node_id, user_id),
        )
        return self._row_to_schema(row) if row else None

    def update_node(self, user_id: str, node_id: str, **fields) -> Optional[NavigationNodeSchema]:
        """更新导航节点"""
        db = get_db()
        allowed = {"name", "user_name", "ai_name", "kind", "knowledge_area_id", "metadata"}
        updates = {}
        for k, v in fields.items():
            if k in allowed:
                updates[k] = v
        if not updates:
            return self.get_node(user_id, node_id)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [node_id, user_id]
        db.execute(
            f"UPDATE navigation_nodes SET {set_clause}, updated_at = NOW() WHERE id = %s AND user_id = %s",
            values,
        )
        return self.get_node(user_id, node_id)

    def delete_node(self, user_id: str, node_id: str) -> bool:
        """递归删除导航节点及其子孙"""
        node = self.get_node(user_id, node_id)
        if not node:
            return False
        # 递归删除子节点
        for child_id in node.children_order:
            self.delete_node(user_id, child_id)
        db = get_db()
        db.execute(
            "UPDATE navigation_nodes SET deleted_at = NOW() WHERE id = %s AND user_id = %s",
            (node_id, user_id),
        )
        # 从父节点 children_order 移除
        if node.parent_id:
            self._remove_child_from_parent(user_id, node.parent_id, node_id)
        return True

    def list_children(self, user_id: str, parent_id: str) -> list[NavigationNodeSchema]:
        """列出子节点 (按 children_order 排序)"""
        parent = self.get_node(user_id, parent_id)
        if not parent:
            return []
        if not parent.children_order:
            return []
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM navigation_nodes WHERE id = ANY(%s) AND user_id = %s AND deleted_at IS NULL",
            (parent.children_order, user_id),
        )
        order_map = {nid: i for i, nid in enumerate(parent.children_order)}
        result = [self._row_to_schema(r) for r in rows]
        result.sort(key=lambda n: order_map.get(n.id, 999))
        return result

    def build_tree(self, user_id: str, root_id: str | None = None) -> list[dict]:
        """构建导航树 (前端侧边栏用)"""
        if root_id is None:
            root = self._ensure_root(user_id)
            root_id = root.id
        return self._build_tree_recursive(user_id, root_id)

    def _build_tree_recursive(self, user_id: str, parent_id: str) -> list[dict]:
        children = self.list_children(user_id, parent_id)
        result = []
        for child in children:
            d = {
                "id": child.id,
                "name": child.display_name,
                "node_type": child.node_type,
                "kind": child.kind,
                "parent_id": child.parent_id,
                "conv_id": child.conv_id,
                "knowledge_area_id": child.knowledge_area_id,
            }
            if child.node_type == "dir":
                d["children"] = self._build_tree_recursive(user_id, child.id)
            result.append(d)
        return result

    def migrate_conv(
        self, user_id: str, nav_id: str, target_dir_id: str,
    ) -> NavigationNodeSchema:
        """将会话导航节点迁移到目标目录"""
        node = self.get_node(user_id, nav_id)
        if not node or node.node_type != "conv":
            raise ValueError(f"导航节点 {nav_id} 不是会话引用")
        target = self.get_node(user_id, target_dir_id)
        if not target or target.node_type != "dir":
            raise ValueError(f"目标 {target_dir_id} 不是目录")

        # 从旧父节点移除
        if node.parent_id:
            self._remove_child_from_parent(user_id, node.parent_id, nav_id)

        # 更新父节点
        db = get_db()
        new_path = target.path + [target.id]
        db.execute(
            "UPDATE navigation_nodes SET parent_id = %s, path = %s, kind = 'general', updated_at = NOW() WHERE id = %s AND user_id = %s",
            (target_dir_id, json.dumps(new_path), nav_id, user_id),
        )
        self._add_child_to_parent(user_id, target_dir_id, nav_id)
        return self.get_node(user_id, nav_id)

    # ── 辅助 ──

    def _add_child_to_parent(self, user_id: str, parent_id: str, child_id: str) -> None:
        db = get_db()
        db.execute(
            """UPDATE navigation_nodes
               SET children_order = children_order || %s::jsonb, updated_at = NOW()
               WHERE id = %s AND user_id = %s
               AND NOT (children_order @> %s::jsonb)""",
            (json.dumps([child_id]), parent_id, user_id, json.dumps([child_id])),
        )

    def _remove_child_from_parent(self, user_id: str, parent_id: str, child_id: str) -> None:
        db = get_db()
        row = db.fetchone(
            "SELECT children_order FROM navigation_nodes WHERE id = %s AND user_id = %s",
            (parent_id, user_id),
        )
        if row:
            order = json.loads(row["children_order"]) if isinstance(row["children_order"], str) else (row["children_order"] or [])
            if child_id in order:
                order.remove(child_id)
                db.execute(
                    "UPDATE navigation_nodes SET children_order = %s, updated_at = NOW() WHERE id = %s AND user_id = %s",
                    (json.dumps(order), parent_id, user_id),
                )

    def _row_to_schema(self, row: dict) -> NavigationNodeSchema:
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

        return NavigationNodeSchema(
            id=row["id"],
            user_id=row["user_id"],
            parent_id=row.get("parent_id"),
            node_type=row.get("node_type", "dir"),
            kind=row.get("kind", "general"),
            name=row.get("name", "新节点"),
            user_name=row.get("user_name"),
            ai_name=row.get("ai_name") or "",
            children_order=_json_list(row.get("children_order")),
            conv_id=row.get("conv_id"),
            knowledge_area_id=row.get("knowledge_area_id"),
            path=_json_list(row.get("path")),
            created_at=row["created_at"].timestamp() if hasattr(row.get("created_at", 0), "timestamp") else time.time(),
            updated_at=row["updated_at"].timestamp() if hasattr(row.get("updated_at", 0), "timestamp") else time.time(),
            metadata=json.loads(row.get("metadata", "{}")) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


nav_svc = NavigationService()