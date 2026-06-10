"""Tree message operations — add/update/modify/delete messages"""
from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)

from app.schemas.conversation import TextBlock, TreeNode, UserData
from app.services.common import get_data_repo


class TreeMessagesMixin:
    """消息 CRUD — add_message, update_message_content, modify_message, delete_message."""

    def add_message(
        self, user_id, partition_id, role, content_blocks,
        text_summary="", conversation_id="",
    ) -> TreeNode:
        data = self._get_data_repo().load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        if not conversation_id:
            conv = None
            # 新路径：通过 conversation.partition_id + is_active 查找
            for c in data.conversations.values():
                if c.partition_id == partition_id and c.is_active:
                    conv = c
                    break
            # 回退旧路径：通过 topic → domain → partition 遍历
            if not conv:
                for topic in data.topics.values():
                    domain = data.domains.get(topic.domain_id)
                    if domain and domain.partition_id == partition_id:
                        cid = topic.active_conversation_id
                        if cid and cid in data.conversations:
                            conv = data.conversations[cid]
                            break
            if not conv:
                raise ValueError("No active conversation in partition")
        else:
            conv = data.conversations.get(conversation_id)
            if not conv:
                raise ValueError(f"Conversation {conversation_id} not found")

        node = TreeNode(
            parent_id=conv.path[-1] if conv.path else partition.root_id,
            partition_id=partition_id,
            conversation_id=conv.id,
            role=role,
            content_blocks=content_blocks,
            text_summary=text_summary,
        )
        parent = data.nodes.get(node.parent_id)
        if parent:
            parent.children_ids.append(node.id)
        conv.path.append(node.id)
        conv.last_message_at = time.time()
        partition.message_count += 1
        partition.updated_at = time.time()
        partition.last_active_at = time.time()
        data.nodes[node.id] = node

        self._get_data_repo().save(user_id, data)
        return node

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
