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
        text_summary="", conv_id="", agent_label="",
        parent_id=None,
    ) -> TreeNode | MessageNode:
        """添加消息到对话。

        parent_id: 指定父消息 ID。
          - 提供时，新消息作为该消息的子节点插入（在 conv_message_ids 中紧随其后）
          - "head" 时，插入到 conv_message_ids 开头（parent 为 None）
          - None 时，沿用当前行为（父为最后一条消息）
        conv_id 优先；备选 dir_id。需至少有一个有效。
        """
        data = self._get_data_repo().load(user_id)

        conv_node: DirectoryNode | None = None
        if conv_id:
            conv_node = data.directory_nodes.get(conv_id)

        if not conv_node and dir_id:
            # 找目录下的第一个 conv 节点
            for dn in data.directory_nodes.values():
                if dn.parent_id == dir_id and dn.node_type == "conv":
                    conv_node = dn
                    break

        if not conv_node:
            raise ValueError(f"未找到对话节点 (conv_id={conv_id}, dir_id={dir_id})")

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

        # 确定 parent_id 及插入位置
        if parent_id == "head":
            # 插入到对话开头
            resolved_parent = None
            insert_pos = 0
        elif parent_id and parent_id in conv_node.conv_message_ids:
            # 插入到指定消息之后
            resolved_parent = parent_id
            insert_pos = conv_node.conv_message_ids.index(parent_id) + 1
        else:
            # 默认：父为最后一条消息
            resolved_parent = conv_node.conv_message_ids[-1] if conv_node.conv_message_ids else None
            insert_pos = len(conv_node.conv_message_ids)

        node = MessageNode(
            directory_id=conv_node.id,
            parent_id=resolved_parent,
            role=role, content=text_content, text_summary=text_summary or text_content,
            content_blocks=[
                b.model_dump(mode="json") if hasattr(b, "model_dump") else b
                for b in (content_blocks or [])
            ],
            status="done",
            stream_started_at=None,
        )
        # 同时也存入 data.nodes 以兼容旧代码
        data.nodes[node.id] = node
        conv_node.conv_message_ids.insert(insert_pos, node.id)
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

        old_dir_id = getattr(old_node, "directory_id", getattr(old_node, "conv_id", ""))
        old_parent_id = getattr(old_node, "parent_id", "")

        new_node = OldTreeNode(
            parent_id=old_parent_id,
            directory_id=old_dir_id,
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
        dir_id = getattr(node, "directory_id", getattr(node, "conv_id", ""))
        conv = data.directory_nodes.get(dir_id)
        if conv and conv.node_type == "conv":
            conv.conv_message_ids = [
                mid for mid in conv.conv_message_ids if mid not in deleted_ids
            ]
            conv.updated_at = time.time()

        self._get_data_repo().save(user_id, data)

    def update_message_content(self, user_id: str, message_id: str, text: str) -> None:
        """更新消息文本内容，保留非 text 块（如 tool / reasoning）。"""
        data = self._get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            return
        node.content = text
        node.text_summary = text
        # 保留非 text 块（tool / reasoning 等），只替换 text 块的位置
        existing_non_text = [b for b in (node.content_blocks or []) if isinstance(b, dict) and b.get("type") != "text"]
        node.content_blocks = [*existing_non_text, {"type": "text", "text": text}]
        self._get_data_repo().save(user_id, data)

    def add_shell_message(self, user_id, conv_id, agent_label="", parent_id=None) -> MessageNode:
        """添加 shell 消息 (status=streaming) 到对话，返回预分配的 msg_id。

        parent_id: 指定父消息 ID。
          - 提供时，新消息作为该消息的子节点插入
          - None 时，沿用当前行为（父为最后一条消息）
        """
        data = self._get_data_repo().load(user_id)
        conv_node = data.directory_nodes.get(conv_id)
        if not conv_node:
            raise ValueError(f"对话节点不存在: {conv_id}")

        # 确定 parent_id 及插入位置
        if parent_id and parent_id in conv_node.conv_message_ids:
            resolved_parent = parent_id
            insert_pos = conv_node.conv_message_ids.index(parent_id) + 1
        else:
            resolved_parent = conv_node.conv_message_ids[-1] if conv_node.conv_message_ids else None
            insert_pos = len(conv_node.conv_message_ids)

        node = MessageNode(
            directory_id=conv_node.id,
            parent_id=resolved_parent,
            role="assistant",
            content="",
            text_summary="",
            content_blocks=[],
            agent_label=agent_label,
            status="streaming",
            stream_started_at=time.time(),
        )
        data.nodes[node.id] = node
        conv_node.conv_message_ids.insert(insert_pos, node.id)
        conv_node.updated_at = time.time()
        self._get_data_repo().save(user_id, data)
        return node

    def update_shell_to_done(self, user_id, message_id, content_blocks, text_summary="") -> MessageNode:
        """将 shell 消息 (status=streaming) 更新为完成态。"""
        data = self._get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            raise ValueError(f"消息 {message_id} 不存在")

        # Extract text content from first text block
        text_content = ""
        if content_blocks:
            for b in content_blocks:
                if isinstance(b, dict) and b.get("type") == "text":
                    text_content = b.get("text", "")
                    break

        node.content = text_content
        node.text_summary = text_summary or text_content
        node.content_blocks = content_blocks
        node.status = "done"
        node.stream_started_at = None
        self._get_data_repo().save(user_id, data)
        return node

    def update_message_status(self, user_id, message_id, content_blocks, text_summary="", content="") -> MessageNode:
        """更新消息状态为 done，更新内容字段。"""
        data = self._get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            raise ValueError(f"消息 {message_id} 不存在")

        node.content_blocks = content_blocks
        node.text_summary = text_summary
        node.content = content
        node.status = "done"
        node.stream_started_at = None
        self._get_data_repo().save(user_id, data)
        return node
