"""
Conversation Service Protocol — 对话模块对外契约

其他模块只能通过此接口调用对话功能。
实现类: domain/conversation/service_impl.py
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.conversation import TreeNode, Branch, Partition, ResponseBlock
from shared.constants import DEFAULT_USER_ID


@runtime_checkable
class ConversationService(Protocol):
    """对话模块对外契约"""

    async def send_message(
        self,
        partition_id: str,
        branch_id: str,
        content: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> TreeNode:
        """发送消息并获取 AI 回复"""
        ...

    async def create_partition(
        self,
        name: str,
        subject: str = "",
        emoji: str = "📐",
    ) -> Partition:
        """创建分区"""
        ...

    async def create_domain(
        self,
        partition_id: str,
        name: str,
        emoji: str = "📚",
    ) -> TreeNode:
        """在分区下创建领域"""
        ...

    async def create_topic(
        self,
        domain_id: str,
        name: str,
        emoji: str = "📝",
    ) -> TreeNode:
        """在领域下创建专题"""
        ...

    async def create_conversation(
        self,
        topic_id: str,
        name: str = "",
    ) -> TreeNode:
        """在专题下创建对话"""
        ...

    async def get_partitions(
        self,
        user_id: str = DEFAULT_USER_ID,
    ) -> list[Partition]:
        """获取用户所有分区（含内嵌 tree）"""
        ...

    async def get_tree(
        self,
        partition_id: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> Partition:
        """获取分区完整树结构"""
        ...

    async def persist_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        source: str = "user",
        metadata: dict | None = None,
    ) -> TreeNode:
        """持久化消息到对话"""
        ...

    async def rename_partition(
        self,
        partition_id: str,
        name: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> dict:
        """重命名分区"""
        ...

    async def delete_partition(
        self,
        partition_id: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> dict:
        """删除分区"""
        ...

    async def search_partitions(
        self,
        query: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> list[Partition]:
        """搜索分区"""
        ...
