"""
Event Bus 工具 — 统一事件发布辅助

设计目标
========
1. **一处实现, 多处复用** — 7+ 个新模块各自实现了 `_publish` / `_do_publish` /
   `_safe_publish` / `_publish_event` 等重复 helper, 且其中 5 处使用了
   deprecated 的 `asyncio.get_event_loop()` (Python 3.10+ 已 deprecate,
   Python 3.12+ 将移除)。本模块将所有这些场景收敛为一个统一入口。

2. **自动适配 sync / async 上下文** — 业务层既可能是 FastAPI async endpoint
   (有 running event loop), 也可能是 sync def 端点或后台线程 (无 running
   event loop)。本工具自动识别并选择最合适的执行路径:

   - 已有 running loop (async 上下文): 调度 fire-and-forget task
   - 没有 running loop (sync 上下文): 用 `asyncio.run` 同步执行

3. **永不抛出** — 事件发布失败不应阻塞主业务逻辑。所有异常被捕获并 log
   (使用 `logger.debug`, 不会污染生产日志)。

4. **不引入新依赖** — 仅依赖标准库 + 已有的 `app.infrastructure.event_bus` /
   `app.infrastructure.persistent_event_bus`。

使用方式
========

    from app.infrastructure.event_bus_utils import publish_event_safe
    from shared.events import PlanItemCreated

    publish_event_safe(PlanItemCreated(...))           # 默认从 DI 容器取 bus
    publish_event_safe(event, bus=custom_bus)         # 显式传入 bus

不要这样做 (使用 `asyncio.get_event_loop()` — 已 deprecated):

    import asyncio
    loop = asyncio.get_event_loop()  # DeprecationWarning in 3.10+
    loop.create_task(bus.publish(event))

替代方案 (调用本工具):

    from app.infrastructure.event_bus_utils import publish_event_safe
    publish_event_safe(event)
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from shared.events import DomainEvent

logger = logging.getLogger(__name__)


# ── bus 解析 ──


def _resolve_bus(bus: Any) -> Any:
    """从参数或 DI 容器获取 EventBus 实例。

    优先使用调用方显式传入的 bus; 否则尝试从 `app.application.di.container` 懒加载。
    两者都失败则返回 None, 调用方应优雅跳过发布。
    """
    if bus is not None:
        return bus
    try:
        from app.application.di import container
        return getattr(container, "event_bus", None)
    except Exception as exc:  # noqa: BLE001
        logger.debug("event_bus 解析失败: %s", exc)
        return None


# ── 异步核心: 实际执行 publish 并吞掉所有异常 ──


async def _do_publish(bus: Any, event: "DomainEvent") -> None:
    """执行 `await bus.publish(event)`, 失败时仅 log 不 raise。"""
    event_type = type(event).__name__
    try:
        await bus.publish(event)
    except Exception as exc:  # noqa: BLE001
        logger.debug("事件发布失败 [%s]: %s", event_type, exc)


# ── 公共入口 ──


def publish_event_safe(event: "DomainEvent", *, bus: Any = None) -> None:
    """安全发布 DomainEvent (fire-and-forget, 永不抛出)。

    兼容 sync / async 上下文, 不使用 `asyncio.get_event_loop()` (deprecated)。

    执行路径:
    - **async 上下文** (有 running event loop):
        通过 `loop.create_task` 调度 fire-and-forget task, 立即返回。
    - **sync 上下文** (无 running event loop):
        通过 `asyncio.run` 同步执行 publish, 阻塞到所有 handler 完成。
    - **无 bus**: 静默跳过, 仅记 debug log。

    Args:
        event: 要发布的 `DomainEvent` 实例。
        bus: 可选 — 显式传入 EventBus 实例; 不传则从 DI 容器懒加载。

    Examples:
        >>> from shared.events import PlanItemCreated
        >>> from app.infrastructure.event_bus_utils import publish_event_safe
        >>> publish_event_safe(PlanItemCreated(user_id="u1", plan_item_id="p1"))
        # 在 async 端点中: fire-and-forget, 不阻塞
        # 在 sync 端点中: 同步执行到所有 handler 完成
    """
    bus = _resolve_bus(bus)
    if bus is None:
        logger.debug(
            "event_bus 不可用, 跳过发布 %s",
            type(event).__name__,
        )
        return

    try:
        # 优先: 当前已有 running event loop → 调度 fire-and-forget task
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 退化: 没有 running loop → 用 asyncio.run 同步执行
        # 注意点: `asyncio.run` 不能在已有 loop 的线程中调用, 所以我们必须先用
        # `get_running_loop` 检测。这正是避免 deprecated `get_event_loop` 的核心原因:
        # `get_event_loop` 会自动创建新 loop (在 async 上下文中会得到错的 loop),
        # 而 `get_running_loop` 严格只在有 running loop 时成功。
        try:
            asyncio.run(_do_publish(bus, event))
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "事件发布失败 (sync fallback) [%s]: %s",
                type(event).__name__, exc,
            )
        return

    # async 路径: 调度 fire-and-forget task
    # task 内部异常已由 _do_publish 捕获, 不会向上传播
    loop.create_task(_do_publish(bus, event))
