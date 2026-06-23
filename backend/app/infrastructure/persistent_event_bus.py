"""
PersistentEventBus — 持久化事件总线

基于 events 表实现可靠事件分发。publish() → INSERT 到 events 表，
后台轮询 pending 事件 → dispatch → mark done。
进程崩溃后事件不丢失，重启后可恢复。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Awaitable, Callable

from shared.events import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]

logger = logging.getLogger(__name__)


class PersistentEventBus:
    """持久化事件总线 — events 表驱动"""

    def __init__(self, handler_timeout: float = 5.0, poll_interval: float = 0.5):
        self._handlers: dict[str, list[EventHandler]] = {}
        self._timeout = handler_timeout
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._published_count = 0
        self._error_count = 0

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅事件类型"""
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("订阅 %s ← %s", event_type, handler.__qualname__)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅"""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug("取消订阅 %s ← %s", event_type, handler.__qualname__)

    async def publish(self, event: DomainEvent) -> str:
        """发布事件 → EventStore 写入 + 立即 dispatch + 短期记忆，返回 event_id

        EventStore 写入保证单一真相源；
        立即 dispatch 保证与内存 EventBus 行为一致；
        EventMemory 短期记忆供 AI 上下文注入。
        """
        from app.infrastructure.db.events_repository import Event, EventsRepository

        event_type = type(event).__name__
        self._published_count += 1

        # 提取元信息
        user_id = getattr(event, "user_id", "") or "system"
        source_type = getattr(event, "source_type", "") or "system"
        source_id = getattr(event, "source_id", "") or ""

        # 写入 EventStore (统一存储)
        try:
            from app.infrastructure.event_store import get_event_store
            store = get_event_store()
            await store.append(
                event,
                stream_type=source_type,
                stream_id=source_id,
                compute_embedding=False,  # 按需开启，节省计算
            )
        except Exception:
            logger.debug("EventStore 写入失败，回退到直接 DB 写入", exc_info=True)

        # 写入 DB (保留兼容)
        repo = EventsRepository()
        db_event = Event(
            user_id=user_id,
            event_type=event_type,
            source_type=source_type,
            source_id=source_id,
            status="pending",
            payload=asdict(event),
        )
        repo.insert(db_event)

        # 写入短期记忆 (供 AI 上下文)
        try:
            from app.infrastructure.event_memory import get_event_memory
            from app.infrastructure.event_store import EventRecord
            record = EventRecord(
                id=db_event.id,
                user_id=user_id,
                event_type=event_type,
                stream_type=source_type,
                stream_id=source_id,
                source_type=source_type,
                source_id=source_id,
                payload=asdict(event),
                created_at=db_event.created_at,
            )
            memory = get_event_memory()
            memory.remember(user_id, record)
            # 工作记忆 (如果在会话中)
            if source_type == "conversation" and source_id:
                memory.working_event(user_id, source_id, record)
            elif source_type == "practice" and source_id:
                memory.working_event(user_id, source_id, record)
        except Exception:
            logger.debug("EventMemory 写入失败", exc_info=True)

        # 立即 dispatch（与内存 EventBus 行为一致）
        await self._dispatch_to_handlers(event_type, event)

        # 标记完成
        repo.mark_done(db_event.id)
        return db_event.id

    async def _poll_and_dispatch(self):
        """后台轮询 pending 事件并分发"""
        from app.infrastructure.db.events_repository import EventsRepository

        repo = EventsRepository()

        while self._running:
            try:
                events = repo.get_pending_events(limit=10)
                for row in events:
                    event_type = row["event_type"]
                    payload = row.get("payload", {}) or {}
                    handlers = self._handlers.get(event_type, [])
                    if not handlers:
                        repo.mark_done(row["id"])
                        continue

                    # 从 payload 重建 DomainEvent
                    event_cls = self._resolve_event_class(event_type)
                    if event_cls is not None:
                        try:
                            domain_event = event_cls(**payload)
                        except TypeError:
                            logger.warning(
                                "无法从 payload 重建 %s，跳过", event_type
                            )
                            repo.mark_done(row["id"])
                            continue
                    else:
                        repo.mark_done(row["id"])
                        continue

                    # 并行 dispatch 所有 handler
                    await self._dispatch_to_handlers(event_type, domain_event)
                    repo.mark_done(row["id"])
            except Exception as e:
                logger.error(f"Poll error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _dispatch_to_handlers(
        self, event_type: str, event: DomainEvent
    ) -> None:
        """并行分发事件到所有订阅 handler"""
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return

        logger.info(
            "📤 [%s] dispatching to %d handler(s)",
            event_type, len(handlers),
        )

        async def safe_invoke(handler: EventHandler) -> None:
            name = handler.__qualname__
            try:
                await asyncio.wait_for(handler(event), timeout=self._timeout)
                logger.debug("✅ [%s] → %s OK", event_type, name)
            except asyncio.TimeoutError:
                self._error_count += 1
                logger.error(
                    "⏰ [%s] → %s TIMEOUT (%.1fs)",
                    event_type, name, self._timeout,
                )
            except Exception:
                self._error_count += 1
                logger.exception("❌ [%s] → %s FAILED", event_type, name)

        tasks = [asyncio.create_task(safe_invoke(h)) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _resolve_event_class(event_type: str) -> type[DomainEvent] | None:
        """从事件类型名解析 DomainEvent 子类"""
        from shared.events import EVENT_TYPES
        return EVENT_TYPES.get(event_type)

    async def start(self):
        """启动后台轮询"""
        self._running = True
        self._task = asyncio.create_task(self._poll_and_dispatch())

    async def stop(self):
        """停止后台轮询"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
