"""
ConversationProcessor — 统一消息处理管线

WS 和 HTTP 共用同一个异步生成器，产出 ReplyEvent 流。
   - WS：边收边发
   - HTTP：收集完成后返回 JSON

原始 Engine 的逻辑（情绪检测、active_streams、回复事件发布）已内联至此。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncGenerator

from app.domain.conversation.reply_pipeline import ReplyPipeline, ReplyEvent
from app.services.conversation.active_stream import active_streams
from app.services.analytics.emotion_analyzer import emotion_analyzer

logger = logging.getLogger(__name__)

AGENT_LABEL = "tutor"


async def process_message(
    user_id: str,
    text: str,
    partition_id: str,
    conversation_id: str = "",
    pending_quote: dict | None = None,
) -> AsyncGenerator[ReplyEvent, None]:
    """统一消息处理入口：情绪检测 → Pipeline → active_stream 管理。

    WS / HTTP 调用方：
        async for event in process_message(user_id, text, pid, cid=conv_id):
            ...
    """
    # ── 情绪检测（fire-and-forget） ──
    try:
        quick_cat = emotion_analyzer.quick_detect(text)
        if quick_cat:
            asyncio.ensure_future(emotion_analyzer.classify(text, user_id))
    except Exception:
        pass

    pipeline = ReplyPipeline(agent_label=AGENT_LABEL)

    await active_streams.mark_start(conversation_id)
    assistant_text = ""

    try:
        async for event in pipeline.invoke(
            user_id, partition_id, text,
            conversation_id=conversation_id,
            pending_quote=pending_quote,
        ):
            yield event
            if event.type == "token":
                assistant_text += event.content or ""
    except Exception as e:
        logger.error("process_message 异常: %s", str(e), exc_info=True)
        yield ReplyEvent(type="error", data={"error": str(e)})
    finally:
        await active_streams.mark_done(conversation_id)
        # fire-and-forget 发布回复事件
        if assistant_text.strip():
            asyncio.ensure_future(_publish_reply_event(
                user_id, partition_id, conversation_id, assistant_text,
            ))


def _to_ws_dict(event: ReplyEvent, request_id: str) -> dict:
    """ReplyEvent → WS 消息 dict（无 agent_label）"""
    ws: dict = {"type": event.type, "request_id": request_id}
    if event.content:
        ws["content"] = event.content
    if event.block:
        ws["block"] = event.block
    if event.message:
        ws["message"] = event.message
    if event.switch_detail:
        ws["switch_detail"] = event.switch_detail
    if event.data:
        ws.update({k: v for k, v in event.data.items() if k not in ws})
    if event.type == "done":
        ws["done"] = True
    return ws


async def _publish_reply_event(
    user_id: str,
    partition_id: str,
    conversation_id: str,
    content: str,
) -> None:
    """发布 AssistantReplied 领域事件（fire-and-forget）"""
    try:
        from app.application.di import container
        from shared.events import AssistantReplied

        skill_ids = re.findall(r"\[KNOWLEDGE:(\w+)\]", content)
        contains_math = bool(re.search(r"\$", content))

        await container.event_bus.publish(
            AssistantReplied(
                user_id=user_id,
                partition_id=partition_id,
                conversation_id=conversation_id,
                content=content,
                skill_ids=skill_ids,
                contains_math=contains_math,
            )
        )
    except Exception:
        logger.debug("事件发布失败（fire-and-forget）", exc_info=True)
