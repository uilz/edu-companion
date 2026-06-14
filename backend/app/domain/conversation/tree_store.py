"""
TreeStore — 对话树聚合根 + 查询/变更分离

DirectoryNode 版本：所有查询和变更统一走 DirectoryNode。
向下兼容：提供旧接口 get_partition/domain/topic/conversation 桩方法。

查询/变更分离：
  TreeQuery   → 只读，零副作用
  TreeMutate  → 写操作，产出领域事件
  TreeStore   → 聚合根，组合两者

Sync 不再从 Mixin 隐式调用 — TreeMutate 产出事件，SyncHook 独立订阅。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.schemas.directory_node import DirectoryNode
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# DataStorage Protocol — 可注入存储
# ═══════════════════════════════════════════════

class DataStorage(Protocol):
    """存储契约 — load / save 两个方法"""

    def load(self, user_id: str) -> Any: ...

    def save(self, user_id: str, data: Any) -> None: ...


# ═══════════════════════════════════════════════
# TreeQuery — 只读查询
# ═══════════════════════════════════════════════

@dataclass
class PathSegment:
    """目录路径信息（前端侧边栏 + 面包屑用）"""
    root_id: str = ""
    root_name: str = ""
    dir_id: str = ""
    dir_name: str = ""
    conv_id: str = ""
    conv_name: str = ""


@dataclass
class AncestorChain:
    """节点祖先链"""
    path: list[tuple[str, str, str]] = field(default_factory=list)  # (type, id, name)


class TreeQuery:
    """只读查询 — 零副作用"""

    def __init__(self, storage: DataStorage) -> None:
        self._storage = storage
        self._data_repo = get_data_repo()
        self._tree_ops = None

    @property
    def _ops(self):
        """懒加载 tree_ops，避免循环导入"""
        if self._tree_ops is None:
            from app.services.knowledge.tree_ops import tree_ops
            self._tree_ops = tree_ops
        return self._tree_ops

    # ── DirectoryNode 查询 ──

    def get_node(self, user_id: str, node_id: str) -> DirectoryNode | None:
        data = self._data_repo.load(user_id)
        return data.directory_nodes.get(node_id)

    def get_directory_node(self, user_id: str, node_id: str) -> DirectoryNode | None:
        return self.get_node(user_id, node_id)

    def list_children(self, user_id: str, parent_id: str) -> list[DirectoryNode]:
        """列出目录子节点。"""
        return self._ops.list_children(user_id, parent_id)

    def list_messages(self, user_id: str, conv_id: str, offset: int = 0, limit: int = 50) -> list:
        """列出对话消息。"""
        data = self._data_repo.load(user_id)
        conv_node = data.directory_nodes.get(conv_id)
        if not conv_node or conv_node.node_type != "conv":
            return []
        msg_ids = conv_node.conv_message_ids[offset: offset + limit]
        messages = []
        for mid in msg_ids:
            node = data.nodes.get(mid)
            if node:
                messages.append(node)
        return messages

    def get_ancestor_chain(self, user_id: str, node_id: str) -> AncestorChain:
        """获取节点所在祖先链。"""
        data = self._data_repo.load(user_id)
        chain = AncestorChain()
        path: list[tuple[str, str, str]] = []
        current_id = node_id

        for _ in range(50):  # 安全上限
            node = data.directory_nodes.get(current_id)
            if not node:
                break
            typ = node.node_type  # "dir" | "conv"
            pid = node.parent_id or ""
            path.append((typ, current_id, node.display_name))
            if pid:
                current_id = pid
            else:
                break

        path.reverse()
        chain.path = path
        return chain

    def list_path(self, user_id: str, node_id: str) -> PathSegment:
        """查询节点所在目录路径（面包屑导航用）。"""
        chain = self.get_ancestor_chain(user_id, node_id)
        seg = PathSegment()
        for typ, nid, name in chain.path:
            if typ == "dir" and not seg.dir_id:
                seg.dir_id = nid
                seg.dir_name = name
            elif typ == "conv":
                seg.conv_id = nid
                seg.conv_name = name
        # 第一个 dir 作为 root
        for typ, nid, name in chain.path:
            if typ == "dir":
                seg.root_id = nid
                seg.root_name = name
                break
        return seg

    def find_active_conversation(self, user_id: str, dir_id: str) -> DirectoryNode | None:
        """查找目录下最新活跃对话。"""
        return self._ops.find_active_conv(user_id, dir_id)

    # ── 旧接口兼容桩 ──

    def get_conversation(self, user_id: str, cid: str) -> Any | None:
        return self.get_node(user_id, cid)

    def get_partition(self, user_id: str, pid: str) -> Any | None:
        return self.get_node(user_id, pid)

    def get_domain(self, user_id: str, did: str) -> Any | None:
        return self.get_node(user_id, did)

    def get_topic(self, user_id: str, tid: str) -> Any | None:
        return self.get_node(user_id, tid)


# ═══════════════════════════════════════════════
# TreeMutate — 写操作（产出事件）
# ═══════════════════════════════════════════════

class TreeMutate:
    """写操作 — 产出领域事件"""

    def __init__(self, storage: DataStorage) -> None:
        self._storage = storage
        self._data_repo = get_data_repo()

    def create_dir(self, user_id: str, parent_id: str, name: str, kind: str = "general") -> str:
        """创建目录 → 返回 dir_id"""
        node = self._ops.create_dir(user_id, parent_id, name, kind)
        return node.id

    def create_conv(self, user_id: str, parent_id: str, name: str = "", kind: str = "general") -> str:
        """创建对话 → 返回 conv_id"""
        node = self._ops.create_conv(user_id, parent_id, name, kind)
        return node.id

    def add_message(
        self, user_id: str, conv_id: str, role: str,
        text: str = "", blocks: list | None = None,
        agent_label: str = "",
    ) -> str | None:
        """添加消息到对话 → 返回 message_id"""
        import uuid
        from app.schemas.conversation import TextBlock
        from app.schemas.directory_node import MessageNode

        data = self._data_repo.load(user_id)
        conv = data.directory_nodes.get(conv_id)
        if not conv or conv.node_type != "conv":
            logger.warning("TreeMutate: conv %s not found", conv_id[:8])
            return None

        mid = str(uuid.uuid4())
        text_content = ""
        if text:
            text_content = text
        elif blocks:
            for b in blocks:
                if isinstance(b, dict) and b.get("type") == "text":
                    text_content = b.get("text", "")
                    break

        node = MessageNode(
            id=mid, directory_id=conv_id,
            parent_id=conv.conv_message_ids[-1] if conv.conv_message_ids else None,
            role=role, content=text_content,
        )
        data.nodes[mid] = node
        conv.conv_message_ids.append(mid)
        conv.updated_at = __import__("time").time()
        self._data_repo.save(user_id, data)
        return mid

    def delete_node(self, user_id: str, node_id: str) -> bool:
        """删除目录/对话节点。"""
        data = self._data_repo.load(user_id)
        if node_id not in data.directory_nodes:
            return False
        self._ops.delete_node(user_id, node_id)
        return True

    def rename_node(self, user_id: str, node_id: str, name: str) -> bool:
        """重命名节点。"""
        try:
            self._ops.rename_node(user_id, node_id, name)
            return True
        except ValueError:
            return False

    # ── 旧接口兼容桩 ──

    @property
    def _ops(self):
        if not hasattr(self, "_tree_ops"):
            from app.services.knowledge.tree_ops import tree_ops
            self._tree_ops = tree_ops
        return self._tree_ops

    def create_partition(self, user_id, name, subject="", emoji=""):
        from app.services.knowledge.tree_ops import tree_ops
        root = tree_ops._ensure_root(user_id, tree_ops._get_data_repo().load(user_id))
        # save 后再拉起
        data = tree_ops._get_data_repo().load(user_id)
        root = tree_ops._ensure_root(user_id, data)
        node = tree_ops.create_dir(user_id, root.id, name, "general")
        return node

    def create_domain(self, user_id, partition_id, name, emoji=""):
        node = self._ops.create_dir(user_id, partition_id, name, "general")
        return node

    def create_topic(self, user_id, domain_id, name, emoji=""):
        node = self._ops.create_dir(user_id, domain_id, name, "general")
        return node

    def create_conversation(self, user_id, topic_id="", parent_id="", name="", type="normal"):
        pid = parent_id or topic_id
        if not pid:
            data = self._data_repo.load(user_id)
            # 找个根目录
            for dn in data.directory_nodes.values():
                if dn.node_type == "dir" and dn.parent_id is None:
                    pid = dn.id
                    break
        node = self._ops.create_conv(user_id, pid, name, "general")
        return node

    def delete_conversation(self, user_id, conv_id):
        return self.delete_node(user_id, conv_id)

    def rename_partition(self, user_id, pid, name):
        return self.rename_node(user_id, pid, name)

    def rename_domain(self, user_id, did, name):
        return self.rename_node(user_id, did, name)

    def rename_topic(self, user_id, tid, name):
        return self.rename_node(user_id, tid, name)


# ═══════════════════════════════════════════════
# TreeStore — 聚合根
# ═══════════════════════════════════════════════

class TreeStore:
    """对话树聚合根 — 组合 TreeQuery + TreeMutate"""

    def __init__(self, storage: DataStorage | None = None) -> None:
        store = storage or get_data_repo()
        self.query = TreeQuery(store)
        self.mutate = TreeMutate(store)

    @property
    def get_node(self):
        return self.query.get_node

    @property
    def get_conversation(self):
        return self.query.get_conversation

    @property
    def list_path(self):
        return self.query.list_path

    @property
    def find_active_conversation(self):
        return self.query.find_active_conversation

    @property
    def auto_resolve(self):
        return self.query.auto_resolve


# 全局单例（兼容旧 tree_ops 模式）
_tree_store: TreeStore | None = None


def get_tree_store() -> TreeStore:
    global _tree_store
    if _tree_store is None:
        _tree_store = TreeStore()
    return _tree_store


def set_tree_store(store: TreeStore) -> None:
    global _tree_store
    _tree_store = store
