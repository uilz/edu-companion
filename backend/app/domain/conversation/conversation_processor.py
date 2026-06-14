"""
ConversationProcessor — 统一消息处理管线

通过 HTTP POST 触发，pipeline 事件自动发布到 TokenBuffer。
前端通过 SSE 订阅 TokenBuffer 实时接收流式事件。

核心流程：
  1. POST /tree/conversation/{cid}/message  →  start_background_pipeline()
  2. pipeline 产出 ReplyEvent，由 _publish_to_buffer() 实时写入 TokenBuffer
  3. GET /stream/{cid} (SSE) → TokenBuffer.subscribe() 回放+实时推送
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from app.domain.conversation.reply_pipeline import ReplyPipeline, ReplyEvent
from app.services.conversation.token_buffer import token_buffer
from app.services.analytics.emotion_analyzer import emotion_analyzer
from app.services.conversation.active_stream import active_streams

logger = logging.getLogger(__name__)

AGENT_LABEL = "tutor"


async def process_message(
    user_id: str,
    text: str,
    partition_id: str,
    conversation_id: str = "",
    pending_quote: dict | None = None,
) -> AsyncGenerator[ReplyEvent, None]:
    """统一消息处理入口 — 保留兼容性，同时发布到 TokenBuffer。

    此函数同时：
      1. yield 事件供旧式 HTTP 消费者收集（阻塞式）
      2. publish 事件到 TokenBuffer 供 SSE 消费者实时读取

    新的 SSE 流程应直接使用 start_background_pipeline()。
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
            # yield 给旧式消费者
            yield event
            assistant_text += event.content or ""

            # 发布到 TokenBuffer
            await _publish_event_to_buffer(conversation_id, event)
    except Exception as e:
        logger.error("process_message 异常: %s", str(e), exc_info=True)
        err_event = ReplyEvent(type="error", data={"error": str(e)})
        yield err_event
        await _publish_event_to_buffer(conversation_id, err_event)
    finally:
        await active_streams.mark_done(conversation_id)
        await token_buffer.mark_done(conversation_id)
        # fire-and-forget 发布回复事件
        if assistant_text.strip():
            asyncio.ensure_future(_publish_reply_event(
                user_id, partition_id, conversation_id, assistant_text,
            ))


async def start_background_pipeline(
    user_id: str,
    text: str,
    partition_id: str,
    conversation_id: str,
    pending_quote: dict | None = None,
) -> None:
    """在后台启动 pipeline，事件自动流入 TokenBuffer。

    调用方（HTTP endpoint）无需 await 此函数，直接返回即可。
    SSE 客户端通过 /stream/{cid} 实时接收事件。
    """
    # 预创建缓冲区，确保 SSE 连接时 entry 已存在
    from app.services.conversation.token_buffer import token_buffer
    await token_buffer.publish(conversation_id, {"type": "stream_start"})

    asyncio.create_task(_run_pipeline_task(
        user_id, text, partition_id, conversation_id, pending_quote,
    ))


async def _run_pipeline_task(
    user_id: str,
    text: str,
    partition_id: str,
    conversation_id: str,
    pending_quote: dict | None = None,
) -> None:
    """后台 pipeline 任务 — 所有事件发布到 TokenBuffer"""
    # ── 情绪检测（fire-and-forget） ──
    try:
        quick_cat = emotion_analyzer.quick_detect(text)
        if quick_cat:
            asyncio.ensure_future(emotion_analyzer.classify(text, user_id))
    except Exception:
        pass

    pipeline = ReplyPipeline(agent_label=AGENT_LABEL)
    assistant_text = ""

    try:
        async for event in pipeline.invoke(
            user_id, partition_id, text,
            conversation_id=conversation_id,
            pending_quote=pending_quote,
        ):
            assistant_text += event.content or ""

            # 检查是否被取消
            if await token_buffer.check_cancelled(conversation_id):
                logger.info("Pipeline cancelled [%s]", conversation_id[:8])
                break

            # 如果暂停，等待恢复（pipeline 继续运行，但等待 resume 信号）
            while await token_buffer.check_paused(conversation_id):
                await token_buffer.wait_resume(conversation_id)
                # 恢复后检查是否被取消
                if await token_buffer.check_cancelled(conversation_id):
                    break

            # 发布事件到 TokenBuffer
            await _publish_event_to_buffer(conversation_id, event)

    except Exception as e:
        logger.error("后台 pipeline 异常 [%s]: %s", conversation_id[:8], e, exc_info=True)
        err_event = ReplyEvent(type="error", data={"error": str(e)})
        await _publish_event_to_buffer(conversation_id, err_event)
    finally:
        await token_buffer.mark_done(conversation_id)
        # fire-and-forget 发布回复事件
        if assistant_text.strip():
            asyncio.ensure_future(_publish_reply_event(
                user_id, partition_id, conversation_id, assistant_text,
            ))


async def _publish_event_to_buffer(conversation_id: str, event: ReplyEvent) -> None:
    """将 ReplyEvent 转为 dict 并发布到 TokenBuffer"""
    if not conversation_id:
        return
    d: dict = {"type": event.type}
    if event.content:
        d["content"] = event.content
    if event.block:
        d["block"] = event.block
    if event.message:
        d["message"] = event.message
    if event.switch_detail:
        d["switch_detail"] = event.switch_detail
    if event.data:
        # 合并 data 字段，避免覆盖上层字段
        for k, v in event.data.items():
            if k not in d:
                d[k] = v
    if event.type == "done":
        d["done"] = True
    await token_buffer.publish(conversation_id, d)


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

        import re
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
