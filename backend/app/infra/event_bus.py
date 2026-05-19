"""
Phase 4: 异步事件总线

轻量级内存实现，后续可替换为 Redis Pub/Sub 或 Kafka。
- 发布者不等待消费者完成（fire-and-forget）
- 消费者异常不影响发布者和其他消费者
- 每个 handler 独立超时保护
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from app.shared.events import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]

logger = logging.getLogger("event_bus")


class HandlerTimeoutError(Exception):
    """事件处理器超时"""


class EventBus:
    """
    异步事件总线

    Usage:
        bus = EventBus()
        bus.subscribe("AnswerSubmitted", analytics.on_answer_submitted)
        await bus.publish(event)
    """

    def __init__(self, handler_timeout: float = 5.0) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._handler_timeout = handler_timeout
        self._published_count: int = 0
        self._error_count: int = 0

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        订阅事件类型。

        event_type: 事件类名（如 "AnswerSubmitted"）
        handler: async callable(DomainEvent) -> None
        """
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("EventBus subscribed: %s → %s", event_type, handler.__name__)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅"""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug("EventBus unsubscribed: %s ← %s", event_type, handler.__name__)

    async def publish(self, event: DomainEvent) -> None:
        """
        发布事件 — 异步并行通知所有订阅者，不等待完成。

        消费者异常会被捕获并记录，不影响发布者。
        """
        event_type = type(event).__name__
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug("EventBus: no handlers for %s", event_type)
            return

        self._published_count += 1
        logger.debug(
            "EventBus: publishing %s (id=%s) to %d handler(s)",
            event_type, event.event_id, len(handlers),
        )

        tasks = []
        for handler in handlers:
            tasks.append(self._safe_invoke(event_type, handler, event))

        # 并行执行，不阻塞发布者
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_invoke(
        self,
        event_type: str,
        handler: EventHandler,
        event: DomainEvent,
    ) -> None:
        """安全调用单个 handler，带超时和异常隔离"""
        try:
            await asyncio.wait_for(
                handler(event),
                timeout=self._handler_timeout,
            )
        except asyncio.TimeoutError:
            self._error_count += 1
            logger.error(
                "EventBus: handler %s timed out after %.1fs for %s",
                handler.__name__, self._handler_timeout, event_type,
            )
        except Exception:
            self._error_count += 1
            logger.exception(
                "EventBus: handler %s failed for %s",
                handler.__name__, event_type,
            )

    @property
    def stats(self) -> dict:
        """事件总线统计"""
        return {
            "published": self._published_count,
            "errors": self._error_count,
            "subscriptions": {
                event_type: len(handlers)
                for event_type, handlers in self._handlers.items()
            },
        }

    def clear(self) -> None:
        """清空所有订阅（用于测试）"""
        self._handlers.clear()
        self._published_count = 0
        self._error_count = 0
