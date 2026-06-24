"""
KnowledgeEventBus — 知识树事件总线

发布知识树变更事件，支持 SSE 实时推送。
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEvent:
    """知识树事件"""
    event_type: str  # node_created | node_updated | node_deleted | mastery_changed | conversation_linked
    user_id: str
    node_id: str | None = None
    conversation_id: str | None = None
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = {
            "event": self.event_type,
            "node_id": self.node_id,
            "conversation_id": self.conversation_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class KnowledgeEventBus:
    """知识树事件总线 — 发布-订阅 + SSE"""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue[KnowledgeEvent]]] = {}
        self._event_history: list[KnowledgeEvent] = []  # 最近 100 条事件

    def subscribe(self, user_id: str) -> asyncio.Queue[KnowledgeEvent]:
        """订阅用户的知识树事件"""
        if user_id not in self._subscribers:
            self._subscribers[user_id] = []
        queue: asyncio.Queue[KnowledgeEvent] = asyncio.Queue(maxsize=256)
        self._subscribers[user_id].append(queue)
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue[KnowledgeEvent]) -> None:
        """取消订阅"""
        if user_id in self._subscribers:
            self._subscribers[user_id] = [
                q for q in self._subscribers[user_id] if q is not queue
            ]

    async def publish(self, event: KnowledgeEvent) -> None:
        """发布事件到所有订阅者"""
        self._event_history.append(event)
        if len(self._event_history) > 100:
            self._event_history = self._event_history[-100:]

        logger.info(
            "KnowledgeEvent: %s user=%s node=%s conv=%s",
            event.event_type, event.user_id, event.node_id, event.conversation_id,
        )

        # 推送到所有该用户的订阅者
        if event.user_id in self._subscribers:
            dead_queues = []
            for q in self._subscribers[event.user_id]:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.append(q)
            for q in dead_queues:
                self.unsubscribe(event.user_id, q)

        # 同时发布到全局 EventBus
        try:
            from app.application.di import container
            from shared.events import DomainEvent
            bus_event = DomainEvent(
                event_type=f"knowledge_{event.event_type}",
                user_id=event.user_id,
                payload={
                    "node_id": event.node_id,
                    "conversation_id": event.conversation_id,
                    "data": event.data,
                },
            )
            await container.event_bus.publish(bus_event)
        except Exception:
            logger.debug("Global event bus publish skipped", exc_info=True)

    async def stream_events(self, user_id: str) -> AsyncIterator[str]:
        """SSE 流式推送事件"""
        queue = self.subscribe(user_id)
        try:
            # 发送初始连接确认
            yield KnowledgeEvent(
                event_type="connected",
                user_id=user_id,
                data={"message": "SSE connection established"},
            ).to_sse()

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(user_id, queue)


# 全局单例
kb_event_bus = KnowledgeEventBus()