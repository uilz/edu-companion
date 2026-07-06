"""
StreamBuffer — 流式事件缓冲区（替代 TokenBuffer）

每个 conv_id 一个 entry：
  - events: list[dict]     全部事件（最多 2000）
  - pipeline_task: Task    后台 asyncio Task
  - subscribers: set       当前 SSE generator 的 asyncio.Event
  - done: bool             流是否已结束

无 paused/stopped 状态。Pipeline 自行运行，客户端通过 action=replay 从事件 0 回放。

线程安全：所有写操作通过 asyncio.Lock 保护。
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

_MAX_EVENTS = 2000


class StreamBuffer:
    """内存流式缓冲区 — 单进程内跨协程共享"""

    def __init__(self) -> None:
        self._buffers: dict[str, dict] = {}
        self._active_msg_ids: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, conv_id: str, event: dict, msg_id: str = "") -> None:
        """发布事件到缓冲区，通知所有 subscriber。

        当提供 msg_id 时，事件会被标记该 msg_id 并纳入 msg_id 级别索引。
        """
        async with self._lock:
            entry = self._get_or_create(conv_id)
            if msg_id:
                event["msg_id"] = msg_id
                self._active_msg_ids.setdefault(conv_id, set()).add(msg_id)
            entry["events"].append(event)

            # 限界：超出上限时优先丢弃旧 token 事件
            if len(entry["events"]) > _MAX_EVENTS:
                drop_target = int(_MAX_EVENTS * 0.8)
                surviving: list[dict] = []
                for ev in entry["events"]:
                    if len(entry["events"]) - len(surviving) > drop_target and ev.get("type") == "token":
                        continue
                    surviving.append(ev)
                if len(surviving) > _MAX_EVENTS:
                    entry["events"] = surviving[-_MAX_EVENTS:]
                else:
                    entry["events"] = surviving

            for evt in entry["subscribers"]:
                if not evt.is_set():
                    evt.set()

    async def stream(
        self, conv_id: str, max_wait: float = 10.0,
    ) -> AsyncGenerator[dict, None]:
        """从事件 0 回放全部 + 实时等待新事件。

        退出条件：done=True（流完成）。
        如果缓冲区在 max_wait 秒内未创建，返回 stream_ended。
        """
        entry = None

        # 等待缓冲区创建（pipeline 可能尚未启动）
        for _ in range(int(max_wait * 10)):
            async with self._lock:
                entry = self._buffers.get(conv_id)
                if entry is not None:
                    break
            await asyncio.sleep(0.1)

        if entry is None:
            logger.debug("StreamBuffer: 缓冲区不存在 [%s]", conv_id[:8])
            yield {"type": "stream_ended"}
            return

        sub = asyncio.Event()
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                yield {"type": "stream_ended"}
                return
            entry["subscribers"].add(sub)

        try:
            replayed = 0
            while True:
                # 读取新事件
                async with self._lock:
                    events = list(entry["events"])
                    new_events = events[replayed:]
                    replayed = len(events)
                    done = entry.get("done", False)

                for ev in new_events:
                    yield ev

                if done:
                    break

                # 等待新事件
                await sub.wait()
                sub.clear()
        finally:
            async with self._lock:
                if entry and sub in entry.get("subscribers", set()):
                    entry["subscribers"].discard(sub)

    async def mark_done(self, conv_id: str) -> None:
        """标记流完成，通知 subscriber"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if not entry:
                return
            entry["done"] = True
            for evt in entry["subscribers"]:
                if not evt.is_set():
                    evt.set()

    async def cancel(self, conv_id: str) -> bool:
        """取消 pipeline_task，通知 subscriber"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if not entry:
                return False
            task = entry.get("pipeline_task")
            if task and not task.done():
                task.cancel()
            entry["done"] = True
            for evt in entry["subscribers"]:
                evt.set()
            logger.info("StreamBuffer cancelled [%s]", conv_id[:8])
            return True

    async def has_active(self, conv_id: str) -> bool:
        """检查是否有活跃的 pipeline（running 且未 done）"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if not entry:
                return False
            if entry.get("done"):
                return False
            task = entry.get("pipeline_task")
            return task is not None and not task.done()

    async def set_task(self, conv_id: str, task: asyncio.Task) -> None:
        """关联 asyncio Task"""
        async with self._lock:
            entry = self._get_or_create(conv_id)
            entry["pipeline_task"] = task

    async def get_raw_events(self, conv_id: str, msg_id: str) -> list[dict]:
        """从会话缓冲区中筛选属于指定 msg_id 的事件列表"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if not entry:
                return []
            return [ev for ev in entry["events"] if ev.get("msg_id") == msg_id]

    async def has_msg_events(self, conv_id: str, msg_id: str) -> bool:
        """检查会话缓冲区中是否存在指定 msg_id 的事件"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if not entry:
                return False
            return any(ev.get("msg_id") == msg_id for ev in entry["events"])

    async def get_active_msg_ids(self, conv_id: str) -> set[str]:
        """返回会话中所有活跃的 msg_id 集合（不存在时返回空集合）"""
        async with self._lock:
            return set(self._active_msg_ids.get(conv_id, set()))

    async def cleanup(self, conv_id: str) -> None:
        """清理会话缓冲区及 msg_id 索引"""
        async with self._lock:
            entry = self._buffers.pop(conv_id, None)
            if entry:
                for evt in entry.get("subscribers", set()):
                    evt.set()
            self._active_msg_ids.pop(conv_id, None)

    def _get_or_create(self, conv_id: str) -> dict:
        if conv_id not in self._buffers:
            self._buffers[conv_id] = {
                "events": [],
                "pipeline_task": None,
                "subscribers": set(),
                "done": False,
            }
        return self._buffers[conv_id]


# 全局单例
stream_buffer = StreamBuffer()
