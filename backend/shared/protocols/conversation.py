"""
Conversation Service Protocol — 对话模块对外契约

其他模块只能通过此接口调用对话功能。
实现: domain/conversation/session_bridge.py SessionBridge (on_session_completed)
"""

from __future__ import annotations

from typing import AsyncGenerator, Protocol, runtime_checkable

from app.schemas.conversation import TreeNode, Branch, Partition, ResponseBlock
from shared.constants import DEFAULT_USER_ID


@runtime_checkable
class ConversationService(Protocol):
    """对话模块对外契约"""

    # ── 核心回复管道 ──

    async def send_and_reply(
        self,
        user_id: str,
        partition_id: str,
        user_text: str,
        content_blocks: list | None = None,
        conversation_id: str = "",
        pending_quote: dict | None = None,
    ) -> dict:
        """完整流程：存用户消息 → 生成回复（含工具） → 存助手消息"""
        ...

    async def send_and_reply_stream(
        self,
        user_id: str,
        partition_id: str,
        user_text: str,
        content_blocks: list | None = None,
        conversation_id: str = "",
        pending_quote: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """完整流程（流式）：自动路由 → 存用户消息 → 预执行工具 → 流式生成回复 → 存助手消息"""
        ...

    async def send_message(
        self,
        user_id: str,
        content: str,
        partition_id: str | None = None,
        branch_id: str | None = None,
    ) -> dict:
        """发送消息 → LLM 回复（简化版）"""
        ...

    # ── 分区/领域/专题/对话 CRUD ──

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

    # ── 查询 ──

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

    # ── 消息持久化 ──

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

    # ── 分区管理 ──

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

    # ── WebSocket 推送 ──

    async def push_response_block(
        self,
        user_id: str,
        message_id: str,
        block_type: str,
        content: dict,
    ) -> None:
        """推送 ResponseBlock 到前端"""
        ...

    # ── 上下文注入 ──

    async def inject_practice_context(
        self,
        user_id: str,
        branch_id: str,
        context: dict,
    ) -> None:
        """注入练习上下文到对话系统"""
        ...
