"""
TreeDirectory — DirectoryNode CRUD

取代 tree_hierarchy.py 的 Partition/Domain/Topic/Conversation 四层模型。
所有节点统一用 DirectoryNode, 通过 node_type (dir/conv) 和 kind 区分。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.domain.cognitive.writer import CognitiveNodeWriter
from app.schemas.directory_node import DirectoryNode, MessageNode
from app.schemas.conversation import UserData
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)


class TreeDirectoryMixin:
    """DirectoryNode 层级 CRUD — 取代旧的 Partition/Domain/Topic/Conversation 四层模型"""

    ROOT_NAME = "我的知识库"

    # ── 根节点 ──

    def _ensure_root(self, user_id: str, data: UserData) -> DirectoryNode:
        """确保存在根目录节点。"""
        for dn in data.directory_nodes.values():
            if dn.node_type == "dir" and dn.parent_id is None:
                return dn
        root = DirectoryNode(
            user_id=user_id,
            parent_id=None,
            node_type="dir",
            kind="general",
            name=self.ROOT_NAME,
            path=[],
        )
        data.directory_nodes[root.id] = root
        return root

    def _ensure_temp_dir(self, user_id: str, data: UserData) -> DirectoryNode:
        """确保存在临时目录。"""
        for dn in data.directory_nodes.values():
            if dn.node_type == "dir" and dn.kind == "temp":
                return dn
        root = self._ensure_root(user_id, data)
        temp = DirectoryNode(
            user_id=user_id,
            parent_id=root.id,
            node_type="dir",
            kind="temp",
            name="💬 临时",
            path=root.path + [root.id],
        )
        root.add_child(temp.id)
        data.directory_nodes[temp.id] = temp
        return temp

    def _sync_cognitive_node(
        self, user_id: str, label: str, node_id: str, level: str,
    ) -> None:
        """创建 DirectoryNode 时联动创建 CognitiveNode。"""
        try:
            writer = CognitiveNodeWriter(user_id)
            writer.create_node(
                label=label,
                level=level,
                parent_id=None,
                node_type="explicit",
                created_by="user",
                is_visible=True,
            )
        except Exception:
            logger.debug("sync cognitive node skipped for %s (%s)", label, level)

    def _find_root(self, data: UserData) -> DirectoryNode | None:
        for dn in data.directory_nodes.values():
            if dn.node_type == "dir" and dn.parent_id is None:
                return dn
        return None

    # ── 创建节点 ──

    def create_dir(
        self, user_id: str, parent_id: str, name: str,
        kind: str = "general",
    ) -> DirectoryNode:
        """创建目录节点。"""
        data = get_data_repo().load(user_id)
        parent = data.directory_nodes.get(parent_id)
        if not parent:
            raise ValueError(f"父目录 {parent_id} 不存在")
        node = DirectoryNode(
            user_id=user_id, parent_id=parent_id,
            node_type="dir", kind=kind, name=name,
            path=parent.path + [parent.id],
        )
        parent.add_child(node.id)
        data.directory_nodes[node.id] = node
        get_data_repo().save(user_id, data)
        self._sync_cognitive_node(user_id, name, parent_id, level="domain")
        return node

    def create_conv(
        self, user_id: str, parent_id: str, name: str = "",
        kind: str = "general",
    ) -> DirectoryNode:
        """创建对话节点 + 初始根消息。"""
        data = get_data_repo().load(user_id)
        parent = data.directory_nodes.get(parent_id)
        if not parent:
            raise ValueError(f"父目录 {parent_id} 不存在")
        node = DirectoryNode(
            user_id=user_id, parent_id=parent_id,
            node_type="conv", kind=kind, name=name or "新对话",
            path=parent.path + [parent.id],
        )
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
        self._sync_cognitive_node(user_id, name or node.name, node.id, level="topic")
        return node

    def create_temp_conv(self, user_id: str) -> DirectoryNode:
        """创建临时对话。"""
        data = get_data_repo().load(user_id)
        temp_dir = self._ensure_temp_dir(user_id, data)
        node = self._create_conv_node(data, temp_dir.id, "临时会话", "temp")
        get_data_repo().save(user_id, data)
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
        if node.kind == "temp":
            raise ValueError("临时节点不可重命名")
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
        root = self._find_root(data) if root_id is None else data.directory_nodes.get(root_id)
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
    # 向后兼容桩 — 下个版本可删除
    # ═══════════════════════════════════════════════

    LEVELS = ["partition", "domain", "topic", "conversation"]

    LEVEL_CONFIG = {
        "partition": {
            "collection": "directory_nodes",
            "child_collection": "directory_nodes",
            "child_key": "parent_id",
            "parent_key": None,
            "factory": lambda name, emoji, parent_id=None, **kw: None,
            "auto_create_child": None,
        },
        "domain": {
            "collection": "directory_nodes",
            "child_collection": "directory_nodes",
            "child_key": "parent_id",
            "parent_key": "parent_id",
            "factory": lambda name, emoji, parent_id=None, **kw: None,
            "auto_create_child": None,
        },
        "topic": {
            "collection": "directory_nodes",
            "child_collection": "directory_nodes",
            "child_key": "parent_id",
            "parent_key": "parent_id",
            "factory": lambda name, emoji, parent_id=None, **kw: None,
            "auto_create_child": None,
        },
        "conversation": {
            "collection": "directory_nodes",
            "child_collection": None,
            "child_key": None,
            "parent_key": "parent_id",
            "factory": lambda name, emoji, **kw: None,
        },
    }

    def _get_collection(self, data, level: str) -> dict:
        """兼容桩：所有模型都映射到 directory_nodes。"""
        return data.directory_nodes

    def create_partition(self, user_id, name, subject="", direction="subject", emoji="💬"):
        root = self._ensure_root(user_id, get_data_repo().load(user_id))
        data = get_data_repo().load(user_id)
        root = self._ensure_root(user_id, data)
        return self.create_dir(user_id, root.id, name, "general")

    def delete_partition(self, user_id, partition_id):
        self.delete_node(user_id, partition_id)

    def create_domain(self, user_id, partition_id, name, emoji="📚"):
        return self.create_dir(user_id, partition_id, name, "general")

    def delete_domain(self, user_id, domain_id):
        self.delete_node(user_id, domain_id)

    def create_topic(self, user_id, domain_id, name, emoji="📝"):
        return self.create_dir(user_id, domain_id, name, "general")

    def delete_topic(self, user_id, topic_id):
        self.delete_node(user_id, topic_id)

    def create_conversation(self, user_id, topic_id="", name="", parent_id="", type="normal"):
        pid = parent_id or topic_id
        if not pid:
            data = get_data_repo().load(user_id)
            root = self._find_root(data)
            if root and root.children_order:
                pid = root.children_order[0]
        return self.create_conv(user_id, pid, name, "general")

    def delete_conversation(self, user_id, conv_id):
        self.delete_node(user_id, conv_id)

    def _ensure_conversation_parent_path(self, user_id, topic_id, data):
        """兼容桩 — no-op。"""
        pass

    def _ensure_temp_partition(self, user_id, data):
        """兼容桩 → 委托给 _ensure_temp_dir。"""
        temp_dir = self._ensure_temp_dir(user_id, data)
        return temp_dir, None

    def ensure_tree_exploration(self, user_id, partition_id, kg_node_id,
                                 kg_node_label, kg_node_level="concept"):
        """兼容桩 — 创建探索对话。"""
        return self.create_temp_conv(user_id)

    def create_temporary_conversation(self, user_id):
        """兼容桩 — 创建临时对话。"""
        return self.create_temp_conv(user_id)

    def migrate_temporary_conversation(self, user_id, conv_id, target_partition_id, target_type="normal"):
        """兼容桩 — 迁移临时对话到目标目录。"""
        return self.migrate_conv(user_id, conv_id, target_partition_id)
