"""Tree sub-branch operations — create / get / delete / update summary"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from app.schemas.conversation import Conversation, SubBranchRef, UserData
from app.services.common import get_data_repo


class TreeSubBranchMixin:
    """子支操作 — create_sub_branch, get_sub_branches, get_sub_branch_parent,
    delete_sub_branch, update_sub_branch_summary."""

    def create_sub_branch(
        self, user_id: str, source_conversation_id: str,
        source_message_id: str, char_start: int, char_end: int,
        quoted_text: str, initial_name: str = "",
    ):
        data = self._get_data_repo().load(user_id)

        source_msg = data.nodes.get(source_message_id)
        if not source_msg:
            raise ValueError(f"Source message {source_message_id} not found")

        source_conv = data.conversations.get(source_conversation_id)
        if not source_conv:
            raise ValueError(f"Source conversation {source_conversation_id} not found")

        if source_conv.is_temporary:
            raise ValueError("临时会话不支持创建子支，请切换到一个学习专题下再创建")

        # 继承父对话的挂载关系
        name = initial_name or (
            f"「{quoted_text[:15]}{'...' if len(quoted_text) > 15 else ''}」"
        )
        conv = Conversation(
            parent_id=source_conv.parent_id,
            parent_type=source_conv.parent_type,
            type=source_conv.type,
            partition_id=source_conv.partition_id,
            domain_id=source_conv.domain_id,
            topic_id=source_conv.topic_id,
            name=name,
        )

        ref = SubBranchRef(
            source_message_id=source_message_id,
            char_start=char_start, char_end=char_end,
            quoted_text=quoted_text, child_conversation_id=conv.id,
        )
        conv.parent_conversation_id = source_conversation_id
        conv.parent_sub_branch_ref = ref
        conv.depth = source_conv.depth + 1

        source_msg.has_sub_branches = True
        if conv.id not in source_msg.sub_branch_ids:
            source_msg.sub_branch_ids.append(conv.id)
        if conv.id not in source_conv.sub_branch_ids:
            source_conv.sub_branch_ids.append(conv.id)

        data.conversations[conv.id] = conv
        data.nodes[source_message_id] = source_msg
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
        data = self._get_data_repo().load(user_id)
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
        data = self._get_data_repo().load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv:
            raise ValueError(f"Sub-branch {conv_id} not found")

        ref = conv.parent_sub_branch_ref
        parent_conv_id = conv.parent_conversation_id
        source_msg_id = ref.source_message_id if ref else ""

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

        if parent_conv_id:
            parent_conv = data.conversations.get(parent_conv_id)
            if parent_conv:
                if conv_id in parent_conv.sub_branch_ids:
                    parent_conv.sub_branch_ids.remove(conv_id)
                data.conversations[parent_conv_id] = parent_conv

        for nid in conv.path:
            node = data.nodes.get(nid)
            if node:
                node.is_deleted = True

        conv.is_active = False
        data.conversations[conv_id] = conv
        self._get_data_repo().save(user_id, data)

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
        self, user_id: str, conv_id: str, summary: str,
    ) -> None:
        data = self._get_data_repo().load(user_id)
        conv = data.conversations.get(conv_id)
        if not conv or not conv.parent_sub_branch_ref:
            return

        ref = conv.parent_sub_branch_ref
        source_msg_id = ref.source_message_id
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
            source_msg.sub_branch_summaries.append({
                "conversation_id": conv_id,
                "quoted_text": ref.quoted_text,
                "summary": summary,
            })

        data.nodes[source_msg_id] = source_msg
        self._get_data_repo().save(user_id, data)
