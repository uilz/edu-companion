"""Tree message operations — add/update/modify/delete messages"""
from __future__ import annotations

import logging
import time
from uuid import uuid4

logger = logging.getLogger(__name__)

from app.schemas.conversation import Conversation, Domain, TextBlock, Topic, TreeNode, UserData
from app.services.common import get_data_repo


class TreeMessagesMixin:
    """消息 CRUD — add_message, update_message_content, modify_message, delete_message."""

    def add_message(
        self, user_id, partition_id, role, content_blocks,
        text_summary="", conversation_id="", agent_label="",
    ) -> TreeNode:
        data = self._get_data_repo().load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        if not conversation_id:
            # 空 conversation_id → 自动创建临时会话（挂到临时分区）
            from app.services.knowledge.tree_ops import tree_ops
            conv = tree_ops.create_temporary_conversation(user_id)
            # 重新加载数据（create_temporary_conversation 已 save）
            data = self._get_data_repo().load(user_id)
            partition = data.partitions.get(partition_id)
            logger.info("Auto-created temporary conversation %s in temp partition %s", conv.id[:8], conv.partition_id[:8])
        else:
            conv = data.conversations.get(conversation_id)
            if not conv:
                raise ValueError(f"Conversation {conversation_id} not found")

        # 使用对话所在的分区（临时会话在临时分区）
        effective_partition_id = conv.partition_id or partition_id
        effective_partition = data.partitions.get(effective_partition_id)

        node = TreeNode(
            parent_id=conv.path[-1] if conv.path else (effective_partition.root_id if effective_partition else partition.root_id),
            partition_id=effective_partition_id,
            conversation_id=conv.id,
            role=role,
            content_blocks=content_blocks,
            text_summary=text_summary,
            agent_label=agent_label,
        )
        parent = data.nodes.get(node.parent_id)
        if parent:
            parent.children_ids.append(node.id)
        conv.path.append(node.id)
        conv.last_message_at = time.time()
        if effective_partition:
            effective_partition.message_count += 1
            effective_partition.updated_at = time.time()
            effective_partition.last_active_at = time.time()
        data.nodes[node.id] = node

        self._get_data_repo().save(user_id, data)
        return node

    def move_subtree_to_conversation(
        self, user_id: str, source_node_id: str,
        target_domain_name: str, target_topic_name: str,
        source_conversation_id: str, target_partition_id: str,
    ) -> dict:
        """将 source_node 及其子节点从源会话移动到目标会话。
        自动创建领域/专题/会话，命名会话，清理空源会话。
        如果 source_node_id 为空，自动使用源会话中最后一条用户消息作为触发节点。"""
        data = self._get_data_repo().load(user_id)

        # 如果未指定触发节点，自动查找源会话中最后一条用户消息
        if not source_node_id:
            source_conv = data.conversations.get(source_conversation_id)
            if source_conv:
                for nid in reversed(source_conv.path):
                    n = data.nodes.get(nid)
                    if n and n.role == "user" and not n.is_deleted:
                        source_node_id = nid
                        break

        source_node = data.nodes.get(source_node_id)
        if not source_node:
            raise ValueError(f"Source node {source_node_id} not found")
        source_conv = data.conversations.get(source_conversation_id)
        if not source_conv:
            raise ValueError(f"Source conversation {source_conversation_id} not found")

        # 1. 收集所有要移动的节点 ID（source_node + 所有后代）
        moved_ids = set()
        def collect(nid: str):
            if nid in moved_ids:
                return
            moved_ids.add(nid)
            n = data.nodes.get(nid)
            if n:
                for cid in n.children_ids:
                    collect(cid)
        collect(source_node_id)

        # 2. 创建/查找目标层级（领域→专题→会话）
        existing_domain = None
        if target_domain_name:
            for d in data.domains.values():
                if d.partition_id == target_partition_id and d.name == target_domain_name:
                    existing_domain = d
                    break

        if not existing_domain and target_domain_name:
            domain_id = str(uuid4())
            existing_domain = Domain(
                id=domain_id, partition_id=target_partition_id,
                name=target_domain_name, emoji="📚",
            )
            data.domains[domain_id] = existing_domain

        domain_id = existing_domain.id if existing_domain else None

        existing_topic = None
        if domain_id and target_topic_name:
            for t in data.topics.values():
                if t.domain_id == domain_id and t.name == target_topic_name:
                    existing_topic = t
                    break
            if not existing_topic:
                topic_id = str(uuid4())
                existing_topic = Topic(
                    id=topic_id, domain_id=domain_id,
                    name=target_topic_name, emoji="📝",
                )
                data.topics[topic_id] = existing_topic

        topic_id = existing_topic.id if existing_topic else None

        # 3. 创建目标会话
        from .tree_hierarchy import TreeHierarchyMixin
        hierarchy = TreeHierarchyMixin()
        hierarchy._storage = self._get_data_repo()
        parent_id = topic_id or domain_id or target_partition_id
        target_conv = hierarchy._create_conversation_node(
            user_id, data, parent_id, name="",
        )
        # 更新 domain_id/topic_id
        if domain_id:
            target_conv.domain_id = domain_id
        if topic_id:
            target_conv.topic_id = topic_id
        target_conv.parent_type = "topic" if topic_id else ("domain" if domain_id else "partition")
        target_conv.is_active = True
        data.conversations[target_conv.id] = target_conv

        # 4. 从源会话中移除节点引用
        source_conv.path = [nid for nid in source_conv.path if nid not in moved_ids]
        # 将 source_node 从其父节点移除
        parent_node = data.nodes.get(source_node.parent_id)
        if parent_node and source_node_id in parent_node.children_ids:
            parent_node.children_ids.remove(source_node_id)
        # 子节点已经通过 collect 收集，不需要再处理 children_ids

        # 5. 将节点添加到目标会话
        # 保持原有父子顺序，移除根节点的占位 node_id（target_conv.path 目前只有 root）
        target_conv.path = []  # 清空 root placeholder

        # 按 conv.path 中的原始顺序排序 moved_ids
        ordered_moved = [nid for nid in source_conv.path + [] if nid in moved_ids]
        # 如果 source_conv.path 不够完整（可能有一些不在 path 中），补充剩余
        if len(ordered_moved) < len(moved_ids):
            ordered_moved = list(moved_ids)

        for nid in ordered_moved:
            node = data.nodes.get(nid)
            if node:
                node.conversation_id = target_conv.id
                node.partition_id = target_partition_id
                target_conv.path.append(nid)

        # 如果 target_conv.path 还是空的（原 path 中找不到），直接 append
        if not target_conv.path:
            for nid in moved_ids:
                node = data.nodes.get(nid)
                if node:
                    node.conversation_id = target_conv.id
                    node.partition_id = target_partition_id
                    target_conv.path.append(nid)

        # 6. 更新目标会话的 last_message_at
        if target_conv.path:
            last_node = data.nodes.get(target_conv.path[-1])
            if last_node:
                target_conv.last_message_at = last_node.timestamp
        target_conv.summary_dirty = True

        # 7. 自动命名新会话（取第一条用户消息的摘要）
        conv_name = ""
        for nid in target_conv.path:
            node = data.nodes.get(nid)
            if node and node.role == "user" and node.text_summary:
                conv_name = node.text_summary[:30]
                break
        if not conv_name and target_topic_name:
            conv_name = target_topic_name
        if conv_name:
            target_conv.name = conv_name

        data.conversations[target_conv.id] = target_conv

        # 8. 如果源会话空了，删除
        source_deleted = False
        active_ids = [nid for nid in source_conv.path if not data.nodes.get(nid, TreeNode(is_deleted=True)).is_deleted]
        if not active_ids:
            # 标记删除整个会话
            for nid in source_conv.path:
                n = data.nodes.get(nid)
                if n:
                    n.is_deleted = True
            source_conv.is_active = False
            source_deleted = True

        self._get_data_repo().save(user_id, data)
        return {
            "target_conversation_id": target_conv.id,
            "target_partition_id": target_partition_id,
            "moved_count": len(moved_ids),
            "source_deleted": source_deleted,
            "conversation_name": conv_name or target_conv.name,
        }

    def update_message_content(self, user_id: str, message_id: str, text: str) -> None:
        data = self._get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            return

        node.content_blocks = [TextBlock(text=text)]
        node.text_summary = text

        self._get_data_repo().save(user_id, data)

    def modify_message(
        self, user_id, message_id, new_content_blocks, new_text_summary="",
    ) -> TreeNode:
        data = self._get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            raise ValueError(f"Message {message_id} not found")

        new_node = TreeNode(
            parent_id=node.parent_id, partition_id=node.partition_id,
            conversation_id=node.conversation_id, role=node.role,
            content_blocks=new_content_blocks, text_summary=new_text_summary,
        )
        parent = data.nodes.get(node.parent_id)
        if parent and new_node.id not in parent.children_ids:
            parent.children_ids.append(new_node.id)
        data.nodes[new_node.id] = new_node

        # 直接追加到 conv.path 末尾，不截断
        conv = data.conversations.get(node.conversation_id)
        if conv:
            conv.path.append(new_node.id)
            conv.summary_dirty = True

        self._get_data_repo().save(user_id, data)
        return new_node

    def delete_message(self, user_id, message_id) -> None:
        data = self._get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            return

        deleted_ids = set()

        def collect(nid: str):
            n = data.nodes.get(nid)
            if not n or nid in deleted_ids:
                return
            deleted_ids.add(nid)
            for cid in n.children_ids:
                collect(cid)

        collect(message_id)

        for nid in deleted_ids:
            n = data.nodes.get(nid)
            if not n:
                continue
            n.is_deleted = True
            parent = data.nodes.get(n.parent_id)
            if parent and nid in parent.children_ids:
                parent.children_ids.remove(nid)

        conv = data.conversations.get(node.conversation_id)
        if conv:
            conv.summary_dirty = True
            conv.path = [nid for nid in conv.path if nid not in deleted_ids]

        self._get_data_repo().save(user_id, data)
