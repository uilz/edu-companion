"""
异步领域事件总线

设计:
- 发布者等待所有 handler 完成
- 多个 handler 并行执行
- 单个 handler 失败不影响其他 handler
- 5 秒超时保护每个 handler
- TODO: 后续可替换为 Redis Pub/Sub 或 Kafka
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from shared.events import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]

logger = logging.getLogger("event_bus")


class EventBus:
    """内存异步事件总线"""

    def __init__(self, handler_timeout: float = 5.0):
        self._handlers: dict[str, list[EventHandler]] = {}
        self._timeout = handler_timeout
        self._published_count = 0
        self._error_count = 0

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        订阅事件

        用法:
          bus.subscribe("AnswerSubmitted", analytics.on_answer)
          bus.subscribe("AnswerSubmitted", habits.on_answer)
        """
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("订阅 %s ← %s", event_type, handler.__qualname__)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅"""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug("取消订阅 %s ← %s", event_type, handler.__qualname__)

    async def publish(self, event: DomainEvent) -> None:
        """
        发布事件 — 等待所有 handler 完成

        所有 handler 并行执行，单个失败不影响其他。
        """
        event_type = type(event).__name__
        handlers = self._handlers.get(event_type, [])
        self._published_count += 1

        if not handlers:
            return

        logger.info(
            "📤 [%s] publishing to %d handler(s)",
            event_type, len(handlers)
        )

        async def safe_invoke(handler: EventHandler) -> None:
            name = handler.__qualname__
            try:
                await asyncio.wait_for(handler(event), timeout=self._timeout)
                logger.debug("✅ [%s] → %s OK", event_type, name)
            except asyncio.TimeoutError:
                self._error_count += 1
                logger.error("⏰ [%s] → %s TIMEOUT (%.1fs)",
                             event_type, name, self._timeout)
            except Exception:
                self._error_count += 1
                logger.exception("❌ [%s] → %s FAILED", event_type, name)

        # 并行执行并等待完成
        tasks = [asyncio.create_task(safe_invoke(h)) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
