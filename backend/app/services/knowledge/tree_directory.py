"""
TreeDirectory — DirectoryNode CRUD

取代 tree_hierarchy.py 的 Partition/Domain/Topic/Conversation 四层模型。
所有节点统一用 DirectoryNode, 通过 node_type (dir/conv) 和 kind 区分。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.schemas.directory_node import DirectoryNode, MessageNode
from app.schemas.conversation import UserData
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)


class TreeDirectoryMixin:
    """DirectoryNode 层级 CRUD — 取代旧的 Partition/Domain/Topic/Conversation 四层模型"""

    ROOT_NAME = "我的知识库"

    # ── 创建节点 ──

    def create_dir(
        self, user_id: str, parent_id: str | None = None, name: str = "",
        kind: str = "general",
    ) -> DirectoryNode:
        """创建目录节点。parent_id=None 表示根级目录（未分类）。"""
        data = get_data_repo().load(user_id)
        path: list[str] = []
        if parent_id:
            parent = data.directory_nodes.get(parent_id)
            if not parent:
                raise ValueError(f"父目录 {parent_id} 不存在")
            if parent.node_type != "dir":
                raise ValueError(f"父节点 {parent_id} 不是目录类型，不能创建子目录")
            path = parent.path + [parent.id]
        node = DirectoryNode(
            user_id=user_id, parent_id=parent_id,
            node_type="dir", kind=kind, name=name or "新文件夹",
            path=path,
        )
        if parent_id:
            parent = data.directory_nodes.get(parent_id)
            if parent:
                parent.add_child(node.id)
        data.directory_nodes[node.id] = node
        get_data_repo().save(user_id, data)
        # 目录与知识树已解耦，不再联动创建 CognitiveNode
        return node

    def create_conv(
        self, user_id: str, parent_id: str | None = None, name: str = "",
        kind: str = "general",
    ) -> DirectoryNode:
        """创建对话节点 + 初始根消息。parent_id=None 表示未分类。"""
        data = get_data_repo().load(user_id)
        path: list[str] = []
        if parent_id:
            parent = data.directory_nodes.get(parent_id)
            if not parent:
                raise ValueError(f"父目录 {parent_id} 不存在")
            if parent.node_type != "dir":
                raise ValueError(f"父节点 {parent_id} 不是目录类型，不能创建会话")
            path = parent.path + [parent.id]
        node = DirectoryNode(
            user_id=user_id, parent_id=parent_id,
            node_type="conv", kind=kind, name=name or "新对话",
            path=path,
        )
        if parent_id:
            parent = data.directory_nodes.get(parent_id)
            if parent:
                parent.add_child(node.id)
        data.directory_nodes[node.id] = node

        # 根消息节点
        root_msg = MessageNode(
            directory_id=node.id, parent_id=None,
            role="assistant", content="", text_summary=node.name,
        )
        node.conv_message_ids.append(root_msg.id)
        data.nodes[root_msg.id] = root_msg

        get_data_repo().save(user_id, data)
        # 目录与知识树已解耦，不再联动创建 CognitiveNode
        return node

    def _create_conv_node(
        self, data: UserData, parent_id: str, name: str = "",
        kind: str = "general",
    ) -> DirectoryNode:
        parent = data.directory_nodes.get(parent_id)
        node = DirectoryNode(
            user_id=data.user_id, parent_id=parent_id,
            node_type="conv", kind=kind, name=name or "新对话",
            path=parent.path + [parent.id] if parent else [],
        )
        if parent:
            parent.add_child(node.id)
        data.directory_nodes[node.id] = node
        root_msg = MessageNode(
            directory_id=node.id, parent_id=None,
            role="assistant", content="", text_summary=node.name,
        )
        node.conv_message_ids.append(root_msg.id)
        data.nodes[root_msg.id] = root_msg
        return node

    # ── 删除 ──

    def delete_node(self, user_id: str, node_id: str) -> None:
        """递归删除节点及其子孙。"""
        data = get_data_repo().load(user_id)
        self._delete_recursive(node_id, data)
        get_data_repo().save(user_id, data)

    def _delete_recursive(self, node_id: str, data: UserData) -> None:
        node = data.directory_nodes.pop(node_id, None)
        if not node:
            return
        # 递归删除子目录/子对话
        for child_id in list(node.children_order):
            self._delete_recursive(child_id, data)
        # 删除对话下的消息
        if node.node_type == "conv":
            for mid in node.conv_message_ids:
                data.nodes.pop(mid, None)
        # 从父节点 children_order 移除
        if node.parent_id:
            parent = data.directory_nodes.get(node.parent_id)
            if parent:
                parent.remove_child(node_id)

    # ── 重命名 ──

    def rename_node(self, user_id: str, node_id: str, name: str) -> DirectoryNode:
        """重命名节点。"""
        data = get_data_repo().load(user_id)
        node = data.directory_nodes.get(node_id)
        if not node:
            raise ValueError(f"节点 {node_id} 不存在")
        node.user_name = name
        node.updated_at = time.time()
        get_data_repo().save(user_id, data)
        return node

    # ── 查询 ──

    def get_node(self, user_id: str, node_id: str) -> DirectoryNode | None:
        data = get_data_repo().load(user_id)
        return data.directory_nodes.get(node_id)

    def list_children(
        self, user_id: str, parent_id: str,
    ) -> list[DirectoryNode]:
        """按 children_order 列出子节点。"""
        data = get_data_repo().load(user_id)
        parent = data.directory_nodes.get(parent_id)
        if not parent:
            return []
        order_map = {cid: i for i, cid in enumerate(parent.children_order)}
        nodes = []
        for dn in data.directory_nodes.values():
            if dn.parent_id == parent_id:
                nodes.append((order_map.get(dn.id, 999), dn))
        nodes.sort(key=lambda x: x[0])
        return [dn for _, dn in nodes]

    # ── 树结构（前端侧边栏用） ──

    def build_tree(
        self, user_id: str, root_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """返回可嵌套的目录树。"""
        data = get_data_repo().load(user_id)
        if root_id is None:
            # 找根节点（parent_id 为 None 的 dir 节点）
            root = next(
                (dn for dn in data.directory_nodes.values()
                 if dn.node_type == "dir" and dn.parent_id is None),
                None,
            )
        else:
            root = data.directory_nodes.get(root_id)
        if not root:
            return []
        return [self._to_dict(dn, data) for dn in self._iter_children(root, data)]

    def _to_dict(self, node: DirectoryNode, data: UserData) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": node.id,
            "name": node.display_name,
            "node_type": node.node_type,
            "kind": node.kind,
            "parent_id": node.parent_id,
        }
        if node.node_type == "dir":
            d["children"] = [
                self._to_dict(c, data)
                for c in self._iter_children(node, data)
            ]
        return d

    def _iter_children(self, parent: DirectoryNode, data: UserData):
        order_map = {cid: i for i, cid in enumerate(parent.children_order)}
        ordered = [
            data.directory_nodes[cid]
            for cid in parent.children_order
            if cid in data.directory_nodes
        ]
        # 补充不在 children_order 中但仍挂在此父节点下的
        extra = sorted(
            [
                dn for dn in data.directory_nodes.values()
                if dn.parent_id == parent.id and dn.id not in order_map
            ],
            key=lambda x: x.created_at,
        )
        return ordered + extra

    # ── 便捷辅助 ──

    def find_conv(self, data: UserData, conv_id: str) -> DirectoryNode | None:
        """根据 ID 查找 conv 节点。"""
        node = data.directory_nodes.get(conv_id)
        if node and node.node_type == "conv":
            return node
        return None

    def find_active_conv(
        self, user_id: str, dir_id: str,
    ) -> DirectoryNode | None:
        """在目录下找最新活跃对话。"""
        data = get_data_repo().load(user_id)
        convs = [
            dn for dn in data.directory_nodes.values()
            if dn.parent_id == dir_id and dn.node_type == "conv"
        ]
        if not convs:
            return None
        convs.sort(key=lambda x: x.updated_at, reverse=True)
        return convs[0]

    def migrate_conv(
        self, user_id: str, conv_id: str, target_dir_id: str,
    ) -> DirectoryNode:
        """将对话迁移到目标目录下。"""
        data = get_data_repo().load(user_id)
        conv = data.directory_nodes.get(conv_id)
        if not conv or conv.node_type != "conv":
            raise ValueError(f"对话 {conv_id} 不存在")
        target = data.directory_nodes.get(target_dir_id)
        if not target or target.node_type != "dir":
            raise ValueError(f"目标目录 {target_dir_id} 不存在")

        # 从原父节点移除
        if conv.parent_id:
            old_parent = data.directory_nodes.get(conv.parent_id)
            if old_parent:
                old_parent.remove_child(conv_id)

        # 挂到新父节点
        conv.parent_id = target_dir_id
        conv.path = target.path + [target.id]
        conv.kind = "general"
        target.add_child(conv_id)
        conv.updated_at = time.time()
        get_data_repo().save(user_id, data)
        return conv

    # ═══════════════════════════════════════════════
    # (Old 4-layer compatibility stubs removed)
    # ═══════════════════════════════════════════════
