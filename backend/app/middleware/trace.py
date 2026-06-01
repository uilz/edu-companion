"""请求追踪中间件 — 为每个请求注入 trace_id"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("trace")


class TraceMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求注入 trace_id 并记录耗时"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", uuid.uuid4().hex[:12])
        request.state.trace_id = trace_id
        start = time.time()

        response = await call_next(request)
        elapsed = time.time() - start

        response.headers["X-Trace-Id"] = trace_id

        if elapsed > 1.0:
            logger.warning(
                "SLOW [%s] %s %s (%.2fs)",
                trace_id, request.method, request.url.path, elapsed,
            )
        elif elapsed > 0.3:
            logger.info(
                "[%s] %s %s (%.2fs)",
                trace_id, request.method, request.url.path, elapsed,
            )

        return response
