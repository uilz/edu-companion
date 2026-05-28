"""
WebSocket 连接管理器

从 chat.py (已删除) 迁移而来。
用于广播消息到已连接的 WebSocket 客户端。
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器 — 管理多用户多连接的广播"""

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

    async def broadcast(self, data: dict) -> None:
        """广播消息到所有已连接的客户端"""
        msg = json.dumps(data, ensure_ascii=False)
        dead: list[tuple[WebSocket, str]] = []
        for user_id, connections in self._connections.items():
            for ws in connections:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append((ws, user_id))
        for ws, uid in dead:
            self.disconnect(ws, uid)


manager = ConnectionManager()
