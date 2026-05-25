"""
流式管理器：服务端 token 缓冲 + 断线续流

设计：
- 每个活跃流用 conversation_id 索引
- 缓冲所有 token 事件，WS 断连后流仍在后台跑
- 新 WS 连接可 subscribe 重放缓冲 + 续接实时流
- 30 秒无订阅者自动清理
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class StreamState:
    """单个活跃流的状态"""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.token_buffer: list[str] = []          # 已产出的所有 token chunk
        self._live_queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._done_event = asyncio.Event()
        self._cancel_event = asyncio.Event()
        self.subscribers = 0
        self.last_activity = time.time()
        self.cleanup_task: asyncio.Task | None = None
        self.stream_task: asyncio.Task | None = None
        self._final_done_event: dict | None = None  # 最终的 done 事件

    @property
    def is_done(self) -> bool:
        return self._done_event.is_set()

    @property
    def accumulated_text(self) -> str:
        return "".join(self.token_buffer)

    async def push_event(self, event: dict) -> None:
        """生产者：向流中推送一个事件"""
        if event.get("type") == "token":
            self.token_buffer.append(event.get("content", ""))
        if event.get("type") == "done":
            self._final_done_event = event
            self._done_event.set()
        self.last_activity = time.time()
        await self._live_queue.put(event)

    async def push_error(self, msg: str) -> None:
        await self._live_queue.put({"type": "error", "message": msg})
        self._done_event.set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._done_event.set()

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        """订阅者：重放缓冲 → 实时流"""
        self.subscribers += 1

        try:
            # 1. 重放缓冲中的 token
            buffered = "".join(self.token_buffer)
            if buffered:
                yield {"type": "resume", "content": buffered, "conversation_id": self.conversation_id}

            # 2. 如果已经 done，直接回放最后的 done 事件
            if self._done_event.is_set() and self._final_done_event:
                yield self._final_done_event
                return

            # 3. 继续消费实时队列
            while not self._cancel_event.is_set():
                try:
                    event = await asyncio.wait_for(self._live_queue.get(), timeout=2)
                    if event is None:
                        break
                    yield event
                    if event.get("type") == "done":
                        break
                except asyncio.TimeoutError:
                    # 检查流是否已完成但队列已空
                    if self._done_event.is_set() and self._live_queue.empty():
                        break
                    continue
        finally:
            self.subscribers -= 1
            self.last_activity = time.time()


class StreamManager:
    """全局流管理器（单例）"""

    def __init__(self):
        self._streams: dict[str, StreamState] = {}
        self._cleanup_interval = 30  # 秒

    async def start_stream(
        self,
        conversation_id: str,
        stream_gen: AsyncGenerator[dict, None],
    ) -> StreamState:
        """注册并启动一个流"""
        state = StreamState(conversation_id)
        self._streams[conversation_id] = state

        async def _consume():
            try:
                async for event in stream_gen:
                    if state._cancel_event.is_set():
                        break
                    await state.push_event(event)
            except Exception as e:
                logger.error(f"Stream consumer error [{conversation_id[:8]}]: {e}")
                await state.push_error(str(e))
            finally:
                logger.info(f"Stream finished [{conversation_id[:8]}]")

        state.stream_task = asyncio.create_task(_consume())
        return state

    def get_state(self, conversation_id: str) -> StreamState | None:
        """获取流状态"""
        return self._streams.get(conversation_id)

    async def subscribe(
        self, conversation_id: str,
    ) -> AsyncGenerator[dict, None] | None:
        """订阅一个已有流"""
        state = self._streams.get(conversation_id)
        if not state:
            return None
        if state.is_done:
            # 流已完成但缓冲还在：回放并返回
            async def _replay():
                buffered = "".join(state.token_buffer)
                if buffered:
                    yield {"type": "resume", "content": buffered, "conversation_id": conversation_id}
                if state._final_done_event:
                    yield state._final_done_event
            return _replay()
        return state.subscribe()

    def cleanup_expired(self) -> int:
        """清理过期流（无订阅者超过 30 秒）"""
        now = time.time()
        expired = [
            cid for cid, s in self._streams.items()
            if s.is_done and now - s.last_activity > self._cleanup_interval
        ]
        for cid in expired:
            state = self._streams.pop(cid, None)
            if state and state.stream_task and not state.stream_task.done():
                state.stream_task.cancel()
            logger.info(f"Stream cleanup [{cid[:8]}]")
        return len(expired)

    def remove(self, conversation_id: str) -> None:
        """主动移除一个流"""
        state = self._streams.pop(conversation_id, None)
        if state:
            state.cancel()


# 全局单例
stream_manager = StreamManager()
