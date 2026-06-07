"""Tree context operations — partition context query / switch conversation"""
from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)

from app.schemas.conversation import Conversation, UserData
from app.services.common.storage import storage


class TreeContextMixin:
    """获取上下文 / 切换活跃对话."""

    _storage = storage

    def get_partition_context(self, user_id: str, partition_id: str) -> dict:
        data = self._storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        messages = []
        conv = None
        # 新路径：通过 conversation.partition_id 查找活跃对话
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
                    if cid:
                        conv = data.conversations.get(cid)
                    break
        if conv:
            for nid in conv.path:
                node = data.nodes.get(nid)
                if node and not node.is_deleted:
                    messages.append(node)

        return {
            "partition": partition,
            "conversation": conv,
            "messages": messages,
            "context_summary": partition.context_summary,
        }

    def switch_conversation(
        self, user_id: str, conversation_id: str,
        partition_id: str | None = None,
    ) -> Conversation:
        """切换活跃对话。使用 conversation.partition_id 查找同级别对话并切换。"""
        data = self._storage.load(user_id)
        conv = data.conversations.get(conversation_id)
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        pid = partition_id or conv.partition_id

        if pid:
            # 新路径：按 partition_id 过滤
            matched_any = False
            for c in data.conversations.values():
                if c.partition_id == pid:
                    matched_any = True
                    if c.id != conversation_id:
                        c.is_active = False
            # 回退：旧数据没有 partition_id，通过 topic 链查找
            if not matched_any:
                topic_ids_in_partition = {
                    t.id for t in data.topics.values()
                    for d in data.domains.values()
                    if d.id == t.domain_id and d.partition_id == pid
                }
                for c in data.conversations.values():
                    if c.topic_id in topic_ids_in_partition and c.id != conversation_id:
                        c.is_active = False
        elif conv.parent_type == "topic":
            # 回退旧路径：按 topic_id 过滤
            for c in data.conversations.values():
                if c.topic_id == conv.parent_id and c.id != conversation_id:
                    c.is_active = False
        else:
            raise ValueError(f"Cannot determine scope for conversation {conversation_id}")

        conv.is_active = True
        # 向下兼容：如果挂载在 topic 下，同步 topic.active_conversation_id
        if conv.parent_type == "topic":
            topic = data.topics.get(conv.parent_id)
            if topic:
                topic.active_conversation_id = conversation_id

        self._storage.save(user_id, data)
        return conv
