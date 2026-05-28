"""
WebSocket 聊天端点
处理实时聊天、流式响应

修复：
- WebSocket 路径改为 /ws（匹配前端）
- 接受前端简化消息格式 { conversationId, message, settings }
- HTTP POST 接受 JSON body
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.learner_model import learner_engine
from shared.constants import DEFAULT_USER_ID
from app.core.orchestrator import orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._sessions: dict[str, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        await websocket.accept()
        session_id = str(uuid.uuid4())
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        self._sessions[session_id] = user_id
        logger.info("WebSocket连接建立: user=%s session=%s", user_id, session_id)
        return session_id

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def send_json(self, user_id: str, data: dict) -> None:
        connections = self._connections.get(user_id, [])
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)


manager = ConnectionManager()


async def _send(websocket: WebSocket, msg_type: str, payload: dict, request_id: str = "") -> None:
    """发送标准化消息"""
    data = {
        "type": msg_type,
        "payload": payload,
        "request_id": request_id,
    }
    await websocket.send_text(json.dumps(data, ensure_ascii=False))


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    WebSocket 聊天端点

    前端连接: ws://host:3000/ws (通过 Next.js 代理到后端 :8000/ws)

    前端发送格式:
        {"conversationId": "xxx", "message": "你好", "settings": {...}}

    后端返回格式:
        {"type": "stream", "payload": {"content": "你"}, "request_id": "xxx"}
        {"type": "done", "payload": {}, "request_id": "xxx"}
        {"type": "error", "payload": {"message": "出错了"}, "request_id": "xxx"}
    """
    # 使用默认 user_id（MVP 单用户模式）
    user_id = DEFAULT_USER_ID
    session_id = await manager.connect(websocket, user_id)

    try:
        while True:
            raw_data = await websocket.receive_text()
            logger.info("收到消息: %s", raw_data[:200])

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                await _send(websocket, "error", {"message": f"JSON解析失败: {e}"})
                continue

            # 兼容前端格式：{ conversationId, message, settings }
            data.get("conversationId", "")
            user_message = data.get("message", "")
            data.get("settings", {})
            request_id = data.get("request_id", str(uuid.uuid4())[:8])

            if not user_message or not user_message.strip():
                await _send(websocket, "error", {"message": "消息内容不能为空"}, request_id)
                continue

            # 发送"正在思考"状态
            await _send(websocket, "status", {"message": "正在思考..."}, request_id)

            try:
                # 流式处理消息
                async for chunk in orchestrator.process_message_stream(
                    user_id=user_id,
                    user_message=user_message,
                    session_id=session_id,
                    subject=None,
                ):
                    await _send(websocket, "stream", {"content": chunk}, request_id)

                # 发送完成标记
                await _send(websocket, "done", {
                    "session_id": session_id,
                }, request_id)

            except Exception as e:
                logger.error("消息处理失败: %s", str(e), exc_info=True)
                await _send(websocket, "error", {
                    "message": f"处理出错: {str(e)}"
                }, request_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info("用户断开连接")
    except Exception as e:
        logger.error("WebSocket异常: %s", str(e), exc_info=True)
        manager.disconnect(websocket, user_id)


# ── HTTP 备用接口 ──

class ChatRequestBody(BaseModel):
    """HTTP聊天请求体"""
    conversationId: str = ""
    message: str
    subject: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/chat")
async def http_chat(body: ChatRequestBody) -> dict[str, Any]:
    """
    HTTP 方式的聊天接口（备用，非流式）
    """
    user_id = DEFAULT_USER_ID
    session_id = learner_engine.create_session(user_id, body.subject)

    result = await orchestrator.process_message(
        user_id=user_id,
        user_message=body.message,
        session_id=session_id,
        subject=body.subject,
    )

    result["session_id"] = session_id
    return result
