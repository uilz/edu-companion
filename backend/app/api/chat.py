"""
WebSocket 聊天端点
处理实时聊天、语音消息、流式响应
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.learner_model import learner_engine
from app.core.orchestrator import orchestrator
from app.schemas.chat import (
    StreamChunk,
    WSIncomingMessage,
    WSMessageType,
    WSOutgoingMessage,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self) -> None:
        # user_id -> list[WebSocket]
        self._connections: dict[str, list[WebSocket]] = {}
        # session_id -> user_id
        self._sessions: dict[str, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """
        接受新的WebSocket连接

        返回: session_id
        """
        await websocket.accept()
        session_id = str(uuid.uuid4())

        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        self._sessions[session_id] = user_id

        logger.info("WebSocket连接建立: user=%s session=%s", user_id, session_id)
        return session_id

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """断开连接"""
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info("WebSocket连接断开: user=%s", user_id)

    async def send_to_user(self, user_id: str, message: WSOutgoingMessage) -> None:
        """向指定用户发送消息"""
        connections = self._connections.get(user_id, [])
        dead_connections: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(message.model_dump_json())
            except Exception:
                dead_connections.append(ws)
        # 清理断开的连接
        for ws in dead_connections:
            self.disconnect(ws, user_id)

    async def broadcast(self, message: WSOutgoingMessage) -> None:
        """向所有连接广播消息"""
        for user_id in list(self._connections.keys()):
            await self.send_to_user(user_id, message)


# 全局连接管理器
manager = ConnectionManager()


@router.websocket("/ws/chat/{user_id}")
async def websocket_chat(
    websocket: WebSocket,
    user_id: str,
) -> None:
    """
    WebSocket 聊天端点

    连接地址: ws://host:port/ws/chat/{user_id}

    消息协议：
    客户端发送:
        {"type": "chat", "payload": {"message": "你好", "subject": "数学"}, "request_id": "xxx"}
        {"type": "voice", "payload": {"audio_base64": "..."}, "request_id": "xxx"}
        {"type": "ping"}

    服务端发送:
        {"type": "status", "payload": {"message": "正在分析..."}, "request_id": "xxx"}
        {"type": "stream", "payload": {"content": "你"}, "request_id": "xxx"}
        {"type": "stream", "payload": {"content": "好"}, "request_id": "xxx"}
        {"type": "done", "payload": {"agent": "tutor", "intent": "question"}, "request_id": "xxx"}
        {"type": "error", "payload": {"message": "出错了"}, "request_id": "xxx"}
    """
    session_id = await manager.connect(websocket, user_id)

    try:
        while True:
            # 接收消息
            raw_data = await websocket.receive_text()

            try:
                msg = WSIncomingMessage.model_validate_json(raw_data)
            except Exception as e:
                logger.warning("消息解析失败: %s", str(e))
                await websocket.send_text(
                    WSOutgoingMessage(
                        type=WSMessageType.ERROR,
                        payload={"message": f"消息格式错误: {str(e)}"},
                    ).model_dump_json()
                )
                continue

            request_id = msg.request_id or str(uuid.uuid4())

            # 处理心跳
            if msg.type == WSMessageType.PING:
                await websocket.send_text(
                    WSOutgoingMessage(
                        type=WSMessageType.PONG,
                        request_id=request_id,
                    ).model_dump_json()
                )
                continue

            # 处理聊天消息
            if msg.type == WSMessageType.CHAT:
                user_message = msg.payload.get("message", "")
                subject = msg.payload.get("subject")

                if not user_message.strip():
                    await websocket.send_text(
                        WSOutgoingMessage(
                            type=WSMessageType.ERROR,
                            payload={"message": "消息内容不能为空"},
                            request_id=request_id,
                        ).model_dump_json()
                    )
                    continue

                # 发送"正在处理"状态
                await websocket.send_text(
                    WSOutgoingMessage(
                        type=WSMessageType.STATUS,
                        payload={"message": "正在分析你的问题..."},
                        request_id=request_id,
                    ).model_dump_json()
                )

                try:
                    # 流式处理消息
                    async for chunk in orchestrator.process_message_stream(
                        user_id=user_id,
                        user_message=user_message,
                        session_id=session_id,
                        subject=subject,
                    ):
                        await websocket.send_text(
                            WSOutgoingMessage(
                                type=WSMessageType.STREAM,
                                payload={"content": chunk},
                                request_id=request_id,
                            ).model_dump_json()
                        )

                    # 发送完成标记
                    await websocket.send_text(
                        WSOutgoingMessage(
                            type=WSMessageType.DONE,
                            payload={
                                "session_id": session_id,
                                "timestamp": datetime.now().isoformat(),
                            },
                            request_id=request_id,
                        ).model_dump_json()
                    )
                except Exception as e:
                    logger.error("消息处理失败: %s", str(e), exc_info=True)
                    await websocket.send_text(
                        WSOutgoingMessage(
                            type=WSMessageType.ERROR,
                            payload={"message": f"处理出错，请重试: {str(e)}"},
                            request_id=request_id,
                        ).model_dump_json()
                    )

            # 处理语音消息
            elif msg.type == WSMessageType.VOICE:
                audio_base64 = msg.payload.get("audio_base64", "")
                if not audio_base64:
                    await websocket.send_text(
                        WSOutgoingMessage(
                            type=WSMessageType.ERROR,
                            payload={"message": "语音数据为空"},
                            request_id=request_id,
                        ).model_dump_json()
                    )
                    continue

                # MVP: 语音转文字功能占位
                # 后续可集成 Whisper 或其他语音识别模型
                await websocket.send_text(
                    WSOutgoingMessage(
                        type=WSMessageType.STATUS,
                        payload={"message": "语音识别功能开发中，目前请使用文字消息"},
                        request_id=request_id,
                    ).model_dump_json()
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info("用户 %s 主动断开连接", user_id)
    except Exception as e:
        logger.error("WebSocket异常: %s", str(e), exc_info=True)
        manager.disconnect(websocket, user_id)


@router.post("/api/chat")
async def http_chat(
    user_id: str,
    message: str,
    subject: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    HTTP 方式的聊天接口（备用，非流式）

    适用于不需要实时流式输出的场景
    """
    if not session_id:
        session_id = learner_engine.create_session(user_id, subject)

    result = await orchestrator.process_message(
        user_id=user_id,
        user_message=message,
        session_id=session_id,
        subject=subject,
    )

    result["session_id"] = session_id
    return result
