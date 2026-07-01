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


# ── Event 清理（每小时）──

_EVENT_RETENTION_DAYS = 7


async def event_cleanup() -> None:
    """删除超过保留期的 events 和 event_relations 记录

    每小时执行一次，防止事件表无限增长（此前曾累积 1.3GB/500万行）。
    """
    from app.infrastructure.db.database import get_db
    try:
        db = get_db()

        # 先删 relations（避免 FK 约束）
        rel_deleted = db.execute(
            "DELETE FROM event_relations WHERE created_at < NOW() - (%s || ' days')::INTERVAL",
            (str(_EVENT_RETENTION_DAYS),),
        )

        # 再删 events
        evt_deleted = db.execute(
            "DELETE FROM events WHERE created_at < NOW() - (%s || ' days')::INTERVAL",
            (str(_EVENT_RETENTION_DAYS),),
        )

        if rel_deleted or evt_deleted:
            logger.info("事件清理: 删除 %d 条 event_relations, %d 条 events",
                       rel_deleted, evt_deleted)
    except Exception:
        logger.exception("事件清理异常")
