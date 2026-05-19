"""
Phase 4: 全链路追踪

Trace ID 贯穿 HTTP 请求 → UseCase → Domain Service → Infrastructure。
通过 contextvars 实现线程/协程安全的上下文传播。

用法:
    # HTTP middleware
    tid = request.headers.get("x-trace-id") or TraceContext.new()
    TraceContext.set(tid)
    response = await call_next(request)
    response.headers["x-trace-id"] = TraceContext.current()

    # 任何调用点
    logger.info("[%s] submit_answer: user=%s", TraceContext.current(), user_id)
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger("tracing")

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_span_stack: ContextVar[list[str]] = ContextVar("span_stack", default=[])


class TraceContext:
    """全链路追踪上下文管理器"""

    @staticmethod
    def new() -> str:
        """生成新 trace_id"""
        tid = str(uuid.uuid4())[:8]
        _trace_id.set(tid)
        return tid

    @staticmethod
    def set(trace_id: str) -> None:
        """设置当前 trace_id"""
        _trace_id.set(trace_id)

    @staticmethod
    def current() -> str:
        """获取当前 trace_id"""
        return _trace_id.get()

    @staticmethod
    def propagate() -> dict[str, str]:
        """传播 trace_id（用于 HTTP 请求头或消息体）"""
        return {"x-trace-id": _trace_id.get()}


class Span:
    """
    调用跨度 — 记录单个操作的耗时和状态。

    用法:
        with Span("bkt_update") as span:
            result = bkt_engine.update(...)
            span.set_ok()
        # 自动打印: [trace_id=abc123] [span=bkt_update] [duration=28ms] OK
    """

    def __init__(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        self.name = name
        self.metadata = metadata or {}
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0
        self.status: str = "pending"
        self.error: str | None = None

    def __enter__(self) -> Span:
        self.start_time = time.monotonic()
        _push_span(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.duration_ms = (time.monotonic() - self.start_time) * 1000
        _pop_span()

        if exc_type is not None:
            self.status = "ERROR"
            self.error = str(exc_val)
        elif self.status == "pending":
            self.status = "OK"

        tid = _trace_id.get()
        span_path = " → ".join(_span_stack.get()) if _span_stack.get() else self.name

        log_msg = (
            f"[trace_id={tid}] [span={span_path}] "
            f"[duration={self.duration_ms:.0f}ms] {self.status}"
        )
        if self.error:
            log_msg += f" | {self.error}"
        if self.metadata:
            log_msg += f" | {self.metadata}"

        if self.status == "ERROR":
            logger.error(log_msg)
        elif self.duration_ms > 1000:
            logger.warning(log_msg)  # 慢调用警告
        else:
            logger.debug(log_msg)

    def set_ok(self) -> None:
        self.status = "OK"

    def set_error(self, error: str) -> None:
        self.status = "ERROR"
        self.error = error

    def add_metadata(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)


def _push_span(name: str) -> None:
    stack = list(_span_stack.get())
    stack.append(name)
    _span_stack.set(stack)


def _pop_span() -> None:
    stack = list(_span_stack.get())
    if stack:
        stack.pop()
    _span_stack.set(stack)


# ── 便捷函数 ──


def trace_span(name: str, **metadata: Any) -> Span:
    """创建带元数据的 Span"""
    return Span(name, metadata)


def trace_id() -> str:
    """快捷获取当前 trace_id"""
    return _trace_id.get()


# ── FastAPI middleware ──


async def tracing_middleware(request, call_next):
    """
    FastAPI 追踪中间件。

    用法:
        from app.infra.tracing import tracing_middleware
        app.middleware("http")(tracing_middleware)
    """
    tid = request.headers.get("x-trace-id", TraceContext.new())
    TraceContext.set(tid)

    with Span(f"HTTP {request.method} {request.url.path}") as span:
        response = await call_next(request)
        span.set_ok()

    response.headers["x-trace-id"] = tid
    return response
