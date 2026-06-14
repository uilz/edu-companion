"""
TokenBuffer — 流式事件内存缓存 + 状态管理 + 订阅发布

每个 conversation_id 对应一个 BufferEntry，包含：
  - events: list[dict]      全部缓存事件
  - state: State            当前状态（RUNNING / PAUSED / DONE / CANCELLED）
  - subscribers: list[Event] 等待新事件的 asyncio.Event
  - resume_event: Event     暂停时等待恢复的信号

线程安全：所有写操作通过 asyncio.Lock 保护。
"""

from __future__ import annotations

import asyncio
import enum
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class State(enum.Enum):
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    CANCELLED = "cancelled"


class BufferEntry:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.state: State = State.RUNNING
        self.subscribers: list[asyncio.Event] = []
        self.resume_event = asyncio.Event()
        self.resume_event.set()  # 初始为「可运行」状态


# 单个会话最大缓冲事件数（超过时丢弃旧 token，保留非 token 事件）
_MAX_BUFFERED_EVENTS = 500


class TokenBuffer:
    """内存 Token 缓冲区 — 单进程内跨协程共享"""

    def __init__(self) -> None:
        self._buffers: dict[str, BufferEntry] = {}
        self._lock = asyncio.Lock()

    # ── 生产者 API ──

    async def publish(self, conv_id: str, event: dict) -> None:
        """发布一个事件到指定会话的缓冲区"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                entry = BufferEntry()
                self._buffers[conv_id] = entry
            entry.events.append(event)
            # 限界：超过上限时优先丢弃旧 token 事件，保留 done 等关键事件
            if len(entry.events) > _MAX_BUFFERED_EVENTS:
                # 保留最后 80%，丢弃前面的纯 token 事件
                keep_count = int(_MAX_BUFFERED_EVENTS * 0.8)
                entry.events = entry.events[-keep_count:]
            # 通知所有订阅者
            for evt in entry.subscribers:
                evt.set()

    async def mark_done(self, conv_id: str) -> None:
        """标记流完成"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return
            entry.state = State.DONE
            for evt in entry.subscribers:
                evt.set()

    async def mark_cancelled(self, conv_id: str) -> None:
        """标记流取消（由 stop 触发）"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return
            entry.state = State.CANCELLED
            for evt in entry.subscribers:
                evt.set()

    # ── 消费者 API（SSE） ──

    async def subscribe(
        self, conv_id: str, from_beginning: bool = True,
        wait_for_entry: bool = True, max_wait: float = 5.0,
    ) -> AsyncGenerator[dict, None]:
        """订阅一个会话的流式事件。

        返回 AsyncGenerator：
          1. 回放已有事件（from_beginning=True）
          2. 实时等待新事件
          3. 状态变为 DONE / CANCELLED 时自动退出

        参数：
          wait_for_entry: 如果 True，当缓冲区不存在时最多等待 max_wait 秒
          max_wait: 等待缓冲区创建的超时秒数
        """
        entry: BufferEntry | None = None
        last_read_idx = 0

        # 如果缓冲区不存在，等待它被创建（处理 SSE 在 pipeline 启动前连接）
        if wait_for_entry:
            for _ in range(int(max_wait * 10)):
                async with self._lock:
                    entry = self._buffers.get(conv_id)
                    if entry is not None:
                        break
                await asyncio.sleep(0.1)

        async with self._lock:
            if entry is None:
                entry = self._buffers.get(conv_id)
            if entry is None:
                return

            subscriber_event = asyncio.Event()
            entry.subscribers.append(subscriber_event)
            last_read_idx = 0 if from_beginning else len(entry.events)

            # 如果已结束且没有事件，直接返回
            if entry.state in (State.DONE, State.CANCELLED) and last_read_idx >= len(entry.events):
                return

        # ── 事件循环 ──
        try:
            while True:
                async with self._lock:
                    # 检查状态
                    if entry.state == State.PAUSED:
                        resume_evt = entry.resume_event
                    else:
                        resume_evt = None

                    # 读取新事件
                    new_events = entry.events[last_read_idx:]
                    last_read_idx = len(entry.events)

                # 如果暂停，等待恢复信号
                if resume_evt is not None:
                    await resume_evt.wait()

                # yield 新事件
                for evt in new_events:
                    yield evt

                # 检查是否结束
                async with self._lock:
                    if entry.state in (State.DONE, State.CANCELLED):
                        # yield 最后一批事件
                        final_events = entry.events[last_read_idx:]
                        last_read_idx = len(entry.events)
                        if final_events:
                            # 需要在锁外 yield
                            pass
                        else:
                            break

                if final_events:
                    for evt in final_events:
                        yield evt
                    break

                # 等待新事件
                await subscriber_event.wait()
                subscriber_event.clear()
        finally:
            # 清理订阅者；无订阅者且流已结束时自动清理缓冲区
            async with self._lock:
                if entry and subscriber_event in entry.subscribers:
                    entry.subscribers.remove(subscriber_event)
                if entry and entry.state in (State.DONE, State.CANCELLED) and not entry.subscribers:
                    self._buffers.pop(conv_id, None)
                    logger.debug("TokenBuffer auto-cleanup [%s]", conv_id[:8])

    # ── 控制 API ──

    async def pause(self, conv_id: str) -> bool:
        """暂停流。返回 False 表示会话不存在或不在 RUNNING 状态"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None or entry.state != State.RUNNING:
                return False
            entry.state = State.PAUSED
            entry.resume_event.clear()
            logger.info("TokenBuffer pause [%s]", conv_id[:8])
            return True

    async def resume(self, conv_id: str) -> bool:
        """恢复流。返回 False 表示会话不存在或不在 PAUSED 状态"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None or entry.state != State.PAUSED:
                return False
            entry.state = State.RUNNING
            entry.resume_event.set()
            logger.info("TokenBuffer resume [%s]", conv_id[:8])
            return True

    async def stop(self, conv_id: str) -> bool:
        """停止/取消流。返回 False 表示会话不存在"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return False
            entry.state = State.CANCELLED
            for evt in entry.subscribers:
                evt.set()
            logger.info("TokenBuffer stop [%s]", conv_id[:8])
            return True

    # ── 查询 API ──

    async def is_active(self, conv_id: str) -> bool:
        """检查指定会话的流是否活跃（RUNNING 或 PAUSED）"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return False
            return entry.state in (State.RUNNING, State.PAUSED)

    async def get_state(self, conv_id: str) -> str | None:
        """获取会话的流状态，不存在返回 None"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return None
            return entry.state.value

    async def cleanup(self, conv_id: str) -> None:
        """清理会话的缓冲区（流完成后调用）"""
        async with self._lock:
            entry = self._buffers.pop(conv_id, None)
            if entry:
                for evt in entry.subscribers:
                    evt.set()
                logger.info("TokenBuffer cleanup [%s]", conv_id[:8])

    async def check_paused(self, conv_id: str) -> bool:
        """检查流是否暂停（供 pipeline 循环中调用）"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return False
            return entry.state == State.PAUSED

    async def check_cancelled(self, conv_id: str) -> bool:
        """检查流是否取消（供 pipeline 循环中调用）"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return False
            return entry.state == State.CANCELLED

    async def wait_resume(self, conv_id: str) -> None:
        """等待流恢复（供 pipeline 循环中调用）"""
        async with self._lock:
            entry = self._buffers.get(conv_id)
            if entry is None:
                return
            resume_evt = entry.resume_event
        await resume_evt.wait()


# ── 全局单例 ──
token_buffer = TokenBuffer()
