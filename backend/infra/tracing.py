"""
全链路追踪 — Trace ID 贯通

用法:
  tid = TraceContext.new()          # 生成新 trace_id
  tid = TraceContext.current()      # 获取当前 trace_id
  headers = TraceContext.propagate()  # 传播到下游

  # middleware 自动注入
  @app.middleware("http")
  async def tracing_middleware(request, call_next):
      tid = request.headers.get("x-trace-id", TraceContext.new())
      trace_id.set(tid)
      response = await call_next(request)
      response.headers["x-trace-id"] = tid
      return response
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncIterator

trace_id: ContextVar[str] = ContextVar("trace_id", default="")
span_id: ContextVar[str] = ContextVar("span_id", default="")

logger = logging.getLogger("tracing")


class TraceContext:
    """全链路追踪上下文 — 基于 ContextVar 的协程安全传播"""

    @staticmethod
    def new() -> str:
        tid = str(uuid.uuid4())[:8]
        trace_id.set(tid)
        return tid

    @staticmethod
    def current() -> str:
        return trace_id.get() or "no-trace"

    @staticmethod
    def propagate() -> dict[str, str]:
        """HTTP 请求头传播"""
        return {"x-trace-id": trace_id.get()}


@asynccontextmanager
async def span(name: str) -> AsyncIterator[str]:
    """
    创建一个追踪 span 并自动记录耗时

    Usage:
      async with span("submit_answer") as sid:
          result = await bkt_engine.update(state)
          # → [trace=abc] [span=submit_answer] [dur=28ms] OK
    """
    sid = str(uuid.uuid4())[:6]
    span_id.set(sid)
    t0 = time.perf_counter()

    try:
        yield sid
    except Exception:
        dt = (time.perf_counter() - t0) * 1000
        logger.error(
            "[trace=%s] [span=%s:%s] [dur=%.0fms] ❌ FAILED",
            trace_id.get(), name, sid, dt
        )
        raise
    else:
        dt = (time.perf_counter() - t0) * 1000
        level = logging.WARNING if dt > 1000 else logging.DEBUG
        logger.log(
            level,
            "[trace=%s] [span=%s:%s] [dur=%.0fms] OK",
            trace_id.get(), name, sid, dt
        )
