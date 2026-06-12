"""
对话系统 LLM 服务（Façade）

本模块是薄封装层，实际编排逻辑统一在 ReplyPipeline 中。
公开 API 保持兼容：send_and_reply / send_and_reply_stream。
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from app.schemas.conversation import ContentBlock

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 公开 API：send_and_reply（非流式完整流程）
# ═══════════════════════════════════════════════

async def send_and_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
    conversation_id: str = "",
    pending_quote: dict | None = None,
) -> dict:
    """
    完整流程（非流式）：收集 ReplyPipeline 的全部事件 → 返回结果字典。
    """
    from .reply_pipeline import ReplyPipeline

    pipeline = ReplyPipeline()
    user_message = None
    assistant_message = None
    response_blocks = []

    async for event in pipeline.invoke(
        user_id, partition_id, user_text,
        content_blocks=content_blocks,
        conversation_id=conversation_id,
        pending_quote=pending_quote,
    ):
        if event.type == "user_message":
            user_message = event.message
        elif event.type == "done":
            assistant_message = event.data.get("assistant_message")
            response_blocks = event.data.get("response_blocks", [])
        elif event.type == "error":
            return {"ok": False, "error": event.data.get("error", "unknown")}

    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
        "partition_id": partition_id,
        "response_blocks": response_blocks,
    }


# ═══════════════════════════════════════════════
# 公开 API：send_and_reply_stream（流式完整流程）
# ═══════════════════════════════════════════════

async def send_and_reply_stream(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
    conversation_id: str = "",
    pending_quote: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """
    完整流程（流式）：转发 ReplyPipeline 事件为 dict。
    """
    from .reply_pipeline import ReplyPipeline

    pipeline = ReplyPipeline()
    async for event in pipeline.invoke(
        user_id, partition_id, user_text,
        content_blocks=content_blocks,
        conversation_id=conversation_id,
        pending_quote=pending_quote,
    ):
        # 将 ReplyEvent 转为 dict（兼容现有调用方）
        result = {"type": event.type}

        if event.type == "context_switch":
            result.update(event.data)
        elif event.type == "user_message":
            result["message"] = event.message
        elif event.type == "tool_block":
            result["block"] = event.block
        elif event.type == "token":
            result["content"] = event.content
        elif event.type == "done":
            result["assistant_message"] = event.data.get("assistant_message")
            result["response_blocks"] = event.data.get("response_blocks", [])
        elif event.type == "error":
            result["error"] = event.data.get("error", "unknown")

        yield result
