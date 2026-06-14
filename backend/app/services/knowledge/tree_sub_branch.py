"""Tree sub-branch operations — create / get / delete / update summary

DirectoryNode 兼容版本：使用 directory_nodes 中的 conv 节点。
向后兼容旧 data.conversations 数据。
"""

from __future__ import annotations

import logging
from uuid import uuid4

logger = logging.getLogger(__name__)

from app.schemas.conversation import Conversation, SubBranchRef, UserData
from app.schemas.directory_node import DirectoryNode, MessageNode


class TreeSubBranchMixin:
    """子支操作 — create_sub_branch, get_sub_branches, get_sub_branch_parent,
    delete_sub_branch, update_sub_branch_summary."""

    def _get_conv(self, data, conv_id: str):
        """从 directory_nodes 或旧 conversations 中取对话。"""
        dn = data.directory_nodes.get(conv_id)
        if dn and dn.node_type == "conv":
            return dn
        return data.conversations.get(conv_id)

    def create_sub_branch(
        self, user_id: str, source_conversation_id: str,
        source_message_id: str, char_start: int, char_end: int,
        quoted_text: str, initial_name: str = "",
    ):
        data = self._get_data_repo().load(user_id)

        source_msg = data.nodes.get(source_message_id)
        if not source_msg:
            raise ValueError(f"Source message {source_message_id} not found")

        source_conv = self._get_conv(data, source_conversation_id)
        if not source_conv:
            raise ValueError(f"Source conversation {source_conversation_id} not found")

        # 检查临时 conv（DirectoryNode 用 kind, 旧 Conversation 用 is_temporary）
        is_temp = False
        if isinstance(source_conv, DirectoryNode):
            is_temp = source_conv.kind == "temp"
        else:
            is_temp = getattr(source_conv, "is_temporary", False)
        if is_temp:
            raise ValueError("临时会话不支持创建子支，请切换到一个学习专题下再创建")

        # 继承父对话的挂载关系
        name = initial_name or (
            f"「{quoted_text[:15]}{'...' if len(quoted_text) > 15 else ''}」"
        )

        # 创建子支 conv 节点
        if isinstance(source_conv, DirectoryNode):
            conv = DirectoryNode(
                user_id=user_id,
                parent_id=source_conv.parent_id,
                node_type="conv",
                kind="general",
                name=name,
                path=source_conv.path + [source_conv.id],
            )
            data.directory_nodes[conv.id] = conv
            # 创建根消息
            root_msg = MessageNode(
                directory_id=conv.id, parent_id=None,
                role="assistant", content="", text_summary=name,
            )
            conv.conv_message_ids.append(root_msg.id)
            data.nodes[root_msg.id] = root_msg
            # 父目录添加子引用
            parent_dir = data.directory_nodes.get(source_conv.parent_id)
            if parent_dir:
                parent_dir.add_child(conv.id)
        else:
            # 旧 Conversation 模型
            conv = Conversation(
                parent_id=getattr(source_conv, "parent_id", ""),
                parent_type=getattr(source_conv, "parent_type", ""),
                type=getattr(source_conv, "type", "normal"),
                partition_id=getattr(source_conv, "partition_id", ""),
                domain_id=getattr(source_conv, "domain_id", ""),
                topic_id=getattr(source_conv, "topic_id", ""),
                name=name,
            )
            data.conversations[conv.id] = conv

        ref = SubBranchRef(
            source_message_id=source_message_id,
            char_start=char_start, char_end=char_end,
            quoted_text=quoted_text, child_conversation_id=conv.id,
        )

        # 子支关系
        if isinstance(source_conv, DirectoryNode):
            conv.metadata["parent_conversation_id"] = source_conversation_id
            source_conv.metadata.setdefault("sub_branch_ids", [])
            if conv.id not in source_conv.metadata["sub_branch_ids"]:
                source_conv.metadata["sub_branch_ids"].append(conv.id)
        else:
            conv.parent_conversation_id = source_conversation_id
            conv.parent_sub_branch_ref = ref
            conv.depth = getattr(source_conv, "depth", 0) + 1
            if conv.id not in source_conv.sub_branch_ids:
                source_conv.sub_branch_ids.append(conv.id)

        source_msg.has_sub_branches = True
        if conv.id not in source_msg.sub_branch_ids:
            source_msg.sub_branch_ids.append(conv.id)

        data.nodes[source_message_id] = source_msg
        if isinstance(source_conv, DirectoryNode):
            data.directory_nodes[source_conv.id] = source_conv
        else:
            data.conversations[source_conversation_id] = source_conv
        self._get_data_repo().save(user_id, data)

        return conv, ref

    def get_sub_branches(self, user_id: str, message_id: str) -> list[dict]:
        data = self._get_data_repo().load(user_id)
        msg = data.nodes.get(message_id)
        if not msg or not msg.has_sub_branches:
            return []

        result = []
        for sb_id in msg.sub_branch_ids:
            conv = self._get_conv(data, sb_id)
            if not conv:
                continue
            ref = None
            quoted = ""
            msg_count = 0
            s_name = ""

            if isinstance(conv, DirectoryNode):
                quoted = conv.metadata.get("quoted_text", "")
                msg_count = len(conv.conv_message_ids)
                s_name = conv.name
            else:
                ref = conv.parent_sub_branch_ref
                quoted = ref.quoted_text if ref else ""
                msg_count = len(conv.path)

            result.append({
                "conversation_id": conv.id,
                "quoted_text": quoted,
                "message_count": msg_count,
                "summary": "",  # TODO: implement summary tracking
                "name": s_name or getattr(conv, "name", ""),
            })
        return result

    def get_sub_branch_parent(self, user_id: str, conv_id: str) -> dict | None:
        data = self._get_data_repo().load(user_id)
        conv = self._get_conv(data, conv_id)
        if not conv:
            return None

        parent_conv_id = ""
        source_msg_id = ""
        c_start = 0
        c_end = 0
        quoted = ""

        if isinstance(conv, DirectoryNode):
            parent_conv_id = conv.metadata.get("parent_conversation_id", "")
        else:
            parent_conv_id = getattr(conv, "parent_conversation_id", "")
            ref = conv.parent_sub_branch_ref
            if ref:
                source_msg_id = ref.source_message_id
                c_start = ref.char_start
                c_end = ref.char_end
                quoted = ref.quoted_text

        if not parent_conv_id:
            return None
        return {
            "parent_conversation_id": parent_conv_id,
            "source_message_id": source_msg_id,
            "char_start": c_start,
            "char_end": c_end,
            "quoted_text": quoted,
        }

    def delete_sub_branch(self, user_id: str, conv_id: str) -> dict:
        data = self._get_data_repo().load(user_id)
        conv = self._get_conv(data, conv_id)
        if not conv:
            raise ValueError(f"Sub-branch {conv_id} not found")

        # 获取源消息 ID 和父 conv ID
        source_msg_id = ""
        parent_conv_id = ""
        if isinstance(conv, DirectoryNode):
            parent_conv_id = conv.metadata.get("parent_conversation_id", "")
        else:
            ref = conv.parent_sub_branch_ref
            if ref:
                source_msg_id = ref.source_message_id
            parent_conv_id = getattr(conv, "parent_conversation_id", "")

        # 从 data.conversations 或子支条目清理
        if not isinstance(conv, DirectoryNode):
            source_msg_id = conv.parent_sub_branch_ref.source_message_id if conv.parent_sub_branch_ref else ""
            parent_conv_id = conv.parent_conversation_id

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

        # 清理父 conv
        parent_conv_data = self._get_conv(data, parent_conv_id) if parent_conv_id else None
        if parent_conv_data:
            if isinstance(parent_conv_data, DirectoryNode):
                sb_ids = parent_conv_data.metadata.get("sub_branch_ids", [])
                if conv_id in sb_ids:
                    sb_ids.remove(conv_id)
                data.directory_nodes[parent_conv_data.id] = parent_conv_data
            else:
                if conv_id in parent_conv_data.sub_branch_ids:
                    parent_conv_data.sub_branch_ids.remove(conv_id)
                data.conversations[parent_conv_id] = parent_conv_data

        # 标记消息为已删除
        if isinstance(conv, DirectoryNode):
            for mid in conv.conv_message_ids:
                node = data.nodes.get(mid)
                if node:
                    node.is_deleted = True
            data.directory_nodes.pop(conv_id, None)
        else:
            for nid in conv.path:
                node = data.nodes.get(nid)
                if node:
                    node.is_deleted = True
            data.conversations.pop(conv_id, None)

        remaining_count = 0
        if source_msg_id:
            source_msg = data.nodes.get(source_msg_id)
            if source_msg:
                remaining_count = len(source_msg.sub_branch_ids)

        self._get_data_repo().save(user_id, data)
        return {
            "ok": True,
            "parent_message_id": source_msg_id,
            "parent_conversation_id": parent_conv_id,
            "remaining_count": remaining_count,
        }

    def update_sub_branch_summary(
        self, user_id: str, conv_id: str, summary: str,
    ) -> None:
        data = self._get_data_repo().load(user_id)
        conv = self._get_conv(data, conv_id)
        if not conv:
            return

        # 获取 source message
        source_msg_id = ""
        if isinstance(conv, DirectoryNode):
            source_msg_id = conv.metadata.get("source_message_id", "")
        else:
            ref = conv.parent_sub_branch_ref
            if ref:
                source_msg_id = ref.source_message_id

        if not source_msg_id:
            return

        source_msg = data.nodes.get(source_msg_id)
        if not source_msg:
            return

        existing = False
        for s in source_msg.sub_branch_summaries:
            if s.get("conversation_id") == conv_id:
                s["summary"] = summary
                existing = True
                break

        if not existing:
            quoted = ""
            if isinstance(conv, DirectoryNode):
                quoted = conv.metadata.get("quoted_text", "")
            else:
                ref = conv.parent_sub_branch_ref
                if ref:
                    quoted = ref.quoted_text
            source_msg.sub_branch_summaries.append({
                "conversation_id": conv_id,
                "quoted_text": quoted,
                "summary": summary,
            })

        data.nodes[source_msg_id] = source_msg
        self._get_data_repo().save(user_id, data)
