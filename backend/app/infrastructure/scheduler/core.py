"""
BackgroundScheduler — 中央后台任务调度器

统一管理所有服务端周期任务，同步 DB 调用自动通过 run_in_executor
放入线程池，避免阻塞 asyncio 事件循环。

用法:
    scheduler = BackgroundScheduler()
    scheduler.add_task("event_bus", 0.5, event_bus_poll)
    scheduler.add_task("event_consumer", 5.0, event_consumer)
    await scheduler.start_all()
    ...
    await scheduler.stop_all()
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

TickFn = Callable[[], Optional[Awaitable[None]]]


class _SchedulerTask:
    """单个调度任务元数据"""

    def __init__(self, name: str, interval: float, fn: TickFn) -> None:
        self.name = name
        self.interval = interval
        self.fn = fn
        self._task: asyncio.Task | None = None
        self._running = False
        self._tick_count = 0
        self._error_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return {
            "name": self.name,
            "interval": self.interval,
            "tick_count": self._tick_count,
            "error_count": self._error_count,
            "running": self._running,
        }


class BackgroundScheduler:
    """中央后台任务调度器"""

    def __init__(self) -> None:
        self._tasks: dict[str, _SchedulerTask] = {}
        self._running = False

    # ── 注册 ──

    def add_task(self, name: str, interval: float, fn: TickFn) -> None:
        """注册一个周期任务

        fn 可以是同步函数或异步函数。
        同步函数会被自动 run_in_executor 避免阻塞事件循环。
        """
        if name in self._tasks:
            logger.warning("调度任务 %s 已存在，跳过注册", name)
            return
        self._tasks[name] = _SchedulerTask(name, interval, fn)
        logger.debug("调度任务已注册: %s (interval=%ss)", name, interval)

    # ── 生命周期 ──

    async def start_all(self) -> None:
        """启动所有已注册的任务"""
        if self._running:
            logger.warning("调度器已在运行")
            return
        self._running = True
        for task in self._tasks.values():
            task._task = asyncio.create_task(self._run_loop(task))
            task._running = True
        logger.info("后台调度器已启动: %d 个任务", len(self._tasks))

    async def stop_all(self) -> None:
        """停止所有任务"""
        self._running = False
        for task in self._tasks.values():
            task._running = False
            if task._task:
                task._task.cancel()
                try:
                    await task._task
                except asyncio.CancelledError:
                    pass
                task._task = None
        logger.info("后台调度器已停止")

    async def start_task(self, name: str) -> None:
        """单独启动一个任务"""
        task = self._tasks.get(name)
        if not task:
            logger.warning("任务 %s 不存在", name)
            return
        if task._running:
            return
        task._running = True
        task._task = asyncio.create_task(self._run_loop(task))
        logger.info("调度任务已启动: %s", name)

    async def stop_task(self, name: str) -> None:
        """单独停止一个任务"""
        task = self._tasks.get(name)
        if not task or not task._running:
            return
        task._running = False
        if task._task:
            task._task.cancel()
            try:
                await task._task
            except asyncio.CancelledError:
                pass
            task._task = None
        logger.info("调度任务已停止: %s", name)

    # ── 内部循环 ──

    async def _run_loop(self, task: _SchedulerTask) -> None:
        """运行一个任务的周期循环"""
        await asyncio.sleep(task.interval)

        while task._running and self._running:
            try:
                await self._execute_tick(task)
                task._tick_count += 1
            except asyncio.CancelledError:
                break
            except Exception:
                task._error_count += 1
                logger.exception("调度任务 %s 执行异常", task.name)
            await asyncio.sleep(task.interval)

    async def _execute_tick(self, task: _SchedulerTask) -> None:
        """执行一次 tick，自动判断 sync/async

        同步函数通过 run_in_executor 放入线程池执行，
        避免阻塞 asyncio 事件循环。
        """
        if inspect.iscoroutinefunction(task.fn):
            await task.fn()
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, task.fn)

    # ── 查询 ──

    def get_stats(self) -> dict:
        """获取所有任务的统计信息"""
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "tasks": {n: t.stats for n, t in self._tasks.items()},
        }

    def get_task(self, name: str) -> Optional[dict]:
        """获取单个任务的统计信息"""
        task = self._tasks.get(name)
        return task.stats if task else None


# ── 全局单例 ──

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler
