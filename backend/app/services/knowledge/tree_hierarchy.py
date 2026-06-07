"""Tree hierarchy CRUD — partition/domain/topic/conversation create/delete + helpers"""
from __future__ import annotations

import time
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

from app.schemas.conversation import (
    Conversation, Domain, Partition, Topic, TreeNode, UserData,
)
from app.services.common.storage import storage


class TreeHierarchyMixin:
    """Partition／Domain／Topic／Conversation 层级 CRUD."""

    LEVELS = ["partition", "domain", "topic", "conversation"]

    LEVEL_CONFIG = {
        "partition": {
            "collection": "partitions",
            "child_collection": "domains",
            "child_key": "partition_id",
            "parent_key": None,
            "factory": lambda name, emoji, **kw: Partition(
                name=name, subject=name, direction="subject",
                emoji=emoji, root_id=str(uuid4()),
            ),
            "auto_create_child": {
                "level": "domain", "name": "新领域", "emoji": "{emoji}",
            },
        },
        "domain": {
            "collection": "domains",
            "child_collection": "topics",
            "child_key": "domain_id",
            "parent_key": "partition_id",
            "factory": lambda name, emoji, **kw: Domain(
                partition_id=kw["parent_id"], name=name, emoji=emoji,
            ),
            "auto_create_child": {
                "level": "topic", "name": "新专题", "emoji": "📝",
            },
        },
        "topic": {
            "collection": "topics",
            "child_collection": "conversations",
            "child_key": "topic_id",
            "parent_key": "domain_id",
            "factory": lambda name, emoji, **kw: Topic(
                domain_id=kw["parent_id"], name=name, emoji=emoji,
            ),
            "auto_create_child": {
                "level": "conversation", "name": "新对话", "emoji": "",
            },
        },
        "conversation": {
            "collection": "conversations",
            "child_collection": None,
            "child_key": None,
            "parent_key": "topic_id",
            "factory": lambda name, emoji, **kw: Conversation(
                topic_id=kw["parent_id"],
                parent_id=kw["parent_id"],
                parent_type="topic",
                name=name or "新对话",
            ),
        },
    }

    _storage = storage

    # ── 内部辅助 ──

    def _get_collection(self, data: UserData, level: str):
        return getattr(data, self.LEVEL_CONFIG[level]["collection"])

    def _resolve_parent(self, data: UserData, parent_id: str) -> tuple[str, Partition | Domain | Topic]:
        """根据 ID 查找父级实体，返回 (level, entity)。支持 partition / domain / topic 三级。"""
        if parent_id in data.partitions:
            return "partition", data.partitions[parent_id]
        if parent_id in data.domains:
            return "domain", data.domains[parent_id]
        if parent_id in data.topics:
            return "topic", data.topics[parent_id]
        raise ValueError(f"Parent {parent_id} not found (not a partition/domain/topic)")

    def _ensure_domain(self, data: UserData, partition_id: str, name: str) -> str:
        """在 partition 下查找或创建同名 domain，返回 domain_id。"""
        for d in data.domains.values():
            if d.partition_id == partition_id and d.name == name:
                return d.id
        domain = Domain(partition_id=partition_id, name=name, emoji="📚")
        data.domains[domain.id] = domain
        return domain.id

    def _ensure_topic(self, data: UserData, partition_id: str, name: str) -> str:
        """在 partition 下查找或创建 domain → topic 链路，返回 topic_id。"""
        domain_id = self._ensure_domain(data, partition_id, name)
        for t in data.topics.values():
            if t.domain_id == domain_id and t.name == name:
                return t.id
        topic = Topic(domain_id=domain_id, name=name, emoji="📝")
        data.topics[topic.id] = topic
        return topic.id

    def _create_conversation_node(
        self, user_id: str, data: UserData, parent_id: str, name: str = "",
        type: str = "normal", metadata: dict | None = None,
    ) -> Conversation:
        """在任意层级下创建 conversation，自动补全省级 ID。"""
        parent_type, parent_entity = self._resolve_parent(data, parent_id)

        conv = Conversation(
            parent_id=parent_id,
            parent_type=parent_type,
            type=type,
            name=name or "新对话",
            metadata=metadata or {},
        )

        # 补全三级 ID
        if parent_type == "partition":
            conv.partition_id = parent_id
        elif parent_type == "domain":
            conv.partition_id = parent_entity.partition_id
            conv.domain_id = parent_id
        elif parent_type == "topic":
            domain = data.domains.get(parent_entity.domain_id)
            conv.partition_id = domain.partition_id if domain else ""
            conv.domain_id = parent_entity.domain_id
            conv.topic_id = parent_id

        # 根节点创建
        root_id = str(uuid4())
        root_node = TreeNode(
            id=root_id, parent_id=root_id,
            partition_id=conv.partition_id, conversation_id=conv.id,
            role="assistant", content_blocks=[], text_summary="[virtual_root]",
        )
        data.nodes[root_id] = root_node
        conv.path.append(root_id)

        # 临时分区标记
        temp_part = data.partitions.get(conv.partition_id)
        if temp_part and getattr(temp_part, "is_temp", False):
            conv.is_temporary = True

        data.conversations[conv.id] = conv
        return conv

    def ensure_tree_exploration(
        self, user_id: str, partition_id: str, kg_node_id: str,
        kg_node_label: str, kg_node_level: str = "concept",
    ) -> Conversation:
        """在 partition 下确保存在对应层级的探索对话。

        kg_node_level 决定 parent 层级：
          - "partition" → parent = partition_id
          - "domain"    → parent = domain_id（自动补全）
          - "topic"/"concept" → parent = topic_id（自动补全 domain→topic）"""
        data = self._storage.load(user_id)

        if kg_node_level == "partition":
            parent_id = partition_id
        elif kg_node_level == "domain":
            parent_id = self._ensure_domain(data, partition_id, kg_node_label)
        else:
            parent_id = self._ensure_topic(data, partition_id, kg_node_label)

        # 查找已有该节点的探索会话
        for conv in data.conversations.values():
            if (conv.parent_id == parent_id and conv.type == "tree_exploration"
                    and conv.metadata.get("bound_node_id") == kg_node_id):
                return conv

        conv = self._create_conversation_node(
            user_id, data, parent_id, name=f"探索：{kg_node_label}",
            type="tree_exploration",
            metadata={"bound_node_id": kg_node_id, "bound_node_label": kg_node_label},
        )
        self._storage.save(user_id, data)
        return conv

    def create_temporary_conversation(self, user_id: str) -> Conversation:
        """空状态时创建临时对话（自动挂临时分区）。"""
        data = self._storage.load(user_id)
        temp_part, _ = self._ensure_temp_partition(user_id, data)
        conv = self._create_conversation_node(
            user_id, data, temp_part.id, name="临时会话", type="temporary",
        )
        self._storage.save(user_id, data)
        return conv

    def migrate_temporary_conversation(
        self, user_id: str, conv_id: str, target_partition_id: str,
        target_type: str = "normal",
    ) -> Conversation:
        """将临时对话迁移到正式分区。
        支持：迁移到已有分区 / 新建分区后调用此方法。"""
        data = self._storage.load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found")
        if conv.type != "temporary":
            raise ValueError("Only temporary conversations can be migrated")

        # 更新对话挂载
        conv.parent_id = target_partition_id
        conv.parent_type = "partition"
        conv.type = target_type
        conv.partition_id = target_partition_id
        conv.domain_id = ""
        conv.topic_id = ""

        # 更新所有消息节点的 partition_id
        for nid in conv.path:
            node = data.nodes.get(nid)
            if node:
                node.partition_id = target_partition_id

        data.conversations[conv.id] = conv
        # TODO: 清理临时分区（后续可考虑更多场景）
        self._cleanup_empty_temp_partition(user_id, data)
        self._storage.save(user_id, data)
        return conv

    def _cleanup_empty_temp_partition(self, user_id: str, data: UserData) -> None:
        """清理无活跃对话的临时分区。"""
        temp_ids = [p.id for p in data.partitions.values() if getattr(p, "is_temp", False)]
        for pid in temp_ids:
            has_active = any(
                c.partition_id == pid for c in data.conversations.values()
                if c.type != "temporary"
            )
            if not has_active:
                # 清理临时分区下的 topic/domain
                for t in list(data.topics.values()):
                    # 通过 domain_id 或 partition_id 判断是否属于临时分区
                    if t.partition_id == pid:
                        data.topics.pop(t.id, None)
                    elif t.domain_id:
                        d = data.domains.get(t.domain_id)
                        if d and d.partition_id == pid:
                            data.topics.pop(t.id, None)
                for d in list(data.domains.values()):
                    if d.partition_id == pid:
                        data.domains.pop(d.id, None)
                data.partitions.pop(pid, None)

    def _delete_node(
        self, user_id: str, node_id: str, level: str, data: UserData | None = None,
    ) -> None:
        if data is None:
            data = self._storage.load(user_id)

        config = self.LEVEL_CONFIG[level]
        collection = self._get_collection(data, level)

        if node_id not in collection:
            raise ValueError(f"{level.capitalize()} {node_id} not found")
        logger.info("Deleting %s %s", level, node_id)

        if level == "conversation":
            conv = collection[node_id]
            # 清除父级上的 active_conversation 引用
            if conv.is_active:
                conv.is_active = False
                if conv.parent_type == "topic":
                    topic = data.topics.get(conv.parent_id)
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

        self._sync_cog_delete(user_id, node_id, level)

    def _create_node(
        self, user_id: str, level: str, parent_id: str | None, name: str,
        emoji: str = "", data: UserData | None = None,
        auto_created: bool = False,
    ):
        if data is None:
            data = self._storage.load(user_id)

        config = self.LEVEL_CONFIG[level]

        if config["parent_key"] is not None:
            parent_level = self.LEVELS[self.LEVELS.index(level) - 1]
            parent_collection = self._get_collection(data, parent_level)
            if parent_id not in parent_collection:
                if level == "conversation":
                    self._ensure_conversation_parent_path(user_id, parent_id, data)
                else:
                    raise ValueError(f"Parent {parent_level} {parent_id} not found")

        collection = self._get_collection(data, level)
        parent_key = config.get("parent_key")
        siblings = (
            [e for e in collection.values()
             if (getattr(e, parent_key, None) == parent_id if parent_key else True)]
            if parent_key else list(collection.values())
        )
        sibling_names = {e.name for e in siblings}
        if name in sibling_names and not name.startswith("新"):
            counter = 2
            while f"{name}({counter})" in sibling_names:
                counter += 1
            name = f"{name}({counter})"

        kwargs = {}
        if parent_id is not None:
            kwargs["parent_id"] = parent_id
        entity = config["factory"](name, emoji, **kwargs)

        if level == "partition":
            root_id = entity.root_id
            root_node = TreeNode(
                id=root_id, parent_id=root_id, partition_id=entity.id,
                conversation_id="", role="assistant", content_blocks=[],
                text_summary="[virtual_root]",
            )
            data.nodes[root_id] = root_node

        collection = self._get_collection(data, level)
        collection[entity.id] = entity

        if level == "conversation":
            topic = data.topics.get(getattr(entity, "topic_id", ""))
            domain = data.domains.get(topic.domain_id) if topic else None
            partition = data.partitions.get(domain.partition_id) if domain else None
            if partition and getattr(partition, "is_temp", False):
                entity.is_temporary = True

        auto_config = config.get("auto_create_child")
        if auto_config:
            child_level = auto_config["level"]
            child_name = auto_config["name"].format(name=name, emoji=emoji)
            child_emoji = auto_config["emoji"].format(name=name, emoji=emoji)
            child = self._create_node(
                user_id, child_level, entity.id, child_name, child_emoji,
                data=data, auto_created=True,
            )
            if level == "topic" and child_level == "conversation":
                entity.active_conversation_id = child.id

        if level == "partition":
            data.active_partition_id = entity.id

        try:
            self._sync_cog_create(user_id, entity, level, name, emoji, parent_id, data,
                                  auto_created=auto_created)
        except Exception:
            logger.warning(f"认知节点同步失败（不影响创建 {level} {entity.id}）", exc_info=True)

        return entity

    def _ensure_conversation_parent_path(
        self, user_id: str, topic_id: str, data: UserData,
    ) -> None:
        from app.cognitive.storage import get_node as cog_get_node
        cog = cog_get_node(topic_id, user_id)

        if not cog or not cog.is_visible:
            temp_partition, _ = self._ensure_temp_partition(user_id, data)
            if topic_id not in data.topics:
                topic = Topic(
                    id=topic_id if topic_id else str(uuid4()),
                    domain_id="",  # 临时分区不再有 domain，直接挂在分区下
                    partition_id=temp_partition.id,
                    name="新对话", emoji="💬",
                )
                data.topics[topic.id] = topic
            return

        label_parts = cog.label.split(" ", 1) if cog.label else [""]
        emoji_char = ""
        node_name = cog.label or ""
        if len(label_parts) == 2 and label_parts[0] and all(
            ord(c) > 0x1F000 for c in label_parts[0]
        ):
            emoji_char = label_parts[0]
            node_name = label_parts[1]

        cog_parent_id = cog.parent
        parent_cog = None
        parent_label = ""
        parent_emoji = ""
        if cog_parent_id:
            parent_cog = cog_get_node(cog_parent_id, user_id)
            if parent_cog:
                pl = parent_cog.label.split(" ", 1) if parent_cog.label else [""]
                parent_emoji = ""
                parent_label = parent_cog.label or ""
                if len(pl) == 2 and pl[0] and all(ord(c) > 0x1F000 for c in pl[0]):
                    parent_emoji = pl[0]
                    parent_label = pl[1]
                self._ensure_conversation_parent_path(user_id, cog_parent_id, data)

        if topic_id not in data.topics:
            domain_id = parent_cog.parent if parent_cog else ""
            if domain_id and domain_id not in data.domains:
                partition_id = ""
                if parent_cog:
                    pp_cog = cog_get_node(parent_cog.parent, user_id) if parent_cog.parent else None
                    if pp_cog:
                        partition_id = pp_cog.id
                        if partition_id not in data.partitions:
                            pp_name = pp_cog.label or "自动创建"
                            pp_emoji = ""
                            ppl = pp_cog.label.split(" ", 1) if pp_cog.label else [""]
                            if len(ppl) == 2 and ppl[0] and all(ord(c) > 0x1F000 for c in ppl[0]):
                                pp_emoji = ppl[0]
                                pp_name = ppl[1]
                            partition = Partition(
                                id=partition_id, name=pp_name, subject=pp_name,
                                direction="subject", emoji=pp_emoji or "💬",
                                root_id=str(uuid4()),
                            )
                            data.partitions[partition_id] = partition
                            root_node = TreeNode(
                                id=partition.root_id, parent_id=partition.root_id,
                                partition_id=partition_id, conversation_id="",
                                role="assistant", content_blocks=[],
                                text_summary="[virtual_root]",
                            )
                            data.nodes[partition.root_id] = root_node
                domain = Domain(
                    id=domain_id, partition_id=partition_id,
                    name=parent_label or "自动创建", emoji=parent_emoji or "📚",
                )
                data.domains[domain_id] = domain

            topic = Topic(
                id=topic_id, domain_id=domain_id,
                name=node_name or "自动创建", emoji=emoji_char or "📝",
            )
            data.topics[topic_id] = topic

    TEMP_PARTITION_NAME = "💬 临时"

    def _ensure_temp_partition(self, user_id: str, data: UserData):
        """确保存在临时分区（不创建子领域，临时会话直接挂在分区下）。"""
        for p in data.partitions.values():
            if getattr(p, "is_temp", False):
                return p, None  # 不再创建 domain，返回 None
        temp_partition = Partition(
            name=self.TEMP_PARTITION_NAME, subject="",
            direction="subject", emoji="💬", color="#888888",
            root_id=str(uuid4()), is_temp=True,
        )
        data.partitions[temp_partition.id] = temp_partition
        root_node = TreeNode(
            id=temp_partition.root_id, parent_id=temp_partition.root_id,
            partition_id=temp_partition.id, conversation_id="",
            role="assistant", content_blocks=[], text_summary="[virtual_root]",
        )
        data.nodes[temp_partition.root_id] = root_node
        return temp_partition, None

    # ── 公开 CRUD ──

    def create_partition(self, user_id, name, subject="", direction="subject", emoji="💬"):
        data = self._storage.load(user_id)
        partition = self._create_node(user_id, "partition", None, name, emoji, data=data)
        self._storage.save(user_id, data)
        return partition

    def delete_partition(self, user_id, partition_id):
        data = self._storage.load(user_id)
        self._delete_node(user_id, partition_id, "partition", data=data)
        self._storage.save(user_id, data)

    def create_domain(self, user_id, partition_id, name, emoji="📚"):
        data = self._storage.load(user_id)
        domain = self._create_node(user_id, "domain", partition_id, name, emoji, data=data)
        self._storage.save(user_id, data)
        return domain

    def delete_domain(self, user_id, domain_id):
        data = self._storage.load(user_id)
        self._delete_node(user_id, domain_id, "domain", data=data)
        self._storage.save(user_id, data)

    def create_topic(self, user_id, domain_id, name, emoji="📝"):
        data = self._storage.load(user_id)
        topic = self._create_node(user_id, "topic", domain_id, name, emoji, data=data)
        self._storage.save(user_id, data)
        return topic

    def delete_topic(self, user_id, topic_id):
        data = self._storage.load(user_id)
        self._delete_node(user_id, topic_id, "topic", data=data)
        self._storage.save(user_id, data)

    def create_conversation(self, user_id, topic_id="", name="", parent_id="", type="normal"):
        """创建对话。向下兼容：传 topic_id 走旧路径；传 parent_id 走新通用路径。"""
        data = self._storage.load(user_id)
        if parent_id:
            conv = self._create_conversation_node(
                user_id, data, parent_id, name=name, type=type,
            )
        else:
            conv = self._create_node(user_id, "conversation", topic_id, name, data=data)
        self._storage.save(user_id, data)
        return conv

    def delete_conversation(self, user_id, conv_id):
        data = self._storage.load(user_id)
        self._delete_node(user_id, conv_id, "conversation", data=data)
        self._storage.save(user_id, data)
