"""
SSE 流式对话端点 — 替代 WebSocket

端点列表：
  GET  /stream/{cid}           — SSE 订阅（回放缓存 + 实时流）
  POST /stream/{cid}/pause     — 暂停
  POST /stream/{cid}/resume    — 恢复
  POST /stream/{cid}/stop      — 停止
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore

from app.domain.auth.dependencies import current_user_id
from app.services.conversation.token_buffer import token_buffer

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stream/{cid}")
async def stream_conversation(cid: str, request: Request, user_id: str = Depends(current_user_id)):
    """SSE 端点：订阅指定会话的流式事件。
    
    支持 SSE 原生断线重连（Last-Event-ID）：
    - 每条事件带 id: <seq> 字段
    - 重连时浏览器自动发送 Last-Event-ID 头
    - 服务端跳过已接收事件
    """
    last_event_id = 0
    try:
        last_event_id = int(request.headers.get("last-event-id", "0"))
    except (ValueError, TypeError):
        last_event_id = 0

    async def event_generator():
        try:
            event_counter = 0
            async for event in token_buffer.subscribe(cid, from_beginning=True):
                event_counter += 1
                if event_counter <= last_event_id:
                    continue  # 跳过客户端已接收的事件
                data = json.dumps(event, ensure_ascii=False, default=str)
                yield f"id: {event_counter}\ndata: {data}\n\n"

            # 流结束信号
            yield "data: {\"type\":\"stream_end\"}\n\n"
        except Exception as e:
            logger.error("SSE 生成器异常 [%s]: %s", cid[:8], e)
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stream/{cid}/pause")
async def pause_stream(cid: str, user_id: str = Depends(current_user_id)):
    """暂停指定会话的流"""
    ok = await token_buffer.pause(cid)
    if not ok:
        # 可能不存在或不在 RUNNING 状态
        state = await token_buffer.get_state(cid)
        return {"ok": False, "state": state, "message": "无法暂停，流可能已完成或不存在"}
    return {"ok": True, "state": "paused"}


@router.post("/stream/{cid}/resume")
async def resume_stream(cid: str, user_id: str = Depends(current_user_id)):
    """恢复指定会话的流"""
    ok = await token_buffer.resume(cid)
    if not ok:
        state = await token_buffer.get_state(cid)
        return {"ok": False, "state": state, "message": "无法恢复，流可能不在暂停状态"}
    return {"ok": True, "state": "running"}


@router.post("/stream/{cid}/stop")
async def stop_stream(cid: str, user_id: str = Depends(current_user_id)):
    """停止指定会话的流"""
    ok = await token_buffer.stop(cid)
    if not ok:
        return {"ok": False, "message": "流不存在或已结束"}
    return {"ok": True, "state": "cancelled"}
