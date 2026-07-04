"""
事件总线安全发布工具

设计目标：
1. 在写操作路径上发布事件，但不让事件发布失败阻塞主业务
2. 捕获所有异常并 debug 日志记录，避免污染业务响应
3. 统一事件发布入口，便于后续替换底层实现 (Redis/Kafka)

Task #87 引入：用于 MoodStress / 认证 / 秘书偏好等场景。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def publish_event_safe(event: Any) -> bool:
    """
    安全发布领域事件到 EventBus。

    设计：
    - 失败时 debug 日志 + return False，不抛异常
    - 业务路径不因事件发布失败而中断
    - 同步发布（基于现有 EventBus.publish 的 async 接口）
    - 在无 event loop 上下文（如迁移脚本）静默返回 True

    Returns:
        True: 发布成功 / 无事件循环 / 已被 EventBus 接收
        False: 事件总线不可用 / 事件发布异常
    """
    try:
        from app.application.di import container
        bus = container.event_bus
    except Exception as exc:  # noqa: BLE001
        logger.debug("event_bus 不可用，跳过事件 %s: %s", getattr(event, "event_type", type(event).__name__), exc)
        return False

    try:
        import asyncio
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 无事件循环 (例如 CLI / 同步脚本) — 静默跳过
        logger.debug("无事件循环，跳过事件 %s", getattr(event, "event_type", type(event).__name__))
        return True

    if loop is None:
        return True

    try:
        # EventBus.publish 是 async；但写操作路径是 sync (FastAPI 路由可 async 也可 sync)
        # 用 ensure_future 不等待结果，避免阻塞主业务
        asyncio.ensure_future(bus.publish(event))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "事件 %s 发布失败: %s",
            getattr(event, "event_type", type(event).__name__),
            exc,
        )
        return False
