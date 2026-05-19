"""
Conversation Service Protocol — 对话模块对外契约

其他模块只能通过此接口调用对话功能。
实现类: domain/conversation/service_impl.py
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.conversation import TreeNode, Branch, Partition, ResponseBlock


@runtime_checkable
class ConversationService(Protocol):
    """对话模块对外契约"""

    async def send_message(
        self,
        partition_id: str,
        branch_id: str,
        content: str,
        user_id: str = "default_user",
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

    async def create_branch(
        self,
        partition_id: str,
        name: str = "新分支",
    ) -> Branch:
        """创建分支"""
        ...

    async def get_messages(
        self,
        branch_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TreeNode]:
        """获取分支消息"""
        ...

    async def get_response_blocks(
        self,
        message_id: str,
    ) -> list[ResponseBlock]:
        """获取消息的响应块"""
        ...

    async def inject_context(
        self,
        branch_id: str,
        context: dict,
    ) -> None:
        """向对话分支注入上下文（练习结果、知识更新等）"""
        ...

    async def send_notification(
        self,
        user_id: str,
        message: str,
        context: dict | None = None,
    ) -> None:
        """向用户发送通知消息"""
        ...

    # Phase 5: 多媒体事件处理
    async def on_audio_synthesized(self, event) -> None:
        """音频合成完成 → 通过 WebSocket 推送 AudioBlock"""
        ...

    async def on_image_rendered(self, event) -> None:
        """配图渲染完成 → 通过 WebSocket 推送 ImageBlock"""
        ...

    async def push_response_block(
        self,
        user_id: str,
        message_id: str,
        block_type: str,
        content: dict,
    ) -> None:
        """推送 ResponseBlock 到前端 (WebSocket)"""
        ...
