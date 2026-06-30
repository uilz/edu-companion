"""Tree sub-branch operations — create / get / delete / update summary

DirectoryNode only — all conversations are DirectoryNode with node_type="conv".
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from app.schemas.conversation import SubBranchRef, UserData
from app.schemas.directory_node import DirectoryNode, MessageNode


class TreeSubBranchMixin:
    """子支操作 — create_sub_branch, get_sub_branches, get_sub_branch_parent,
    delete_sub_branch, update_sub_branch_summary."""

    def create_sub_branch(
        self, user_id: str, source_conv_id: str,
        source_message_id: str, char_start: int, char_end: int,
        quoted_text: str, initial_name: str = "", mode: str = "tutor",
    ):
        data = self._get_data_repo().load(user_id)

        source_msg = data.nodes.get(source_message_id)
        if not source_msg:
            raise ValueError(f"Source message {source_message_id} not found")

        source_conv = data.directory_nodes.get(source_conv_id)
        if not source_conv:
            raise ValueError(f"Source conversation {source_conv_id} not found")

        # 继承父对话的挂载关系
        name = initial_name or (
            f"「{quoted_text[:15]}{'...' if len(quoted_text) > 15 else ''}」"
        )

        # 创建子支 conv 节点
        conv = DirectoryNode(
            user_id=user_id,
            parent_id=source_conv.parent_id,
            node_type="conv",
            kind="general",
            name=name,
            path=source_conv.path + [source_conv.id],
        )
        # 存储对话模式
        conv.metadata["mode"] = mode
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

        ref = SubBranchRef(
            source_message_id=source_message_id,
            char_start=char_start, char_end=char_end,
            quoted_text=quoted_text, child_conv_id=conv.id,
        )

        # 子支关系
        conv.metadata["parent_conv_id"] = source_conv_id
        source_conv.metadata.setdefault("sub_branch_ids", [])
        if conv.id not in source_conv.metadata["sub_branch_ids"]:
            source_conv.metadata["sub_branch_ids"].append(conv.id)

        source_msg.has_sub_branches = True
        if conv.id not in source_msg.sub_branch_ids:
            source_msg.sub_branch_ids.append(conv.id)

        data.nodes[source_message_id] = source_msg
        data.directory_nodes[source_conv.id] = source_conv
        self._get_data_repo().save(user_id, data)

        return conv, ref

    def get_sub_branches(self, user_id: str, message_id: str) -> list[dict]:
        data = self._get_data_repo().load(user_id)
        msg = data.nodes.get(message_id)
        if not msg or not msg.has_sub_branches:
            return []

        result = []
        for sb_id in msg.sub_branch_ids:
            conv = data.directory_nodes.get(sb_id)
            if not conv:
                continue
            quoted = conv.metadata.get("quoted_text", "")
            msg_count = len(conv.conv_message_ids)
            s_name = conv.name

            result.append({
                "conv_id": conv.id,
                "quoted_text": quoted,
                "message_count": msg_count,
                "summary": "",  # TODO: implement summary tracking
                "name": s_name or getattr(conv, "name", ""),
            })
        return result

    def get_sub_branch_parent(self, user_id: str, conv_id: str) -> dict | None:
        data = self._get_data_repo().load(user_id)
        conv = data.directory_nodes.get(conv_id)
        if not conv:
            return None

        parent_conv_id = conv.metadata.get("parent_conv_id", "")
        if not parent_conv_id:
            return None

        return {
            "parent_conv_id": parent_conv_id,
            "source_message_id": "",
            "char_start": 0,
            "char_end": 0,
            "quoted_text": "",
        }

    def delete_sub_branch(self, user_id: str, conv_id: str) -> dict:
        data = self._get_data_repo().load(user_id)
        conv = data.directory_nodes.get(conv_id)
        if not conv:
            raise ValueError(f"Sub-branch {conv_id} not found")

        # 获取源消息 ID 和父 conv ID
        source_msg_id = ""
        parent_conv_id = conv.metadata.get("parent_conv_id", "")

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
                        if s.get("conv_id") != conv_id
                    ]
                data.nodes[source_msg_id] = source_msg

        # 清理父 conv
        parent_conv_data = data.directory_nodes.get(parent_conv_id) if parent_conv_id else None
        if parent_conv_data:
            sb_ids = parent_conv_data.metadata.get("sub_branch_ids", [])
            if conv_id in sb_ids:
                sb_ids.remove(conv_id)
            data.directory_nodes[parent_conv_data.id] = parent_conv_data

        # 标记消息为已删除
        for mid in conv.conv_message_ids:
            node = data.nodes.get(mid)
            if node:
                node.is_deleted = True
        data.directory_nodes.pop(conv_id, None)

        remaining_count = 0
        if source_msg_id:
            source_msg = data.nodes.get(source_msg_id)
            if source_msg:
                remaining_count = len(source_msg.sub_branch_ids)

        self._get_data_repo().save(user_id, data)
        return {
            "ok": True,
            "parent_message_id": source_msg_id,
            "parent_conv_id": parent_conv_id,
            "remaining_count": remaining_count,
        }

    def update_sub_branch_summary(
        self, user_id: str, conv_id: str, summary: str,
    ) -> None:
        data = self._get_data_repo().load(user_id)
        conv = data.directory_nodes.get(conv_id)
        if not conv:
            return

        # 获取 source message
        source_msg_id = conv.metadata.get("source_message_id", "")

        if not source_msg_id:
            return

        source_msg = data.nodes.get(source_msg_id)
        if not source_msg:
            return

        existing = False
        for s in source_msg.sub_branch_summaries:
            if s.get("conv_id") == conv_id:
                s["summary"] = summary
                existing = True
                break

        if not existing:
            quoted = conv.metadata.get("quoted_text", "")
            source_msg.sub_branch_summaries.append({
                "conv_id": conv_id,
                "quoted_text": quoted,
                "summary": summary,
            })

        data.nodes[source_msg_id] = source_msg
        self._get_data_repo().save(user_id, data)
