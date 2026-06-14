"""Tree message operations — add/update/modify/delete messages

DirectoryNode 版本：使用 directory_nodes 替代旧 partitions/conversations 模型。
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

logger = logging.getLogger(__name__)

from app.infrastructure.db.events_repository import Event, get_events_repo
from app.schemas.directory_node import DirectoryNode, MessageNode
from app.schemas.conversation import TextBlock, TreeNode, UserData
from app.services.common import get_data_repo


class TreeMessagesMixin:
    """消息 CRUD — add_message, modify_message, delete_message."""

    def add_message(
        self, user_id, dir_id, role, content_blocks,
        text_summary="", conversation_id="", agent_label="",
    ) -> TreeNode | MessageNode:
        """添加消息到对话。

        dir_id 和 conversation_id 二选一：
        - 有 conversation_id → 使用 directory_nodes 中 conv 节点的 conv_message_ids
        - 有 dir_id → 在目录下查找/创建临时对话
        """
        data = self._get_data_repo().load(user_id)

        conv_node: DirectoryNode | None = None
        if conversation_id:
            conv_node = data.directory_nodes.get(conversation_id)

        if not conv_node:
            # 自动创建临时对话
            if not dir_id:
                temp_dir = self._ensure_temp_dir(user_id, data)
                dir_id = temp_dir.id
            # 尝试找目录下已有临时 conv
            for dn in data.directory_nodes.values():
                if dn.parent_id == dir_id and dn.node_type == "conv" and dn.kind == "temp":
                    conv_node = dn
                    break
            if not conv_node:
                conv_node = self._create_conv_node(data, dir_id, "临时会话", "temp")
                data = self._get_data_repo().load(user_id)
                conv_node = data.directory_nodes.get(conv_node.id)

        # 创建消息节点
        text_content = ""
        if content_blocks:
            for b in content_blocks:
                if isinstance(b, TextBlock) and b.text:
                    text_content = b.text
                    break
                elif isinstance(b, dict) and b.get("type") == "text":
                    text_content = b.get("text", "")
                    break

        node = MessageNode(
            directory_id=conv_node.id,
            parent_id=conv_node.conv_message_ids[-1] if conv_node.conv_message_ids else None,
            role=role, content=text_content, text_summary=text_summary or text_content,
        )
        # 同时也存入 data.nodes 以兼容旧代码
        data.nodes[node.id] = node
        conv_node.conv_message_ids.append(node.id)
        conv_node.updated_at = time.time()

        self._get_data_repo().save(user_id, data)

        # 触发组织事件: 标记 conv 需要 organize (Detector 轮询时按阈值触发)
        try:
            repo = get_events_repo()
            repo.insert(Event(
                id=f"evt_{uuid4().hex[:12]}",
                user_id=user_id,
                event_type="organize",
                source_type="conversation",
                source_id=conv_node.id,
                status="pending",
            ))
        except Exception:
            logger.debug("插入 organize 事件失败", exc_info=True)

        return node

    def modify_message(
        self, user_id, message_id, new_content_blocks, new_text_summary="",
    ) -> TreeNode:
        """编辑消息 — 创建新版本。"""
        from app.schemas.conversation import TreeNode as OldTreeNode

        data = self._get_data_repo().load(user_id)
        old_node = data.nodes.get(message_id)
        if not old_node:
            raise ValueError(f"消息 {message_id} 不存在")

        old_dir_id = getattr(old_node, "directory_id", getattr(old_node, "conversation_id", ""))
        old_parent_id = getattr(old_node, "parent_id", "")

        new_node = OldTreeNode(
            parent_id=old_parent_id,
            partition_id=getattr(old_node, "partition_id", ""),
            conversation_id=old_dir_id,
            role=old_node.role,
            content_blocks=new_content_blocks,
            text_summary=new_text_summary,
        )
        parent = data.nodes.get(old_parent_id)
        if parent and new_node.id not in parent.children_ids:
            parent.children_ids.append(new_node.id)
        data.nodes[new_node.id] = new_node

        # 追加到 conv 的 message_ids
        conv = data.directory_nodes.get(old_dir_id)
        if conv and conv.node_type == "conv":
            if new_node.id not in conv.conv_message_ids:
                conv.conv_message_ids.append(new_node.id)

        self._get_data_repo().save(user_id, data)
        return new_node

    def delete_message(self, user_id, message_id) -> None:
        """删除消息。"""
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
            for cid in getattr(n, "children_ids", []):
                collect(cid)

        collect(message_id)

        for nid in deleted_ids:
            n = data.nodes.get(nid)
            if not n:
                continue
            n.is_deleted = True
            parent = data.nodes.get(getattr(n, "parent_id", ""))
            if parent and nid in getattr(parent, "children_ids", []):
                parent.children_ids.remove(nid)

        # 从 conv 的 conv_message_ids 移除
        dir_id = getattr(node, "directory_id", getattr(node, "conversation_id", ""))
        conv = data.directory_nodes.get(dir_id)
        if conv and conv.node_type == "conv":
            conv.conv_message_ids = [
                mid for mid in conv.conv_message_ids if mid not in deleted_ids
            ]
            conv.updated_at = time.time()

        self._get_data_repo().save(user_id, data)

    def update_message_content(self, user_id: str, message_id: str, text: str) -> None:
        """更新消息文本内容。"""
        data = self._get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            return
        node.content = text
        node.text_summary = text
        self._get_data_repo().save(user_id, data)
