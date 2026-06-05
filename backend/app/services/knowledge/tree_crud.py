"""CRUD operations for the tree hierarchy (mixin for TreeOpsService).

Covers: create / delete / get / switch / add_message / modify_message /
delete_message / sub-branch operations, and the shared helpers
_get_collection / _create_node / _delete_node / _ensure_conversation_parent_path.
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
    TextBlock,
    Topic,
    TreeNode,
    UserData,
)
from app.services.common.storage import storage


class TreeCrudMixin:
    """Core tree CRUD operations mixed into TreeOpsService."""

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
                "name": "新领域",
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
            "auto_create_child": {  # 创建领域时自动创建新专题
                "level": "topic",
                "name": "新专题",
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

    # ------------------------------------------------------------------
    # Internal storage attribute – set in __init__ of the concrete class
    # so that sub-modules can reference self._storage instead of importing
    # the singleton directly.
    # ------------------------------------------------------------------
    _storage = storage  # default; overridden in TreeOpsService.__init__

    # ═══════════════════════════════════════════════════════
    # Private helpers
    # ═══════════════════════════════════════════════════════

    def _get_collection(self, data: UserData, level: str):
        return getattr(data, self.LEVEL_CONFIG[level]["collection"])

    def _delete_node(
        self, user_id: str, node_id: str, level: str, data: UserData | None = None
    ) -> None:
        if data is None:
            data = self._storage.load(user_id)

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

        # sync: delete cognitive node
        self._sync_cog_delete(user_id, node_id, level)

    def _ensure_conversation_parent_path(
        self, user_id: str, topic_id: str, data: UserData
    ) -> None:
        """When a topic_id (from cognitive_nodes) is not in data.topics,
        walk the cognitive_nodes hierarchy and create missing tree nodes
        (topic → domain → partition) as needed.

        If the cognitive node is invisible/auto_created or doesn't exist,
        route to the 临时 partition instead (no domain/topic in the graph)."""
        from app.cognitive.storage import get_node as cog_get_node

        cog = cog_get_node(topic_id, user_id)

        # ── 不可见/不存在 → 接入临时分区 ──
        if not cog or not cog.is_visible:
            temp_partition, temp_domain = self._ensure_temp_partition(user_id, data)
            # Create a flat topic under the temp domain for this conversation
            if topic_id not in data.topics:
                label = "新对话"
                topic = Topic(
                    id=topic_id if topic_id else str(uuid4()),
                    domain_id=temp_domain.id,
                    name=label,
                    emoji="💬",
                )
                data.topics[topic.id] = topic
            return

        # ── 可见认知节点 → 沿层级创建分区/领域/专题 ──
        label_parts = cog.label.split(" ", 1) if cog.label else [""]
        emoji_char = ""
        node_name = cog.label or ""
        if len(label_parts) == 2 and label_parts[0] and all(
            ord(c) > 0x1F000 for c in label_parts[0]
        ):
            emoji_char = label_parts[0]
            node_name = label_parts[1]

        # Build path from cognitive hierarchy (walk up parent chain)
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
                if len(pl) == 2 and pl[0] and all(
                    ord(c) > 0x1F000 for c in pl[0]
                ):
                    parent_emoji = pl[0]
                    parent_label = pl[1]
                # Recursively ensure grandparent exists
                self._ensure_conversation_parent_path(
                    user_id, cog_parent_id, data
                )

        # Create the topic if not present
        if topic_id not in data.topics:
            domain_id = parent_cog.parent if parent_cog else ""

            # Ensure domain exists in tree
            if domain_id and domain_id not in data.domains:
                # Find or create partition
                partition_id = ""
                if parent_cog:
                    pp_cog = cog_get_node(parent_cog.parent, user_id) if parent_cog.parent else None
                    if pp_cog:
                        partition_id = pp_cog.id
                        # Create partition if missing
                        if partition_id not in data.partitions:
                            pp_name = pp_cog.label or "自动创建"
                            pp_emoji = ""
                            ppl = pp_cog.label.split(" ", 1) if pp_cog.label else [""]
                            if len(ppl) == 2 and ppl[0] and all(
                                ord(c) > 0x1F000 for c in ppl[0]
                            ):
                                pp_emoji = ppl[0]
                                pp_name = ppl[1]
                            partition = Partition(
                                id=partition_id,
                                name=pp_name,
                                subject=pp_name,
                                direction="subject",
                                emoji=pp_emoji or "💬",
                                root_id=str(uuid4()),
                            )
                            data.partitions[partition_id] = partition
                            # Create virtual root node
                            root_node = TreeNode(
                                id=partition.root_id,
                                parent_id=partition.root_id,
                                partition_id=partition_id,
                                conversation_id="",
                                role="assistant",
                                content_blocks=[],
                                text_summary="[virtual_root]",
                            )
                            data.nodes[partition.root_id] = root_node

                # Create domain if missing
                domain_name = parent_label or "自动创建"
                domain = Domain(
                    id=domain_id,
                    partition_id=partition_id,
                    name=domain_name,
                    emoji=parent_emoji or "📚",
                )
                data.domains[domain_id] = domain

            # Create topic
            topic = Topic(
                id=topic_id,
                domain_id=domain_id,
                name=node_name or "自动创建",
                emoji=emoji_char or "📝",
            )
            data.topics[topic_id] = topic

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
            data = self._storage.load(user_id)

        config = self.LEVEL_CONFIG[level]

        if config["parent_key"] is not None:
            parent_level = self.LEVELS[self.LEVELS.index(level) - 1]
            parent_collection = self._get_collection(data, parent_level)
            if parent_id not in parent_collection:
                # For conversation level: auto-create missing parent path
                # from cognitive_nodes hierarchy
                if level == "conversation":
                    self._ensure_conversation_parent_path(
                        user_id, parent_id, data
                    )
                else:
                    raise ValueError(f"Parent {parent_level} {parent_id} not found")

        # ── 同名检测：同父节点下不允许重复名字（"新"开头的自动命名除外）──
        collection = self._get_collection(data, level)
        parent_key = config.get("parent_key")
        siblings = [
            e for e in collection.values()
            if (getattr(e, parent_key, None) == parent_id if parent_key else True)
        ] if parent_key else list(collection.values())
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

        # ── sync CognitiveNode ──
        self._sync_cog_create(
            user_id, entity, level, name, emoji, parent_id, data,
            auto_created=auto_created,
        )

        return entity

    # ═══════════════════════════════════════════════════════
    # 公开接口 – 分区 / 领域 / 专题 / 对话 CRUD
    # ═══════════════════════════════════════════════════════

    def create_partition(
        self, user_id, name, subject="", direction="subject", emoji="💬"
    ):
        data = self._storage.load(user_id)
        partition = self._create_node(
            user_id, "partition", None, name, emoji, data=data
        )
        self._storage.save(user_id, data)
        return partition

    def delete_partition(self, user_id, partition_id):
        data = self._storage.load(user_id)
        self._delete_node(user_id, partition_id, "partition", data=data)
        self._storage.save(user_id, data)

    def create_domain(self, user_id, partition_id, name, emoji="📚"):
        data = self._storage.load(user_id)
        domain = self._create_node(
            user_id, "domain", partition_id, name, emoji, data=data
        )
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

    def create_conversation(self, user_id, topic_id, name=""):
        data = self._storage.load(user_id)
        conv = self._create_node(user_id, "conversation", topic_id, name, data=data)
        self._storage.save(user_id, data)
        return conv

    def delete_conversation(self, user_id, conv_id):
        data = self._storage.load(user_id)
        self._delete_node(user_id, conv_id, "conversation", data=data)
        self._storage.save(user_id, data)

    # ═══════════════════════════════════════════════════════
    # 上下文查询 / 切换
    # ═══════════════════════════════════════════════════════

    def get_partition_context(self, user_id: str, partition_id: str) -> dict:
        data = self._storage.load(user_id)
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
        data = self._storage.load(user_id)
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
        self._storage.save(user_id, data)
        return conv

    # ═══════════════════════════════════════════════════════
    # 消息操作
    # ═══════════════════════════════════════════════════════

    def add_message(
        self,
        user_id,
        partition_id,
        role,
        content_blocks,
        text_summary="",
        conversation_id="",
    ) -> TreeNode:
        data = self._storage.load(user_id)
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
        # ── v6 Phase 3：同步写入 messages 表 ──
        try:
            from app.services.conversation.message_repository import save_message

            text_content = text_summary or ""
            save_message(
                user_id=user_id,
                message_id=node.id,
                conversation_id=conv.id,
                role=role,
                content=text_content,
                content_blocks=content_blocks,
                summary="",
                token_count=getattr(node, "token_count", 0),
            )
        except Exception:
            logger.exception("写入 messages 表失败 (不影响主流程)")
        # ──────────────────────────────────
        self._storage.save(user_id, data)
        return node

    def update_message_content(
        self,
        user_id: str,
        message_id: str,
        text: str,
    ) -> None:
        """覆写消息内容（原地更新，不创建版本）"""
        data = self._storage.load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            return
        node.content_blocks = [TextBlock(text=text)]
        node.text_summary = text
        # ── v6 Phase 3：同步更新 messages 表内容 ──
        try:
            from app.services.conversation.message_repository import save_message

            save_message(
                user_id=user_id,
                message_id=message_id,
                conversation_id=getattr(node, "conversation_id", ""),
                role=getattr(node, "role", "assistant"),
                content=text,
                content_blocks=[TextBlock(text=text)],
                summary="",
                token_count=0,
            )
        except Exception:
            logger.exception("更新 messages 表失败 (不影响主流程)")
        # ──────────────────────────────────
        self._storage.save(user_id, data)

    def modify_message(
        self, user_id, message_id, new_content_blocks, new_text_summary=""
    ) -> TreeNode:
        """创建消息新版本（分支），不移动子节点。
        旧版本保留自己的子树，新版本初始无子节点。
        conv.path 在用户消息位置截断，用新版本替换。
        """
        data = self._storage.load(user_id)
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
            has_modified_version=True,
        )

        # 添加到父节点的 children_ids（作为兄弟版本）
        parent = data.nodes.get(node.parent_id)
        if parent and new_node.id not in parent.children_ids:
            parent.children_ids.append(new_node.id)
        data.nodes[new_node.id] = new_node

        # 更新 conv.path：在用户消息位置截断，替换为新版本
        conv = data.conversations.get(node.conversation_id)
        if conv:
            replace_idx = None
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
                        replace_idx = i
                        break

            if replace_idx is not None:
                conv.path = conv.path[:replace_idx] + [new_node.id]
                conv.summary_dirty = True

        self._storage.save(user_id, data)
        return new_node

    def delete_message(self, user_id, message_id) -> None:
        data = self._storage.load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            return

        # 1. 收集目标节点及其整个子树（回复链）
        deleted_ids: set[str] = set()

        def collect(nid: str):
            n = data.nodes.get(nid)
            if not n or nid in deleted_ids:
                return
            deleted_ids.add(nid)
            for cid in n.children_ids:
                collect(cid)

        collect(message_id)

        # 2. 标记删除，从父节点移除
        for nid in deleted_ids:
            n = data.nodes.get(nid)
            if not n:
                continue
            n.is_deleted = True
            parent = data.nodes.get(n.parent_id)
            if parent and nid in parent.children_ids:
                parent.children_ids.remove(nid)

        # 3. 更新 conv.path：移除被删节点
        conv = data.conversations.get(node.conversation_id)
        if conv:
            conv.summary_dirty = True
            new_path = [nid for nid in conv.path if nid not in deleted_ids]
            if not new_path:
                for root_child_id in (data.nodes.get(node.parent_id).children_ids
                                      if data.nodes.get(node.parent_id) else []):
                    if root_child_id not in deleted_ids:
                        alt = data.nodes.get(root_child_id)
                        if alt and not alt.is_deleted:
                            new_path = [root_child_id]
                            def add_children(pid):
                                pn = data.nodes.get(pid)
                                if not pn:
                                    return
                                for pcid in pn.children_ids:
                                    pc = data.nodes.get(pcid)
                                    if pc and not pc.is_deleted:
                                        new_path.append(pcid)
                                        add_children(pcid)
                            add_children(root_child_id)
                            break
            conv.path = new_path

        self._storage.save(user_id, data)

    # ═══════════════════════════════════════════════════════
    # 子支操作
    # ═══════════════════════════════════════════════════════

    def create_sub_branch(
        self,
        user_id: str,
        source_conversation_id: str,
        source_message_id: str,
        char_start: int,
        char_end: int,
        quoted_text: str,
        initial_name: str = "",
    ) -> tuple:
        """创建子支会话，返回 (Conversation, SubBranchRef)"""
        from app.schemas.conversation import SubBranchRef

        data = self._storage.load(user_id)

        # 1. 验证源消息存在
        source_msg = data.nodes.get(source_message_id)
        if not source_msg:
            raise ValueError(f"Source message {source_message_id} not found")

        source_conv = data.conversations.get(source_conversation_id)
        if not source_conv:
            raise ValueError(f"Source conversation {source_conversation_id} not found")

        # 2. 创建子支会话（同 topic 下）
        topic_id = source_conv.topic_id
        name = initial_name or f"「{quoted_text[:15]}{'...' if len(quoted_text) > 15 else ''}」"
        conv = Conversation(topic_id=topic_id, name=name)

        # 3. 创建引用锚点
        ref = SubBranchRef(
            source_message_id=source_message_id,
            char_start=char_start,
            char_end=char_end,
            quoted_text=quoted_text,
            child_conversation_id=conv.id,
        )

        # 4. 设置子支会话的父会话信息
        conv.parent_conversation_id = source_conversation_id
        conv.parent_sub_branch_ref = ref
        conv.depth = source_conv.depth + 1

        # 5. 更新源消息的子支标识
        source_msg.has_sub_branches = True
        if conv.id not in source_msg.sub_branch_ids:
            source_msg.sub_branch_ids.append(conv.id)

        # 6. 更新源会话的子支列表
        if conv.id not in source_conv.sub_branch_ids:
            source_conv.sub_branch_ids.append(conv.id)

        # 7. 保存
        data.conversations[conv.id] = conv
        data.nodes[source_message_id] = source_msg
        data.conversations[source_conversation_id] = source_conv
        self._storage.save(user_id, data)

        return conv, ref

    def get_sub_branches(self, user_id: str, message_id: str) -> list[dict]:
        """获取消息的子支列表"""
        data = self._storage.load(user_id)
        msg = data.nodes.get(message_id)
        if not msg or not msg.has_sub_branches:
            return []

        result = []
        for sb_id in msg.sub_branch_ids:
            conv = data.conversations.get(sb_id)
            if not conv:
                continue
            ref = conv.parent_sub_branch_ref
            result.append({
                "conversation_id": conv.id,
                "quoted_text": ref.quoted_text if ref else "",
                "message_count": len(conv.path),
                "summary": conv.summary or "",
                "name": conv.name,
            })
        return result

    def get_sub_branch_parent(self, user_id: str, conv_id: str) -> dict | None:
        """获取子支的父会话信息"""
        data = self._storage.load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv or not conv.parent_conversation_id:
            return None

        ref = conv.parent_sub_branch_ref
        return {
            "parent_conversation_id": conv.parent_conversation_id,
            "source_message_id": ref.source_message_id if ref else "",
            "char_start": ref.char_start if ref else 0,
            "char_end": ref.char_end if ref else 0,
            "quoted_text": ref.quoted_text if ref else "",
        }

    def delete_sub_branch(self, user_id: str, conv_id: str) -> dict:
        """删除子支会话，返回父消息信息"""
        data = self._storage.load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv:
            raise ValueError(f"Sub-branch {conv_id} not found")

        ref = conv.parent_sub_branch_ref
        parent_conv_id = conv.parent_conversation_id
        source_msg_id = ref.source_message_id if ref else ""

        # 1. 从源消息移除子支引用
        if source_msg_id:
            source_msg = data.nodes.get(source_msg_id)
            if source_msg:
                if conv_id in source_msg.sub_branch_ids:
                    source_msg.sub_branch_ids.remove(conv_id)
                if not source_msg.sub_branch_ids:
                    source_msg.has_sub_branches = False
                    source_msg.sub_branch_summaries = []
                else:
                    source_msg.sub_branch_summaries = [
                        s for s in source_msg.sub_branch_summaries
                        if s.get("conversation_id") != conv_id
                    ]
                data.nodes[source_msg_id] = source_msg

        # 2. 从父会话移除子支引用
        if parent_conv_id:
            parent_conv = data.conversations.get(parent_conv_id)
            if parent_conv:
                if conv_id in parent_conv.sub_branch_ids:
                    parent_conv.sub_branch_ids.remove(conv_id)
                data.conversations[parent_conv_id] = parent_conv

        # 3. 软删除子支会话的所有消息
        for nid in conv.path:
            node = data.nodes.get(nid)
            if node:
                node.is_deleted = True

        # 4. 软删除子支会话
        conv.is_active = False
        data.conversations[conv_id] = conv

        self._storage.save(user_id, data)

        remaining_count = 0
        if source_msg_id:
            source_msg = data.nodes.get(source_msg_id)
            if source_msg:
                remaining_count = len(source_msg.sub_branch_ids)

        return {
            "ok": True,
            "parent_message_id": source_msg_id,
            "parent_conversation_id": parent_conv_id,
            "remaining_count": remaining_count,
        }

    def update_sub_branch_summary(
        self, user_id: str, conv_id: str, summary: str
    ) -> None:
        """更新子支摘要，写入父消息的 sub_branch_summaries"""
        data = self._storage.load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv or not conv.parent_sub_branch_ref:
            return

        ref = conv.parent_sub_branch_ref
        source_msg_id = ref.source_message_id
        source_msg = data.nodes.get(source_msg_id)
        if not source_msg:
            return

        # 更新或添加摘要
        existing = False
        for s in source_msg.sub_branch_summaries:
            if s.get("conversation_id") == conv_id:
                s["summary"] = summary
                existing = True
                break

        if not existing:
            source_msg.sub_branch_summaries.append({
                "conversation_id": conv_id,
                "quoted_text": ref.quoted_text,
                "summary": summary,
            })

        data.nodes[source_msg_id] = source_msg
        self._storage.save(user_id, data)

    # ═══════════════════════════════════════════════════════
    # 临时分区管理
    # ═══════════════════════════════════════════════════════

    TEMP_PARTITION_NAME = "💬 临时"

    def _ensure_temp_partition(
        self, user_id: str, data: UserData
    ) -> tuple[Partition, Domain]:
        """确保临时分区+占位领域存在，返回 (partition, domain)。"""
        # Find existing temp partition
        for p in data.partitions.values():
            if getattr(p, "is_temp", False):
                temp_partition = p
                break
        else:
            # Create temp partition
            temp_partition = Partition(
                name=self.TEMP_PARTITION_NAME,
                subject="",
                direction="subject",
                emoji="💬",
                color="#888888",
                root_id=str(uuid4()),
                is_temp=True,
            )
            data.partitions[temp_partition.id] = temp_partition
            # Create virtual root node
            root_node = TreeNode(
                id=temp_partition.root_id,
                parent_id=temp_partition.root_id,
                partition_id=temp_partition.id,
                conversation_id="",
                role="assistant",
                content_blocks=[],
                text_summary="[virtual_root]",
            )
            data.nodes[temp_partition.root_id] = root_node

        # Find or create a single domain for the temp partition
        temp_domain = None
        for d in data.domains.values():
            if d.partition_id == temp_partition.id:
                temp_domain = d
                break
        if not temp_domain:
            temp_domain = Domain(
                partition_id=temp_partition.id,
                name="💬 临时",
                emoji="💬",
            )
            data.domains[temp_domain.id] = temp_domain

        return temp_partition, temp_domain
