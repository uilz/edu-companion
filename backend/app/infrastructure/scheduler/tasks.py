"""
Scheduler Tasks — 所有服务端后台任务的 tick 函数

每个 tick 函数执行一次迭代，由 BackgroundScheduler 周期性调度。
同步 DB 调用通过 run_in_executor 放入线程池，不阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


# ── PersistentEventBus 轮询（0.5s）──


async def event_bus_poll() -> None:
    """轮询 events 表，分发 pending 事件

    从容器获取 PersistentEventBus 实例，调用 poll_once()。
    同步 DB 调用在 poll_once 内部通过 run_in_executor 执行。
    """
    from app.application.di import container
    try:
        count = await container.event_bus.poll_once()
        if count:
            logger.debug("EventBus 分发 %d 个事件", count)
    except Exception:
        logger.exception("EventBus poll 异常")


# ── EventService 消费者（5s）──


async def event_consumer() -> None:
    """消费 cognitive_events 表中未处理的事件

    同步 DB 调用在 _consume_once 内部通过 run_in_executor 执行。
    """
    from app.services.common.event_service import event_service
    try:
        await event_service._consume_once()
    except Exception:
        logger.exception("EventService 消费异常")
