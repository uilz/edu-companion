"""简洁版：后台流活跃检测

设计：
- _active_streams: set[conv_id] 记录正在运行的后台流
- WS 断开后流仍在后台跑，持续写入 DB
- 前端通过 GET /api/stream/active/{conv_id} 检测活跃状态
- 活跃时轮询 loadMessages() 拿到增量内容
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class ActiveStreamTracker:
    """活跃流量追踪器（比 StreamManager 简单 100 倍）"""

    def __init__(self):
        self._active: set[str] = set()
        self._lock = asyncio.Lock()

    async def mark_start(self, conv_id: str) -> None:
        async with self._lock:
            self._active.add(conv_id)
            logger.info(f"Stream active [{conv_id[:8]}]")

    async def mark_done(self, conv_id: str) -> None:
        async with self._lock:
            self._active.discard(conv_id)
            logger.info(f"Stream done [{conv_id[:8]}]")

    async def is_active(self, conv_id: str) -> bool:
        async with self._lock:
            return conv_id in self._active


active_streams = ActiveStreamTracker()
