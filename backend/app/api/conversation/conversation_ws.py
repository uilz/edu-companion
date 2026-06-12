"""
WebSocket 流式对话端点（统一入口）

process_message → ReplyEvent 流 → WS 发送。
与 conversation_routes.py 共用 conversation_processor。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect  # type: ignore

from app.domain.conversation.conversation_processor import process_message, _to_ws_dict

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_conversation(websocket: WebSocket) -> None:
    """WebSocket 流式对话端点

    认证：由 auth-gateway 注入 user_id 到 query 参数。
    """
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
            pending_quote = data.get("pending_quote")

            if not text:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "消息不能为空"})
                )
                continue

            await websocket.send_text(
                json.dumps({"type": "status", "message": "正在思考...", "request_id": request_id})
            )

            # 后台 generator + 队列解耦（WS 断后 pipeline 继续跑）
            stream_queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=200)

            async def _background_consume():
                try:
                    async for event in process_message(
                        user_id, text, partition_id,
                        conversation_id=conversation_id,
                        pending_quote=pending_quote,
                    ):
                        ws_event = _to_ws_dict(event, request_id)
                        await stream_queue.put(ws_event)
                    await stream_queue.put(None)
                except Exception as e:
                    logger.error("后台流异常: %s", str(e), exc_info=True)
                    await stream_queue.put({"type": "error", "message": str(e), "request_id": request_id})
                    await stream_queue.put(None)

            asyncio.create_task(_background_consume())

            try:
                while True:
                    event = await asyncio.wait_for(stream_queue.get(), timeout=120)
                    if event is None:
                        break
                    event["request_id"] = request_id

                    if event.get("type") == "context_switch":
                        new_pid = event.get("partition_id", "")
                        new_cid = event.get("conversation_id", "")
                        if new_pid:
                            partition_id = new_pid
                        if new_cid:
                            conversation_id = new_cid
                        event["partition_id"] = partition_id

                    if event.get("type") == "conversation_created":
                        new_cid = event.get("data", {}).get("conversation_id", "")
                        if new_cid:
                            conversation_id = new_cid

                    if "partition_id" not in event or not event["partition_id"]:
                        event["partition_id"] = partition_id

                    await websocket.send_text(
                        json.dumps(event, ensure_ascii=False, default=str)
                    )
            except (WebSocketDisconnect, asyncio.TimeoutError, ConnectionError):
                logger.info("WS 断开 [%s], 后台流继续", conversation_id[:8] if conversation_id else "?")
            except Exception as e:
                logger.error("消息处理失败: %s", str(e), exc_info=True)
                try:
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": str(e), "request_id": request_id})
                    )
                except Exception:
                    pass

    except WebSocketDisconnect:
        logger.info("对话WebSocket断开")
