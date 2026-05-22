"""
树形对话操作服务 v4.0
层级：分区 → 领域 → 专题 → 对话 → 消息节点
内联分支：编辑消息在当前对话内创建新版本，不另开对话线程
"""

from __future__ import annotations

import time
from uuid import uuid4

from app.schemas.conversation import (
    ContentBlock,
    Conversation,
    Domain,
    Partition,
    Topic,
    TreeNode,
    UserData,
)
from app.services.storage import storage


class TreeOpsService:
    """所有树形结构操作（v4: 领域/专题/对话 体系）"""

    # ── 分区 ──

    def create_partition(
        self,
        user_id: str,
        name: str,
        subject: str = "",
        direction: str = "subject",
        emoji: str = "💬",
    ) -> Partition:
        """创建新分区，附带虚拟根节点 + 默认领域"""
        data = storage.load(user_id)

        root_id = str(uuid4())
        root_node = TreeNode(
            id=root_id,
            parent_id=root_id,
            partition_id="",
            conversation_id="",
            role="assistant",
            content_blocks=[],
            text_summary="[virtual_root]",
        )

        partition = Partition(
            name=name,
            subject=subject,
            direction=direction,
            emoji=emoji,
            root_id=root_id,
        )
        root_node.partition_id = partition.id

        # 创建默认领域
        domain = Domain(
            partition_id=partition.id,
            name=name,
            emoji=emoji,
        )

        data.nodes[root_id] = root_node
        data.partitions[partition.id] = partition
        data.domains[domain.id] = domain
        data.active_partition_id = partition.id

        storage.save(user_id, data)
        return partition

    # ── 领域 ──

    def create_domain(
        self, user_id: str, partition_id: str, name: str, emoji: str = "📚",
    ) -> Domain:
        data = storage.load(user_id)
        if partition_id not in data.partitions:
            raise ValueError(f"Partition {partition_id} not found")
        domain = Domain(partition_id=partition_id, name=name, emoji=emoji)
        data.domains[domain.id] = domain
        storage.save(user_id, data)
        return domain

    def rename_domain(self, user_id: str, domain_id: str, name: str) -> Domain:
        data = storage.load(user_id)
        domain = data.domains.get(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")
        domain.name = name
        domain.updated_at = time.time()
        storage.save(user_id, data)
        return domain

    def delete_domain(self, user_id: str, domain_id: str) -> None:
        data = storage.load(user_id)
        domain = data.domains.get(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")
        # 归档所有下属 topic 和 conversation
        for tid, topic in list(data.topics.items()):
            if topic.domain_id != domain_id:
                continue
            self._archive_topic(data, tid)
        data.domains.pop(domain_id, None)
        storage.save(user_id, data)

    # ── 专题 ──

    def create_topic(
        self, user_id: str, domain_id: str, name: str, emoji: str = "📝",
    ) -> Topic:
        data = storage.load(user_id)
        if domain_id not in data.domains:
            raise ValueError(f"Domain {domain_id} not found")
        topic = Topic(domain_id=domain_id, name=name, emoji=emoji)

        # 为专题创建首个默认对话
        conv = Conversation(topic_id=topic.id, name=name)
        topic.active_conversation_id = conv.id

        data.topics[topic.id] = topic
        data.conversations[conv.id] = conv
        storage.save(user_id, data)
        return topic

    def rename_topic(self, user_id: str, topic_id: str, name: str) -> Topic:
        data = storage.load(user_id)
        topic = data.topics.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")
        topic.name = name
        topic.updated_at = time.time()
        storage.save(user_id, data)
        return topic

    def delete_topic(self, user_id: str, topic_id: str) -> None:
        data = storage.load(user_id)
        topic = data.topics.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")
        self._archive_topic(data, topic_id)
        data.topics.pop(topic_id, None)
        storage.save(user_id, data)

    def _archive_topic(self, data: UserData, topic_id: str) -> None:
        """软删专题下所有对话和消息"""
        for cid, conv in list(data.conversations.items()):
            if conv.topic_id != topic_id:
                continue
            for nid in conv.path:
                node = data.nodes.get(nid)
                if node:
                    node.is_deleted = True
            data.conversations.pop(cid, None)

    # ── 对话 ──

    def create_conversation(
        self, user_id: str, topic_id: str, name: str = "",
    ) -> Conversation:
        """用户在专题下手动创建新对话"""
        data = storage.load(user_id)
        topic = data.topics.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")

        # 停用旧活跃对话
        old_cid = topic.active_conversation_id
        if old_cid and old_cid in data.conversations:
            data.conversations[old_cid].is_active = False

        conv = Conversation(topic_id=topic_id, name=name or "新对话")
        topic.active_conversation_id = conv.id
        data.conversations[conv.id] = conv
        storage.save(user_id, data)
        return conv

    def switch_conversation(
        self, user_id: str, topic_id: str, conversation_id: str,
    ) -> Conversation:
        """切换专题的活跃对话"""
        data = storage.load(user_id)
        topic = data.topics.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")

        for c in data.conversations.values():
            if c.topic_id == topic_id:
                c.is_active = False

        conv = data.conversations.get(conversation_id)
        if not conv or conv.topic_id != topic_id:
            raise ValueError(f"Conversation {conversation_id} not found in topic {topic_id}")

        conv.is_active = True
        topic.active_conversation_id = conversation_id
        storage.save(user_id, data)
        return conv

    def rename_conversation(self, user_id: str, conv_id: str, name: str) -> Conversation:
        data = storage.load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found")
        conv.name = name
        storage.save(user_id, data)
        return conv

    def delete_conversation(self, user_id: str, conv_id: str) -> None:
        """删除对话（软删消息，移除对话记录）。
        若为活跃对话则先取消活跃状态。"""
        data = storage.load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found")

        # 如果删除的是活跃对话，先取消活跃状态
        if conv.is_active:
            conv.is_active = False
            # 清除关联专题的 active_conversation_id
            topic = data.topics.get(conv.topic_id)
            if topic and topic.active_conversation_id == conv_id:
                topic.active_conversation_id = ""

        for nid in conv.path:
            node = data.nodes.get(nid)
            if node:
                node.is_deleted = True
        data.conversations.pop(conv_id, None)
        storage.save(user_id, data)

    # ── 消息 ──

    def add_message(
        self,
        user_id: str,
        partition_id: str,
        role: str,
        content_blocks: list[ContentBlock],
        text_summary: str = "",
        conversation_id: str = "",
    ) -> TreeNode:
        """向活跃对话添加消息"""
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        # 找到活跃 topic → conversation
        if not conversation_id:
            # 从 partition 的 domains 中找到活跃的 topic 和 conversation
            conv = None
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
        storage.save(user_id, data)
        return node

    def modify_message(
        self,
        user_id: str,
        message_id: str,
        new_content_blocks: list[ContentBlock],
        new_text_summary: str = "",
    ) -> TreeNode:
        """
        编辑消息 — v4: 不创建新对话，在当前对话内创建新版本。
        新版本加入父节点的 children_ids，原消息标记 has_modified_version。
        前端用 < > 按钮在同级版本间切换。
        """
        data = storage.load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            raise ValueError(f"Message {message_id} not found")

        # 标记原消息有修改版本
        node.has_modified_version = True

        # 在同父节点下创建新版本
        new_node = TreeNode(
            parent_id=node.parent_id,
            partition_id=node.partition_id,
            conversation_id=node.conversation_id,
            role=node.role,
            content_blocks=new_content_blocks,
            text_summary=new_text_summary,
        )

        # 添加到父节点的 children_ids（同级版本列表）
        parent = data.nodes.get(node.parent_id)
        if parent and new_node.id not in parent.children_ids:
            parent.children_ids.append(new_node.id)

        data.nodes[new_node.id] = new_node

        # 迁移原消息的子节点到新版本，保持树结构完整
        # 新版本继承原消息的 children_ids，原消息变为纯历史叶子
        if node.children_ids:
            new_node.children_ids = list(node.children_ids)
            for child_id in node.children_ids:
                child = data.nodes.get(child_id)
                if child:
                    child.parent_id = new_node.id
            node.children_ids = []

        # 更新对话路径——用新版本替换原消息ID，确保加载时显示最新版本
        conv = data.conversations.get(node.conversation_id)
        if conv and message_id in conv.path:
            idx = conv.path.index(message_id)
            conv.path[idx] = new_node.id

        storage.save(user_id, data)
        return new_node

    def delete_message(self, user_id: str, message_id: str) -> None:
        """软删除消息及其子树"""
        data = storage.load(user_id)

        def delete_subtree(nid: str) -> None:
            node = data.nodes.get(nid)
            if not node:
                return
            node.is_deleted = True
            parent = data.nodes.get(node.parent_id)
            if parent and nid in parent.children_ids:
                parent.children_ids.remove(nid)
                for child_id in node.children_ids:
                    if child_id not in parent.children_ids:
                        parent.children_ids.append(child_id)
                    child = data.nodes.get(child_id)
                    if child:
                        child.parent_id = parent.id
            for child_id in node.children_ids[:]:
                delete_subtree(child_id)

        delete_subtree(message_id)

        node = data.nodes.get(message_id)
        if node:
            conv = data.conversations.get(node.conversation_id)
            if conv:
                conv.summary_dirty = True
                conv.path = [
                    nid for nid in conv.path
                    if not data.nodes.get(
                        nid,
                        TreeNode(parent_id="", conversation_id="", partition_id="", role="user"),
                    ).is_deleted
                ]

        storage.save(user_id, data)

    # ── 分区/领域/专题编辑与删除 ──

    def rename_partition(self, user_id: str, partition_id: str, name: str) -> Partition:
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")
        partition.name = name
        partition.updated_at = time.time()
        storage.save(user_id, data)
        return partition

    def delete_partition(self, user_id: str, partition_id: str) -> None:
        data = storage.load(user_id)
        if partition_id not in data.partitions:
            raise ValueError(f"Partition {partition_id} not found")

        # 归档所有下属领域/专题/对话
        for did, domain in list(data.domains.items()):
            if domain.partition_id != partition_id:
                continue
            for tid, topic in list(data.topics.items()):
                if topic.domain_id != did:
                    continue
                self._archive_topic(data, tid)
                data.topics.pop(tid, None)
            data.domains.pop(did, None)
        data.partitions.pop(partition_id, None)
        storage.save(user_id, data)

    def get_partition_context(self, user_id: str, partition_id: str) -> dict:
        """获取分区完整上下文"""
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        # 找到活跃对话的消息
        messages: list[TreeNode] = []
        conv = None
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


# 全局单例
tree_ops = TreeOpsService()
