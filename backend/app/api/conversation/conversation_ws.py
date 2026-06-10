"""
WebSocket 流式对话端点 + 事件发布辅助

从 conversation.py 拆分：仅 WebSocket 通道
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect  # type: ignore

from app.services.conversation.active_stream import active_streams

router = APIRouter()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# WebSocket 流式对话
# ═══════════════════════════════════════════


@router.websocket("/ws")
async def websocket_conversation(websocket: WebSocket) -> None:
    """WebSocket 流式对话端点，后台 generator 不依赖 WS 连接

    认证机制：
    - 请求经 auth-gateway（:18001）代理转发，由 gateway 完成 JWT 验证
    - user_id 由 gateway 注入到 query 参数，backend 信任内网来源，直接使用
    """
    # 从 query 参数获取 user_id（由 auth-gateway 注入）
    user_id = websocket.query_params.get("user_id", "")
    if not user_id:
        await websocket.close(code=4001)
        return
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "JSON解析失败"})
                )
                continue

            text = data.get("text", "").strip()
            partition_id = data.get("partition_id")
            conversation_id = data.get("conversation_id", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            pending_quote = data.get("pending_quote")  # 引用数据

            if not text:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "消息不能为空"})
                )
                continue

            # ═══════════════════════════════════════════
            # 情绪检测（后台异步，不影响主流程）
            # ═══════════════════════════════════════════
            try:
                from app.services.analytics.emotion_analyzer import emotion_analyzer
                quick_cat = emotion_analyzer.quick_detect(text)
                if quick_cat:
                    asyncio.ensure_future(emotion_analyzer.classify(text, user_id))
            except Exception:
                pass

            await websocket.send_text(
                json.dumps({"type": "status", "message": "正在思考...", "request_id": request_id})
            )

            from app.domain.conversation.llm import send_and_reply_stream

            # 后台 generator + 队列解耦（WS 断后 generator 继续跑，持续写 DB）
            stream_queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=200)

            async def _background_consume():
                """后台消费 generator，产出→队列，不依赖 WS"""
                await active_streams.mark_start(conversation_id)
                assistant_text = ""
                try:
                    async for event in send_and_reply_stream(
                        user_id, partition_id, text, conversation_id=conversation_id,
                        pending_quote=pending_quote,
                    ):
                        await stream_queue.put(event)
                        if event.get("type") == "token":
                            assistant_text += event.get("content", "")
                    await stream_queue.put(None)  # 哨兵：流结束
                except Exception as e:
                    logger.error("后台流异常: %s", str(e), exc_info=True)
                    await stream_queue.put({"type": "error", "message": str(e)})
                    await stream_queue.put(None)
                finally:
                    await active_streams.mark_done(conversation_id)
                    # 发布回复事件
                    if assistant_text.strip():
                        import re as _re
                        skill_ids = _re.findall(r"\[KNOWLEDGE:(\w+)\]", assistant_text)
                        contains_math = bool(_re.search(r"\$", assistant_text))
                        asyncio.ensure_future(_publish_reply_event(
                            user_id, partition_id, conversation_id,
                            assistant_text, skill_ids, contains_math,
                        ))

            asyncio.create_task(_background_consume())

            # 从队列读取并转发到 WS
            try:
                while True:
                    event = await asyncio.wait_for(stream_queue.get(), timeout=120)
                    if event is None:
                        break  # 流正常结束
                    event["request_id"] = request_id

                    if event.get("type") == "context_switch":
                        rec_pid = event.get("partition_id", "")
                        rec_cid = event.get("conversation_id", "")
                        if rec_pid:
                            partition_id = rec_pid
                        if rec_cid:
                            conversation_id = rec_cid
                        event["partition_id"] = partition_id

                    if "partition_id" not in event or not event["partition_id"]:
                        event["partition_id"] = partition_id

                    await websocket.send_text(
                        json.dumps(event, ensure_ascii=False, default=str)
                    )
            except (WebSocketDisconnect, asyncio.TimeoutError, ConnectionError):
                # WS 断开 → generator 仍在后台跑，持续写 DB
                logger.info(f"WS 断开 [{conversation_id[:8]}], 后台流继续")
                # 不取消 bg_task，让它自然完成
            except Exception as e:
                logger.error("消息处理失败: %s", str(e), exc_info=True)
                try:
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": str(e), "request_id": request_id})
                    )
                except Exception:
                    logger.debug("无法发送错误消息到 WebSocket（客户端可能已断开）")

    except WebSocketDisconnect:
        logger.info("对话WebSocket断开")


async def _publish_reply_event(
    user_id, partition_id, conversation_id, content, skill_ids, contains_math
):
    try:
        from app.application.di import container
        from shared.events import AssistantReplied

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
