"""
Phase 4: 基础设施层

提供:
- EventBus: 异步事件总线
- resilience: 超时/重试/降级装饰器
- CircuitBreaker: 熔断器
- tracing: 全链路追踪 (TraceContext, Span)

依赖规则: infra 只依赖 shared.protocols 和 shared.events
"""

from app.infra.event_bus import EventBus, HandlerTimeoutError
from app.infra.resilience import (
    with_timeout,
    with_retry,
    fallback,
    safe_async,
    ServiceTimeoutError,
    RetryExhaustedError,
)
from app.infra.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
)
from app.infra.tracing import (
    TraceContext,
    Span,
    trace_span,
    trace_id,
    tracing_middleware,
)

__all__ = [
    # EventBus
    "EventBus",
    "HandlerTimeoutError",
    # Resilience
    "with_timeout",
    "with_retry",
    "fallback",
    "safe_async",
    "ServiceTimeoutError",
    "RetryExhaustedError",
    # CircuitBreaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerOpenError",
    # Tracing
    "TraceContext",
    "Span",
    "trace_span",
    "trace_id",
    "tracing_middleware",
]
