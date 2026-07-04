"""
PersistentEventBus — 持久化事件总线

基于 events 表实现可靠事件分发。publish() → EventStore.append() (单一写入路径)，
后台轮询 pending 事件 → dispatch → mark done。
进程崩溃后事件不丢失，重启后可恢复。

修复 (2026-07-04 B1)：
原本 EventStore.append() + EventsRepository.insert() 双写会产生重复行，
现统一走 EventStore.append() 单一写入路径。
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
        # 递归深度保护 (修复 B4)
        self._depth = 0
        self._max_depth = 8

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
        """发布事件 → EventStore 单一写入 + 立即 dispatch + 短期记忆，返回 event_id

        修复 (B1 2026-07-04)：
        EventStore.append() 已经是单一写入路径，移除重复的 EventsRepository.insert。
        EventMemory 短期记忆供 AI 上下文注入。

        修复 (B4 2026-07-04)：
        递归深度保护 — handler 内 publish 嵌套事件时不会无限递归。
        """
        # 递归深度保护
        if self._depth >= self._max_depth:
            logger.warning(
                "⛔ [%s] PersistentEventBus 递归深度 %d 超限，阻断",
                type(event).__name__, self._depth,
            )
            return ""

        self._depth += 1
        try:
            event_type = type(event).__name__
            self._published_count += 1

            # 提取元信息
            user_id = getattr(event, "user_id", "") or "system"
            source_type = getattr(event, "source_type", "") or "system"
            source_id = getattr(event, "source_id", "") or ""

            # 单一写入路径: EventStore.append() (修复 B1)
            try:
                from app.infrastructure.event_store import get_event_store
                store = get_event_store()
                event_id = await store.append(
                    event,
                    stream_type=source_type,
                    stream_id=source_id,
                    compute_embedding=False,  # 按需开启，节省计算
                )
            except Exception:
                logger.debug("EventStore 写入失败", exc_info=True)
                event_id = ""

            # 写入短期记忆 (供 AI 上下文)
            try:
                from app.infrastructure.event_memory import get_event_memory
                from app.infrastructure.event_store import EventRecord
                record = EventRecord(
                    id=event_id,
                    user_id=user_id,
                    event_type=event_type,
                    stream_type=source_type,
                    stream_id=source_id,
                    source_type=source_type,
                    source_id=source_id,
                    payload=asdict(event),
                    created_at=__import__("time").time(),
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

            return event_id
        finally:
            self._depth -= 1

    async def poll_once(self) -> int:
        """单次轮询 pending 事件并分发，返回处理的事件数

        同步 DB 调用通过 run_in_executor 放入线程池。
        供 BackgroundScheduler 周期调用。
        """
        import asyncio
        from app.infrastructure.db.events_repository import EventsRepository

        loop = asyncio.get_event_loop()
        repo = EventsRepository()
        count = 0

        try:
            events = await loop.run_in_executor(None, repo.get_pending_events, 10)
            for row in events:
                event_type = row["event_type"]
                payload = row.get("payload", {}) or {}
                handlers = self._handlers.get(event_type, [])
                if not handlers:
                    await loop.run_in_executor(None, repo.mark_done, row["id"])
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
                        await loop.run_in_executor(None, repo.mark_done, row["id"])
                        continue
                else:
                    await loop.run_in_executor(None, repo.mark_done, row["id"])
                    continue

                # 并行 dispatch 所有 handler
                await self._dispatch_to_handlers(event_type, domain_event)
                await loop.run_in_executor(None, repo.mark_done, row["id"])
                count += 1
        except Exception as e:
            logger.error(f"Poll error: {e}")

        return count

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
        """启动后台轮询（保留兼容，推荐由中央调度器管理）"""
        self._running = True
        self._task = asyncio.create_task(self._legacy_loop())

    async def stop(self):
        """停止后台轮询"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _legacy_loop(self):
        """保留的旧版循环（仅当未使用调度器时生效）"""
        while self._running:
            await self.poll_once()
            await asyncio.sleep(self._poll_interval)
