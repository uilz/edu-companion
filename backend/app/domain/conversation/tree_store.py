"""
TreeStore — 对话树聚合根 + 查询/变更分离

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
    """PDTC 全链路信息（前端侧边栏 + 面包屑用）"""
    partition_id: str = ""
    partition_name: str = ""
    domain_id: str = ""
    domain_name: str = ""
    topic_id: str = ""
    topic_name: str = ""
    conversation_id: str = ""
    conversation_name: str = ""


@dataclass
class AncestorChain:
    """节点祖先链"""
    partition_id: str = ""
    domain_id: str = ""
    topic_id: str = ""
    conversation_id: str = ""
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

    def get_node(self, user_id: str, node_id: str) -> Any | None:
        data = self._data_repo.load(user_id)
        return data.nodes.get(node_id)

    def get_conversation(self, user_id: str, cid: str) -> Any | None:
        data = self._data_repo.load(user_id)
        return data.conversations.get(cid)

    def get_partition(self, user_id: str, pid: str) -> Any | None:
        data = self._data_repo.load(user_id)
        return data.partitions.get(pid)

    def get_domain(self, user_id: str, did: str) -> Any | None:
        data = self._data_repo.load(user_id)
        return data.domains.get(did)

    def get_topic(self, user_id: str, tid: str) -> Any | None:
        data = self._data_repo.load(user_id)
        return data.topics.get(tid)

    def list_messages(self, user_id: str, cid: str, offset: int = 0, limit: int = 50) -> list:
        """列出对话消息"""
        data = self._data_repo.load(user_id)
        conv = data.conversations.get(cid)
        if not conv:
            return []
        # 收集对话的消息
        messages = []
        idx = offset
        while idx < len(conv.message_ids) and idx - offset < limit:
            node = data.nodes.get(conv.message_ids[idx])
            if node:
                messages.append(node)
            idx += 1
        return messages

    def list_children(self, user_id: str, parent_id: str, level: str = "") -> list:
        """列出自节点（按层级）"""
        data = self._data_repo.load(user_id)
        results = []
        for node in data.nodes.values():
            if node.parent_id == parent_id:
                if not level or node.parent_type == level:
                    results.append(node)
        return results

    def get_ancestor_chain(self, user_id: str, node_id: str) -> AncestorChain:
        """获取节点所在完整 PDTC 祖先链"""
        data = self._data_repo.load(user_id)
        chain = AncestorChain()
        path = []
        current_id = node_id

        for _ in range(20):  # 安全上限
            node = data.nodes.get(current_id)
            if not node:
                break
            typ = node.parent_type or ""
            pid = node.parent_id or ""
            name = ""
            if typ == "conversation":
                conv = data.conversations.get(pid)
                name = conv.name if conv else ""
                chain.conversation_id = pid
            elif typ == "topic":
                topic = data.topics.get(pid)
                name = topic.name if topic else ""
                chain.topic_id = pid
            elif typ == "domain":
                domain = data.domains.get(pid)
                name = domain.name if domain else ""
                chain.domain_id = pid
            elif typ == "partition":
                part = data.partitions.get(pid)
                name = part.name if part else ""
                chain.partition_id = pid

            if typ:
                path.append((typ, pid, name))
            current_id = pid

        path.reverse()
        chain.path = path
        return chain

    def list_path(self, user_id: str, node_id: str) -> PathSegment:
        """查询节点所在完整 PDTC 路径（面包屑导航用）"""
        chain = self.get_ancestor_chain(user_id, node_id)
        seg = PathSegment()
        for typ, pid, name in chain.path:
            if typ == "partition":
                seg.partition_id = pid
                seg.partition_name = name
            elif typ == "domain":
                seg.domain_id = pid
                seg.domain_name = name
            elif typ == "topic":
                seg.topic_id = pid
                seg.topic_name = name
            elif typ == "conversation":
                seg.conversation_id = pid
                seg.conversation_name = name
        return seg

    def find_active_conversation(self, user_id: str, partition_id: str) -> Any | None:
        """查找分区下最新活跃对话"""
        data = self._data_repo.load(user_id)
        latest = None
        latest_ts = ""
        for conv in data.conversations.values():
            if conv.partition_id == partition_id and getattr(conv, "status", "") != "archived":
                if not latest_ts or str(conv.updated_at) > latest_ts:
                    latest_ts = str(conv.updated_at)
                    latest = conv
        return latest

    async def auto_resolve(
        self,
        user_id: str, partition_id: str, text: str, node_id: str = "",
    ) -> dict | None:
        """自动分类 → 返回 ResolveRoute"""
        try:
            from app.services.common.classifier import classifier

            data = self._data_repo.load(user_id)
            target = data.conversations.get(node_id) if node_id else None
            topic_id = target.topic_id if target else ""
            domain_id = ""
            if topic_id:
                topic = data.topics.get(topic_id)
                if topic:
                    domain_id = topic.domain_id

            route = await classifier.classify_and_resolve(
                user_id, partition_id, text, domain_id, topic_id,
            )
            if route:
                return {
                    "partition_id": route.partition_id,
                    "domain_id": route.domain_id,
                    "topic_id": route.topic_id,
                    "domain_name": route.domain_name,
                    "topic_name": route.topic_name,
                    "confidence": route.confidence,
                    "is_new": route.is_new,
                }
        except Exception:
            logger.debug("auto_resolve failed", exc_info=True)
        return None


# ═══════════════════════════════════════════════
# TreeMutate — 写操作（产出事件）
# ═══════════════════════════════════════════════

class TreeMutate:
    """写操作 — 产出领域事件"""

    def __init__(self, storage: DataStorage) -> None:
        self._storage = storage
        self._data_repo = get_data_repo()

    def create_partition(
        self, user_id: str, name: str, subject: str = "", emoji: str = "",
    ) -> str:
        """创建分区 → 返回 partition_id"""
        import uuid
        from app.schemas.conversation import Partition

        pid = str(uuid.uuid4())
        data = self._data_repo.load(user_id)
        partition = Partition(
            id=pid, name=name, subject=subject, emoji=emoji,
            direction="subject",
        )
        data.partitions[pid] = partition
        data.root_ids.append(pid)
        self._data_repo.save(user_id, data)
        logger.info("TreeMutate: partition created %s [%s]", pid[:8], name)
        return pid

    def create_domain(self, user_id: str, partition_id: str, name: str, emoji: str = "") -> str:
        """创建领域"""
        import uuid
        from app.schemas.conversation import Domain

        did = str(uuid.uuid4())
        data = self._data_repo.load(user_id)
        domain = Domain(id=did, name=name, partition_id=partition_id, emoji=emoji)
        data.domains[did] = domain
        self._data_repo.save(user_id, data)
        return did

    def create_topic(self, user_id: str, domain_id: str, name: str, emoji: str = "") -> str:
        """创建专题"""
        import uuid
        from app.schemas.conversation import Topic

        tid = str(uuid.uuid4())
        data = self._data_repo.load(user_id)
        topic = Topic(id=tid, name=name, domain_id=domain_id, emoji=emoji)
        data.topics[tid] = topic
        self._data_repo.save(user_id, data)
        return tid

    def create_conversation(
        self, user_id: str, topic_id: str = "", parent_id: str = "",
        parent_type: str = "", conv_type: str = "normal", name: str = "",
    ) -> str:
        """创建对话"""
        import uuid
        from datetime import datetime, timezone
        from app.schemas.conversation import Conversation

        cid = str(uuid.uuid4())
        data = self._data_repo.load(user_id)

        # 推断 partition_id
        partition_id = ""
        if parent_type == "partition":
            partition_id = parent_id
        elif parent_type == "domain":
            dom = data.domains.get(parent_id)
            if dom:
                partition_id = dom.partition_id
        elif parent_type == "topic":
            top = data.topics.get(parent_id)
            if top:
                dom = data.domains.get(top.domain_id)
                if dom:
                    partition_id = dom.partition_id

        conv = Conversation(
            id=cid, name=name or "新对话", type=conv_type,
            partition_id=partition_id, topic_id=topic_id,
            parent_id=parent_id, parent_type=parent_type,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        data.conversations[cid] = conv
        data.node_index[cid] = []

        # 在父节点下添加引用
        if parent_type == "topic" and parent_id:
            topic = data.topics.get(parent_id)
            if topic:
                topic.conversation_ids.append(cid)

        self._data_repo.save(user_id, data)
        return cid

    def add_message(
        self, user_id: str, conversation_id: str, role: str,
        text: str = "", blocks: list | None = None, agent_label: str = "",
    ) -> str | None:
        """添加消息到对话 → 返回 message_id"""
        import uuid
        from datetime import datetime, timezone
        from app.schemas.conversation import TreeNode, TextBlock

        data = self._data_repo.load(user_id)
        conv = data.conversations.get(conversation_id)
        if not conv:
            logger.warning("TreeMutate: conversation %s not found", conversation_id[:8])
            return None

        mid = str(uuid.uuid4())
        node = TreeNode(
            id=mid, role=role, parent_id=conversation_id,
            parent_type="conversation", agent_label=agent_label,
            created_at=datetime.now(timezone.utc),
        )

        if text:
            node.content_blocks = [TextBlock(type="text", text=text)]
        elif blocks:
            node.content_blocks = [TextBlock(**b) if isinstance(b, dict) else b for b in blocks]

        data.nodes[mid] = node
        conv.message_ids.append(mid)
        conv.updated_at = datetime.now(timezone.utc)
        self._data_repo.save(user_id, data)
        return mid

    def delete_conversation(self, user_id: str, cid: str) -> bool:
        """删除对话及其消息"""
        data = self._data_repo.load(user_id)
        conv = data.conversations.pop(cid, None)
        if not conv:
            return False
        # 删除关联消息
        for mid in conv.message_ids:
            data.nodes.pop(mid, None)
        self._data_repo.save(user_id, data)
        return True

    def rename_partition(self, user_id: str, pid: str, name: str) -> bool:
        data = self._data_repo.load(user_id)
        part = data.partitions.get(pid)
        if not part:
            return False
        part.name = name
        self._data_repo.save(user_id, data)
        return True

    def rename_domain(self, user_id: str, did: str, name: str) -> bool:
        data = self._data_repo.load(user_id)
        dom = data.domains.get(did)
        if not dom:
            return False
        dom.name = name
        self._data_repo.save(user_id, data)
        return True

    def rename_topic(self, user_id: str, tid: str, name: str) -> bool:
        data = self._data_repo.load(user_id)
        top = data.topics.get(tid)
        if not top:
            return False
        top.name = name
        self._data_repo.save(user_id, data)
        return True


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