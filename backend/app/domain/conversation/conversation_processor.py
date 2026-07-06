"""
ConversationProcessor — 统一消息处理管线

核心流程：
  1. POST /{conv_id}/message { action: "send" } → start_background_pipeline()
  2. pipeline 产出 ReplyEvent → _publish_event_to_buffer() 写入 StreamBuffer
  3. 同一请求的 StreamingResponse 从 StreamBuffer.stream() 回放+实时推送
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from app.domain.conversation.reply_pipeline import ReplyPipeline, ReplyEvent
from app.domain.conversation.pipeline_stages import ToolResult, PipelineCtx, _pop_suspended, _has_suspended
from app.services.conversation.stream_buffer import stream_buffer
from app.services.analytics.emotion_analyzer import emotion_analyzer
from app.services.conversation.active_stream import active_streams

logger = logging.getLogger(__name__)

AGENT_LABEL = "tutor"


async def process_message(
    user_id: str,
    text: str,
    dir_id: str,
    conv_id: str = "",
    parent_id: str = "",
    pending_quote: dict | None = None,
) -> AsyncGenerator[ReplyEvent, None]:
    """统一消息处理入口 — 保留兼容性，同时发布到 StreamBuffer。

    此函数同时：
      1. yield 事件供旧式 HTTP 消费者收集（阻塞式）
      2. publish 事件到 StreamBuffer 供 SSE 消费者实时读取
    """
    try:
        quick_cat = emotion_analyzer.quick_detect(text)
        if quick_cat:
            asyncio.ensure_future(emotion_analyzer.classify(text, user_id))
    except Exception:
        pass

    pipeline = ReplyPipeline(agent_label=AGENT_LABEL)

    await active_streams.mark_start(conv_id)
    assistant_text = ""
    assistant_message_id = ""
    current_msg_id = ""

    try:
        async for event in pipeline.invoke(
            user_id, dir_id, text,
            conv_id=conv_id,
            parent_id=parent_id,
            pending_quote=pending_quote,
        ):
            yield event
            assistant_text += event.content or ""
            if event.type == "done":
                assistant_message_id = event.data.get("assistant_message", {}).get("id", "")
            if event.type == "pending_msg" and event.data:
                current_msg_id = event.data.get("msg_id", "")
            await _publish_event_to_buffer(conv_id, event, msg_id=current_msg_id)
    except Exception as e:
        logger.error("process_message 异常: %s", str(e), exc_info=True)
        err_event = ReplyEvent(type="error", data={"error": str(e)})
        yield err_event
        await _publish_event_to_buffer(conv_id, err_event)
    finally:
        await active_streams.mark_done(conv_id)
        await stream_buffer.mark_done(conv_id)
        if assistant_text.strip():
            asyncio.ensure_future(_publish_reply_event(
                user_id, dir_id, conv_id, assistant_text,
                user_text=text, assistant_message_id=assistant_message_id,
            ))


async def start_background_pipeline(
    user_id: str,
    text: str,
    dir_id: str,
    conv_id: str,
    parent_id: str = "",
    pending_quote: dict | None = None,
    knowledge_node_id: str | None = None,
    tool_result: ToolResult | None = None,
) -> None:
    """启动后台 pipeline，事件自动流入 StreamBuffer。

    调用方直接管理 StreamingResponse，同一请求内从 StreamBuffer.stream() 读取事件。
    """
    # 清理上一次对话的缓冲区，避免旧事件回放导致消息重复
    await stream_buffer.cleanup(conv_id)

    # ── stale streaming 检测：清理残留的 streaming 消息 ──
    try:
        _cleanup_stale_streaming(user_id, conv_id)
    except Exception:
        logger.debug("stale streaming 清理失败（非关键）", exc_info=True)

    # 预创建缓冲区，确保 streaming 时 entry 已存在
    await stream_buffer.publish(conv_id, {"type": "stream_start"})
    await active_streams.mark_start(conv_id)

    task = asyncio.create_task(_run_pipeline_task(
        user_id, text, dir_id, conv_id, parent_id, pending_quote, knowledge_node_id, tool_result,
    ))
    await stream_buffer.set_task(conv_id, task)


async def resume_background_pipeline(
    conv_id: str,
    tool_result: ToolResult,
) -> bool:
    """恢复挂起的管线：将用户答案注入 tool result，继续 while 循环。

    返回 True 表示成功恢复，False 表示无挂起管线。
    """
    state = _pop_suspended(conv_id)
    if state is None:
        logger.warning("resume_background_pipeline: no suspended pipeline for %s", conv_id[:8])
        return False

    # 将用户答案作为 tool result 注入 llm_messages
    state.llm_messages.append({
        "role": "tool",
        "tool_call_id": tool_result.tool_call_id,
        "content": f"用户回答了之前提出的问题：\n{tool_result.answers}",
    })

    # 持久化用户答案到 question 工具块的 result_content.user_answer。
    # 这样 PostProcessStage 持久化时，user_answer 会跟随 stream_content_blocks
    # 一起写入 MessageNode.content_blocks，刷新页面后 QuestionBlock 仍能识别已作答状态。
    _persist_user_answer_to_question_block(
        state.ctx.stream_content_blocks,
        tool_result.tool_call_id,
        tool_result.answers,
    )

    logger.info("Resuming suspended pipeline, conv=%s, round=%d", conv_id[:8], state._round)

    # 创建恢复用的 ctx（拷贝原始 ctx 的产出字段）
    saved_ctx = state.ctx
    ctx = PipelineCtx(
        user_id=saved_ctx.user_id,
        dir_id=saved_ctx.dir_id,
        user_text=saved_ctx.user_text,
        conv_id=saved_ctx.conv_id,
        agent_label=saved_ctx.agent_label,
        pending_quote=saved_ctx.pending_quote,
        knowledge_node_id=saved_ctx.knowledge_node_id,
    )
    ctx.response_blocks = saved_ctx.response_blocks
    ctx.stream_content_blocks = saved_ctx.stream_content_blocks
    ctx.full_reply = saved_ctx.full_reply
    ctx.conversation = saved_ctx.conversation
    ctx.user_msg_id = saved_ctx.user_msg_id
    ctx.parent_id = saved_ctx.parent_id

    resume_state = {
        "llm_messages": state.llm_messages,
        "tools": state.tools,
        "_round": state._round,
    }

    pipeline = ReplyPipeline(agent_label=AGENT_LABEL)
    assistant_text = ""
    current_msg_id = ""

    try:
        async for event in pipeline.invoke(
            ctx.user_id, ctx.dir_id, ctx.user_text,
            conv_id=ctx.conv_id,
            resume_state=resume_state,
        ):
            assistant_text += event.content or ""
            if event.type == "pending_msg" and event.data:
                current_msg_id = event.data.get("msg_id", "")
            await _publish_event_to_buffer(conv_id, event, msg_id=current_msg_id)
    except Exception as e:
        logger.error("Resume pipeline 异常 [%s]: %s", conv_id[:8], e, exc_info=True)
        await _publish_event_to_buffer(conv_id, ReplyEvent(
            type="error", data={"error": str(e)},
        ))
    finally:
        await stream_buffer.mark_done(conv_id)
        await active_streams.mark_done(conv_id)
        if assistant_text.strip():
            asyncio.ensure_future(_publish_reply_event(
                ctx.user_id, ctx.dir_id, ctx.conv_id, assistant_text,
                user_text=ctx.user_text,
            ))

    return True


async def _run_pipeline_task(
    user_id: str,
    text: str,
    dir_id: str,
    conv_id: str,
    parent_id: str = "",
    pending_quote: dict | None = None,
    knowledge_node_id: str | None = None,
    tool_result: ToolResult | None = None,
) -> None:
    """后台 pipeline 任务 — 所有事件发布到 StreamBuffer"""
    try:
        quick_cat = emotion_analyzer.quick_detect(text)
        if quick_cat:
            asyncio.ensure_future(emotion_analyzer.classify(text, user_id))
    except Exception:
        pass

    pipeline = ReplyPipeline(agent_label=AGENT_LABEL)
    assistant_text = ""
    assistant_message_id = ""
    suspended = False
    current_msg_id = ""

    me = asyncio.current_task()

    try:
        async for event in pipeline.invoke(
            user_id, dir_id, text,
            conv_id=conv_id,
            parent_id=parent_id,
            pending_quote=pending_quote,
            knowledge_node_id=knowledge_node_id,
            tool_result=tool_result,
        ):
            assistant_text += event.content or ""
            if event.type == "done":
                assistant_message_id = event.data.get("assistant_message", {}).get("id", "")
            elif event.type == "pipeline_suspended":
                suspended = True
            if event.type == "pending_msg" and event.data:
                current_msg_id = event.data.get("msg_id", "")

            await _publish_event_to_buffer(conv_id, event, msg_id=current_msg_id)

    except Exception as e:
        logger.error("后台 pipeline 异常 [%s]: %s", conv_id[:8], e, exc_info=True)
        err_event = ReplyEvent(type="error", data={"error": str(e)})
        await _publish_event_to_buffer(conv_id, err_event)
    finally:
        if not suspended:
            await stream_buffer.mark_done(conv_id)
        await active_streams.mark_done(conv_id)
        if assistant_text.strip():
            asyncio.ensure_future(_publish_reply_event(
                user_id, dir_id, conv_id, assistant_text,
                user_text=text, assistant_message_id=assistant_message_id,
            ))


async def _publish_event_to_buffer(conv_id: str, event: ReplyEvent, msg_id: str = "") -> None:
    """将 ReplyEvent 转为 dict 并发布到 StreamBuffer"""
    if not conv_id:
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
        for k, v in event.data.items():
            if k not in d:
                d[k] = v
    if event.type == "done":
        d["done"] = True
    await stream_buffer.publish(conv_id, d, msg_id=msg_id)


async def _publish_reply_event(
    user_id: str,
    dir_id: str,
    conv_id: str,
    content: str,
    user_text: str = "",
    assistant_message_id: str = "",
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
                dir_id=dir_id,
                conv_id=conv_id,
                content=content,
                user_text=user_text,
                assistant_message_id=assistant_message_id,
                skill_ids=skill_ids,
                contains_math=contains_math,
            )
        )
    except Exception:
        logger.debug("事件发布失败（fire-and-forget）", exc_info=True)


def _persist_user_answer_to_question_block(
    stream_blocks: list[dict],
    tool_call_id: str,
    answers: str,
) -> None:
    """将用户答案写入到对应的 question 工具块 result_content.user_answer 字段。

    stream_blocks 形态：每个块是 dict，type="tool" 的块含 result_block_type/result_content。
    ask_question 工具的 result_block_type="question"，result_content 含 type/questions/question/options/tool_call_id。

    写入后，PostProcessStage 持久化 MessageNode.content_blocks 时，user_answer 会一并保存，
    刷新页面后 QuestionBlock 组件读 result_content.user_answer 即可识别已作答状态。
    """
    if not stream_blocks or not tool_call_id:
        return
    for block in stream_blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool":
            continue
        # 优先匹配 tool_call_id 字段（_append_tool_to_stream 写入的）
        if block.get("tool_call_id") and block["tool_call_id"] != tool_call_id:
            continue
        if block.get("result_block_type") != "question":
            continue
        result_content = block.get("result_content")
        if not isinstance(result_content, dict):
            continue
        # 二次校验：result_content.tool_call_id 才是 LLM 给的 tc["id"]
        if result_content.get("tool_call_id") and result_content["tool_call_id"] != tool_call_id:
            continue
        result_content["user_answer"] = answers
        result_content["answered_at"] = __import__("time").time()
        logger.info(
            "user_answer 持久化到 question 块: tool_call_id=%s, len=%d",
            tool_call_id[:8], len(answers),
        )
        return
    logger.warning(
        "未找到匹配的 question 工具块: tool_call_id=%s, stream_blocks 数=%d",
        tool_call_id[:8], len(stream_blocks),
    )


def _cleanup_stale_streaming(user_id: str, conv_id: str) -> None:
    """清理残留的 streaming 消息（因崩溃/断连而遗留的 shell 消息）。

    规则：
      - 查找 conv.conv_message_ids 中 status=streaming 的消息
      - 标记为 orphaned 并从 conv.conv_message_ids 移除
      - 同时从 data.nodes 中软删除
    """
    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    conv_node = data.directory_nodes.get(conv_id)
    if not conv_node:
        return

    cleaned = []
    for mid in conv_node.conv_message_ids:
        node = data.nodes.get(mid)
        if node and getattr(node, "status", None) == "streaming":
            node.status = "orphaned"
            node.is_deleted = True
            logger.info("清理 stale streaming 消息: %s (conv=%s)", mid[:8], conv_id[:8])
        else:
            cleaned.append(mid)

    if len(cleaned) != len(conv_node.conv_message_ids):
        conv_node.conv_message_ids = cleaned
        get_data_repo().save(user_id, data)
