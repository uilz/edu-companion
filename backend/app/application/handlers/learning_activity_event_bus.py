"""LearningActivityEventBus — 学习活动 SSE 发布订阅总线

为前端仪表盘、秘书页等场景提供学习活动实时推送。
设计参考 KnowledgeEventBus，但专注于跨壳学习活动流。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class LearningActivitySSEEvent:
    """学习活动 SSE 事件"""

    event_type: str  # activity_created | activity_updated | connected | heartbeat
    user_id: str
    activity_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = {
            "event": self.event_type,
            "activity_id": self.activity_id,
            "user_id": self.user_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class LearningActivityEventBus:
    """学习活动事件总线 — 发布-订阅 + SSE"""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[LearningActivitySSEEvent]]] = {}
        self._event_history: list[LearningActivitySSEEvent] = []  # 最近 100 条
        self._lock = asyncio.Lock()

    def subscribe(self, user_id: str) -> asyncio.Queue[LearningActivitySSEEvent]:
        """订阅用户的学习活动事件"""
        if user_id not in self._subscribers:
            self._subscribers[user_id] = []
        queue: asyncio.Queue[LearningActivitySSEEvent] = asyncio.Queue(maxsize=256)
        self._subscribers[user_id].append(queue)
        logger.debug("LearningActivityEventBus: user=%s 订阅，当前订阅者 %d", user_id, len(self._subscribers[user_id]))
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue[LearningActivitySSEEvent]) -> None:
        """取消订阅"""
        if user_id in self._subscribers:
            self._subscribers[user_id] = [
                q for q in self._subscribers[user_id] if q is not queue
            ]
            if not self._subscribers[user_id]:
                del self._subscribers[user_id]

    async def publish(
        self,
        event_type: str,
        user_id: str,
        activity_id: str | None,
        data: dict[str, Any],
    ) -> None:
        """发布事件到所有订阅者"""
        async with self._lock:
            event = LearningActivitySSEEvent(
                event_type=event_type,
                user_id=user_id,
                activity_id=activity_id,
                data=data,
            )
            self._event_history.append(event)
            if len(self._event_history) > 100:
                self._event_history = self._event_history[-100:]

            if user_id not in self._subscribers:
                return

            dead_queues: list[asyncio.Queue[LearningActivitySSEEvent]] = []
            for q in self._subscribers[user_id]:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.append(q)

            for q in dead_queues:
                self.unsubscribe(user_id, q)

    async def stream_events(
        self,
        user_id: str,
        *,
        heartbeat_interval: float = 30.0,
    ) -> AsyncIterator[str]:
        """SSE 流式推送事件"""
        queue = self.subscribe(user_id)
        try:
            # 发送初始连接确认
            yield LearningActivitySSEEvent(
                event_type="connected",
                user_id=user_id,
                data={"message": "SSE connection established"},
            ).to_sse()

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(user_id, queue)


# 全局单例
learning_activity_event_bus = LearningActivityEventBus()
