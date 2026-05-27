"""树形对话操作服务 v4.0（归一化版）
层级：分区 → 领域 → 专题 → 对话 → 消息节点
内联分支：编辑消息在当前对话内创建新版本，不另开对话线程
"""

from __future__ import annotations

import time
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)
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

# Cognitive 图谱同步导入
from app.cognitive.models import CognitiveNode, MetaInfo
from app.cognitive.storage import upsert_node, delete_node as cog_delete_node


class TreeOpsService:
    """所有树形结构操作（归一化版本）"""

    # ═══════════════════════════════════════════════════════
    # 层级配置常量
    # ═══════════════════════════════════════════════════════
    LEVELS = ["partition", "domain", "topic", "conversation"]

    LEVEL_CONFIG = {
        "partition": {
            "collection": "partitions",
            "child_collection": "domains",
            "child_key": "partition_id",
            "parent_key": None,
            "factory": lambda name, emoji, **kw: Partition(
                name=name,
                subject=name,
                direction="subject",
                emoji=emoji,
                root_id=str(uuid4()),
            ),
            "auto_create_child": {
                "level": "domain",
                "name": "临时领域",  # 固定名称
                "emoji": "{emoji}",  # 继承分区的 emoji
            },
        },
        "domain": {
            "collection": "domains",
            "child_collection": "topics",
            "child_key": "domain_id",
            "parent_key": "partition_id",
            "factory": lambda name, emoji, **kw: Domain(
                partition_id=kw["parent_id"], name=name, emoji=emoji
            ),
            "auto_create_child": {  # 新增：创建领域时自动创建临时专题
                "level": "topic",
                "name": "临时专题",
                "emoji": "📝",
            },
        },
        "topic": {
            "collection": "topics",
            "child_collection": "conversations",
            "child_key": "topic_id",
            "parent_key": "domain_id",
            "factory": lambda name, emoji, **kw: Topic(
                domain_id=kw["parent_id"], name=name, emoji=emoji
            ),
            "auto_create_child": {
                "level": "conversation",
                "name": "新对话",  # 固定名称
                "emoji": "",
            },
        },
        "conversation": {
            "collection": "conversations",
            "child_collection": None,
            "child_key": None,
            "parent_key": "topic_id",
            "factory": lambda name, emoji, **kw: Conversation(
                topic_id=kw["parent_id"], name=name or "新对话"
            ),
        },
    }

    def _get_collection(self, data: UserData, level: str):
        return getattr(data, self.LEVEL_CONFIG[level]["collection"])

    def _delete_node(
        self, user_id: str, node_id: str, level: str, data: UserData | None = None
    ) -> None:
        if data is None:
            data = storage.load(user_id)

        config = self.LEVEL_CONFIG[level]
        collection = self._get_collection(data, level)

        if node_id not in collection:
            raise ValueError(f"{level.capitalize()} {node_id} not found")
        logger.info(f"Deleting {level} {node_id}")

        if level == "conversation":
            conv = collection[node_id]
            if conv.is_active:
                conv.is_active = False
                topic = data.topics.get(conv.topic_id)
                if topic and topic.active_conversation_id == node_id:
                    topic.active_conversation_id = ""
            for nid in conv.path:
                node = data.nodes.get(nid)
                if node:
                    node.is_deleted = True
            collection.pop(node_id, None)
        else:
            next_level = self.LEVELS[self.LEVELS.index(level) + 1]
            child_collection = self._get_collection(data, next_level)
            child_key = config["child_key"]
            child_ids = [
                cid
                for cid, child in list(child_collection.items())
                if getattr(child, child_key, None) == node_id
            ]
            for child_id in child_ids:
                self._delete_node(user_id, child_id, next_level, data=data)
            collection.pop(node_id, None)

        # 同步删除 CognitiveNode
        if level in ("partition", "domain", "topic"):
            try:
                cog_delete_node(node_id, user_id)
            except Exception:
                logger.warning(f"Failed to delete cognitive node {node_id}", exc_info=True)

    def _rename_node(self, user_id: str, node_id: str, level: str, new_name: str):
        data = storage.load(user_id)
        collection = self._get_collection(data, level)
        node = collection.get(node_id)
        if not node:
            raise ValueError(f"{level.capitalize()} {node_id} not found")
        node.name = new_name
        node.updated_at = time.time()
        storage.save(user_id, data)
        logger.info(f"Renamed {level} {node_id} to {new_name}")
        # 同步更新 CognitiveNode 的 label
        if level in ("partition", "domain", "topic"):
            try:
                from app.cognitive.storage import get_node as cog_get_node
                cog = cog_get_node(node_id, user_id)
                if cog:
                    old_emoji = cog.label.split(" ")[0] if cog.label and len(cog.label.split(" ")) > 1 else ""
                    cog.label = (old_emoji + " " + new_name) if old_emoji else new_name
                    upsert_node(cog, user_id)
            except Exception:
                logger.warning(f"Failed to rename cognitive node {node_id}", exc_info=True)
        return node

    def _create_node(
        self,
        user_id: str,
        level: str,
        parent_id: str | None,
        name: str,
        emoji: str = "",
        data: UserData | None = None,
        auto_created: bool = False,  # 是否由 auto_create_child 递归创建
    ):
        if data is None:
            data = storage.load(user_id)

        config = self.LEVEL_CONFIG[level]

        if config["parent_key"] is not None:
            parent_level = self.LEVELS[self.LEVELS.index(level) - 1]
            parent_collection = self._get_collection(data, parent_level)
            if parent_id not in parent_collection:
                raise ValueError(f"Parent {parent_level} {parent_id} not found")

        kwargs = {}
        if parent_id is not None:
            kwargs["parent_id"] = parent_id
        entity = config["factory"](name, emoji, **kwargs)

        if level == "partition":
            root_id = entity.root_id
            root_node = TreeNode(
                id=root_id,
                parent_id=root_id,
                partition_id=entity.id,
                conversation_id="",
                role="assistant",
                content_blocks=[],
                text_summary="[virtual_root]",
            )
            data.nodes[root_id] = root_node
            entity.root_id = root_id

        collection = self._get_collection(data, level)
        collection[entity.id] = entity

        auto_config = config.get("auto_create_child")
        if auto_config:
            child_level = auto_config["level"]
            child_name = auto_config["name"].format(name=name, emoji=emoji)
            child_emoji = auto_config["emoji"].format(name=name, emoji=emoji)
            child = self._create_node(
                user_id, child_level, entity.id, child_name, child_emoji, data=data,
                auto_created=True,
            )
            if level == "topic" and child_level == "conversation":
                entity.active_conversation_id = child.id

        if level == "partition":
            data.active_partition_id = entity.id

        # ── 同步 CognitiveNode 到认知图谱 ──
        if level in ("partition", "domain", "topic"):
            cog_parent = None if level == "partition" else parent_id
            # 判断是否为自动创建的临时节点
            is_auto = auto_created
            # 构造 path_id（追加 short uuid 确保唯一性，避免自动创建同名校节点冲突）
            path_id = name
            if cog_parent:
                # 从 collection 中取父节点名称
                parent_level = self.LEVELS[self.LEVELS.index(level) - 1]
                parent_coll = self._get_collection(data, parent_level)
                parent_entity = parent_coll.get(cog_parent)
                if parent_entity:
                    path_id = getattr(parent_entity, "name", name) + "." + name
            path_id += "." + entity.id[:8]
            cog_node = CognitiveNode(
                id=entity.id,
                label=(emoji + " " + name) if emoji else name,
                level=level,
                parent=cog_parent,
                path_id=path_id,
                node_type="auto_generated" if is_auto else "explicit",
                is_visible=True,
                meta=MetaInfo(created_at=time.time()),
            )
            upsert_node(cog_node, user_id)

        return entity

    # ═══════════════════════════════════════════════════════
    # 公开接口
    # ═══════════════════════════════════════════════════════

    def create_partition(
        self, user_id, name, subject="", direction="subject", emoji="💬"
    ):
        data = storage.load(user_id)
        partition = self._create_node(
            user_id, "partition", None, name, emoji, data=data
        )
        storage.save(user_id, data)
        return partition

    def delete_partition(self, user_id, partition_id):
        data = storage.load(user_id)
        self._delete_node(user_id, partition_id, "partition", data=data)
        storage.save(user_id, data)

    def rename_partition(self, user_id, partition_id, name):
        return self._rename_node(user_id, partition_id, "partition", name)

    def create_domain(self, user_id, partition_id, name, emoji="📚"):
        data = storage.load(user_id)
        domain = self._create_node(
            user_id, "domain", partition_id, name, emoji, data=data
        )
        storage.save(user_id, data)
        return domain

    def delete_domain(self, user_id, domain_id):
        data = storage.load(user_id)
        self._delete_node(user_id, domain_id, "domain", data=data)
        storage.save(user_id, data)

    def rename_domain(self, user_id, domain_id, name):
        return self._rename_node(user_id, domain_id, "domain", name)

    def create_topic(self, user_id, domain_id, name, emoji="📝"):
        data = storage.load(user_id)
        topic = self._create_node(user_id, "topic", domain_id, name, emoji, data=data)
        storage.save(user_id, data)
        return topic

    def delete_topic(self, user_id, topic_id):
        data = storage.load(user_id)
        self._delete_node(user_id, topic_id, "topic", data=data)
        storage.save(user_id, data)

    def rename_topic(self, user_id, topic_id, name):
        return self._rename_node(user_id, topic_id, "topic", name)

    def create_conversation(self, user_id, topic_id, name=""):
        data = storage.load(user_id)
        conv = self._create_node(user_id, "conversation", topic_id, name, data=data)
        storage.save(user_id, data)
        return conv

    def delete_conversation(self, user_id, conv_id):
        data = storage.load(user_id)
        self._delete_node(user_id, conv_id, "conversation", data=data)
        storage.save(user_id, data)

    def rename_conversation(self, user_id, conv_id, name):
        return self._rename_node(user_id, conv_id, "conversation", name)

    def get_partition_context(self, user_id: str, partition_id: str) -> dict:
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")
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

    def switch_conversation(
        self, user_id: str, topic_id: str, conversation_id: str
    ) -> Conversation:
        data = storage.load(user_id)
        topic = data.topics.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")
        for c in data.conversations.values():
            if c.topic_id == topic_id:
                c.is_active = False
        conv = data.conversations.get(conversation_id)
        if not conv or conv.topic_id != topic_id:
            raise ValueError(
                f"Conversation {conversation_id} not found in topic {topic_id}"
            )
        conv.is_active = True
        topic.active_conversation_id = conversation_id
        storage.save(user_id, data)
        return conv

    def add_message(
        self,
        user_id,
        partition_id,
        role,
        content_blocks,
        text_summary="",
        conversation_id="",
    ) -> TreeNode:
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")
        if not conversation_id:
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

    def update_message_content(
        self,
        user_id: str,
        message_id: str,
        text: str,
    ) -> None:
        """覆写消息内容（原地更新，不创建版本）"""
        data = storage.load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            return
        node.content_blocks = [ContentBlock(text=text)]
        node.text_summary = text
        storage.save(user_id, data)

    def modify_message(
        self, user_id, message_id, new_content_blocks, new_text_summary=""
    ) -> TreeNode:
        data = storage.load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            raise ValueError(f"Message {message_id} not found")
        node.has_modified_version = True
        new_node = TreeNode(
            parent_id=node.parent_id,
            partition_id=node.partition_id,
            conversation_id=node.conversation_id,
            role=node.role,
            content_blocks=new_content_blocks,
            text_summary=new_text_summary,
        )
        parent = data.nodes.get(node.parent_id)
        if parent and new_node.id not in parent.children_ids:
            parent.children_ids.append(new_node.id)
        data.nodes[new_node.id] = new_node
        conv = data.conversations.get(node.conversation_id)
        current_version = node
        replace_idx = None
        if conv:
            if message_id in conv.path:
                replace_idx = conv.path.index(message_id)
            else:
                for i, nid in enumerate(conv.path):
                    sibling = data.nodes.get(nid)
                    if (
                        sibling
                        and sibling.parent_id == node.parent_id
                        and sibling.role == node.role
                    ):
                        current_version = sibling
                        replace_idx = i
                        break
        if (
            current_version
            and current_version.id != new_node.id
            and current_version.children_ids
        ):
            new_node.children_ids = list(current_version.children_ids)
            for child_id in current_version.children_ids:
                child = data.nodes.get(child_id)
                if child:
                    child.parent_id = new_node.id
            current_version.children_ids = []
            current_version.has_modified_version = True
        if replace_idx is not None:
            assert conv is not None
            conv.path[replace_idx] = new_node.id
        if conv:
            conv.summary_dirty = True
        storage.save(user_id, data)
        return new_node

    def delete_message(self, user_id, message_id) -> None:
        data = storage.load(user_id)

        def delete_subtree(nid):
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
                    nid
                    for nid in conv.path
                    if not data.nodes.get(
                        nid,
                        TreeNode(
                            parent_id="",
                            conversation_id="",
                            partition_id="",
                            role="user",
                        ),
                    ).is_deleted
                ]
        storage.save(user_id, data)


tree_ops = TreeOpsService()
