"""
Phase 4: 稳定性机制 — 超时、重试、降级

为所有跨模块同步调用提供保护。
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Callable, TypeVar, ParamSpec, Awaitable

logger = logging.getLogger("resilience")

P = ParamSpec("P")
T = TypeVar("T")


class ServiceTimeoutError(Exception):
    """服务调用超时"""


class RetryExhaustedError(Exception):
    """重试次数耗尽"""


def with_timeout(seconds: float = 5.0):
    """
    超时保护装饰器。

    用法:
        @with_timeout(3.0)
        async def call_external_service(...): ...
    """
    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "%s timed out after %.1fs", func.__name__, seconds
                )
                raise ServiceTimeoutError(
                    f"{func.__name__} timed out after {seconds}s"
                ) from None
        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    backoff: float = 0.5,
    retryable_exceptions: tuple[type[Exception], ...] = (
        ServiceTimeoutError,
        ConnectionError,
        TimeoutError,
    ),
):
    """
    指数退避重试装饰器。

    用法:
        @with_retry(max_attempts=3, backoff=1.0)
        async def call_flaky_service(...): ...
    """
    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_error = e
                    if attempt < max_attempts:
                        wait = backoff * (2 ** (attempt - 1))
                        logger.warning(
                            "%s attempt %d/%d failed, retrying in %.1fs: %s",
                            func.__name__, attempt, max_attempts, wait, e,
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__, max_attempts, e,
                        )

            raise RetryExhaustedError(
                f"{func.__name__} failed after {max_attempts} attempts"
            ) from last_error

        return wrapper
    return decorator


def fallback(default_value: T):
    """
    降级装饰器 — 调用失败时返回默认值。

    用法:
        @fallback([])
        async def get_recommendations(...): ...
    """
    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "%s failed, returning fallback: %s", func.__name__, e,
                )
                return default_value
        return wrapper
    return decorator


def safe_async(description: str = ""):
    """
    安全异步调用装饰器 — 静默吞下异常，不中断调用方。

    用于事件 handler 等 fire-and-forget 场景。

    用法:
        @safe_async("achievement check")
        async def check_achievements(...): ...
    """
    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T | None]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            try:
                return await func(*args, **kwargs)
            except Exception:
                label = description or func.__name__
                logger.exception("safe_async %s failed (swallowed)", label)
                return None
        return wrapper
    return decorator
