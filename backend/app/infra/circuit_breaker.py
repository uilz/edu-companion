"""
Phase 4: 熔断器 (Circuit Breaker)

保护下游服务，防止级联故障。
状态机: CLOSED → OPEN → HALF_OPEN → CLOSED

用法:
    llm_cb = CircuitBreaker("llm_service", failure_threshold=3)
    result = await llm_cb.call(llm.generate, prompt="...")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, TypeVar, ParamSpec, Awaitable

logger = logging.getLogger("circuit_breaker")

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"        # 正常通行
    OPEN = "open"            # 熔断中，拒绝请求
    HALF_OPEN = "half_open"  # 探测恢复


class CircuitBreakerOpenError(Exception):
    """熔断器已打开，请求被拒绝"""


class CircuitBreaker:
    """
    熔断器实现。

    状态转换:
    - CLOSED: 正常，累计失败计数
    - OPEN: 失败数 >= threshold，直接拒绝所有请求
    - HALF_OPEN: 等待 recovery_timeout 后，允许一次探测请求
      - 成功 → CLOSED（恢复）
      - 失败 → OPEN（重新熔断）
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests

        self.state = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: datetime | None = None
        self.last_state_change: datetime = datetime.now(timezone.utc)
        self.half_open_in_flight: int = 0

    async def call(
        self,
        func: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """
        通过熔断器调用函数。

        如果熔断器 OPEN 且尚未到恢复时间，直接抛出 CircuitBreakerOpenError。
        """
        self._check_state()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _check_state(self) -> None:
        """检查当前状态，决定是否允许请求通过"""
        if self.state == CircuitState.CLOSED:
            return

        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to(CircuitState.HALF_OPEN)
                logger.info(
                    "CircuitBreaker[%s]: OPEN → HALF_OPEN (recovery attempt)",
                    self.name,
                )
            else:
                raise CircuitBreakerOpenError(
                    f"CircuitBreaker[{self.name}] is OPEN. "
                    f"Retry after {self.recovery_timeout}s"
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_in_flight >= self.half_open_max_requests:
                raise CircuitBreakerOpenError(
                    f"CircuitBreaker[{self.name}] is HALF_OPEN, "
                    f"max in-flight requests reached"
                )
            self.half_open_in_flight += 1

    def _on_success(self) -> None:
        """调用成功回调"""
        self.success_count += 1

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_in_flight = max(0, self.half_open_in_flight - 1)
            if self.half_open_in_flight == 0:
                self._transition_to(CircuitState.CLOSED)
                self.failure_count = 0
                logger.info(
                    "CircuitBreaker[%s]: HALF_OPEN → CLOSED (recovered)",
                    self.name,
                )

    def _on_failure(self, error: Exception) -> None:
        """调用失败回调"""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_in_flight = max(0, self.half_open_in_flight - 1)
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                "CircuitBreaker[%s]: HALF_OPEN → OPEN (probe failed: %s)",
                self.name, error,
            )

        elif (
            self.state == CircuitState.CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                "CircuitBreaker[%s]: CLOSED → OPEN (%d failures, threshold=%d)",
                self.name, self.failure_count, self.failure_threshold,
            )

    def _should_attempt_recovery(self) -> bool:
        """判断是否应该尝试恢复"""
        if self.last_failure_time is None:
            return True
        elapsed = (
            datetime.now(timezone.utc) - self.last_failure_time
        ).total_seconds()
        return elapsed >= self.recovery_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转换"""
        old_state = self.state
        self.state = new_state
        self.last_state_change = datetime.now(timezone.utc)
        logger.debug(
            "CircuitBreaker[%s]: %s → %s",
            self.name, old_state.value, new_state.value,
        )

    @property
    def stats(self) -> dict:
        """熔断器统计"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": (
                self.last_failure_time.isoformat()
                if self.last_failure_time else None
            ),
        }

    def reset(self) -> None:
        """强制重置（用于测试）"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_in_flight = 0
