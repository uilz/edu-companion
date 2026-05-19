"""
稳定性基础设施 — 超时、重试、熔断

用法:
  @with_timeout(5.0)
  @with_retry(3)
  async def call_llm(prompt): ...
"""
from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger("resilience")

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════
# 异常类型
# ═══════════════════════════════════════════════════════════

class ServiceTimeoutError(Exception):
    """跨模块调用超时"""

class RetryExhaustedError(Exception):
    """重试耗尽 — 所有尝试均失败后抛出"""

class CircuitBreakerOpenError(Exception):
    """熔断器开启 — 拒绝请求"""


# ═══════════════════════════════════════════════════════════
# 超时
# ═══════════════════════════════════════════════════════════

def with_timeout(seconds: float = 5.0):
    """同步跨模块调用超时保护"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=seconds
                )
            except asyncio.TimeoutError:
                caller = func.__qualname__
                logger.warning("⏰ %s timeout after %.1fs", caller, seconds)
                raise ServiceTimeoutError(
                    f"{caller} timed out after {seconds}s"
                )
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════
# 重试（指数退避）
# ═══════════════════════════════════════════════════════════

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    retryable_exceptions: tuple = (ServiceTimeoutError, ConnectionError),
):
    """指数退避重试装饰器"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_error = e
                    if attempt == max_attempts:
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        "🔄 %s attempt %d/%d failed → retry in %.1fs",
                        func.__qualname__, attempt, max_attempts, delay
                    )
                    await asyncio.sleep(delay)
            raise RetryExhaustedError(
                f"{func.__qualname__} exhausted after {max_attempts} attempts"
            ) from last_error
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════
# 熔断器
# ═══════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED = "closed"        # 正常放行
    OPEN = "open"            # 熔断中，直接拒绝
    HALF_OPEN = "half_open"  # 探测中，允许少量请求


class CircuitBreaker:
    """
    熔断器 — 保护下游服务不被雪崩

    状态机:
      CLOSED ──(failures ≥ threshold)──▶ OPEN
      OPEN ──(wait recovery_timeout)──▶ HALF_OPEN
      HALF_OPEN ──(success)──▶ CLOSED
      HALF_OPEN ──(failure)──▶ OPEN
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_count = 0
        self._state = CircuitState.CLOSED
        self._last_state_change = datetime.now()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def last_failure_time(self) -> datetime | None:
        return self._last_failure_time

    @property
    def last_state_change(self) -> datetime:
        return self._last_state_change

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """通过熔断器调用函数"""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_count = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' is OPEN — rejecting"
                )

        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_count >= self.half_open_max_requests:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' HALF_OPEN limit reached"
                )
            self._half_open_count += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        self._success_count += 1
        if self._state == CircuitState.HALF_OPEN:
            logger.info("🔌 Circuit '%s' → CLOSED (recovered)", self.name)
        self._transition_to(CircuitState.CLOSED)
        self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        if self._state == CircuitState.HALF_OPEN:
            logger.warning("🔌 Circuit '%s' HALF_OPEN failed → OPEN", self.name)
            self._transition_to(CircuitState.OPEN)
        elif self._failure_count >= self.failure_threshold:
            logger.warning(
                "🔌 Circuit '%s' → OPEN (%d failures)",
                self.name, self._failure_count
            )
            self._transition_to(CircuitState.OPEN)

    def _should_attempt_recovery(self) -> bool:
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        self._last_state_change = datetime.now()
        if old != new_state:
            logger.info("🔌 Circuit '%s': %s → %s", self.name, old.value, new_state.value)


# ═══════════════════════════════════════════════════════════
# 降级与容错
# ═══════════════════════════════════════════════════════════

def fallback(default_value: T):
    """装饰器：函数失败时返回默认值"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception:
                logger.warning("⚠️ %s failed, returning fallback", func.__qualname__)
                return default_value
        return wrapper
    return decorator


def safe_async(name: str = ""):
    """装饰器：异步函数静默吞异常，返回 None"""
    def decorator(func: Callable[..., Awaitable[T | None]]) -> Callable[..., Awaitable[T | None]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T | None:
            try:
                return await func(*args, **kwargs)
            except Exception:
                logger.warning("🔇 %s suppressed error", name or func.__qualname__)
                return None
        return wrapper
    return decorator
