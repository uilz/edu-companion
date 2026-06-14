"""
Organization Detector — 后台扫描 events 表，按阈值触发组织操作。

阈值:
  - conv: ≥6 条 pending "organize" 事件 → 触发 organize_conversation
  - dir:  ≥3 条 pending "organize" 事件 → 触发 organize_directory

继承 EventService 的异步轮询模式，使用 EventsRepository。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import Counter

from app.infrastructure.db.events_repository import Event, get_events_repo
from app.services.common import get_data_repo
from app.services.common.organization_service import organization_service

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 10   # 秒
_MAX_BATCH = 50
_CONV_THRESHOLD = 6
_DIR_THRESHOLD = 3


class OrganizationDetector:
    """后台轮询 events 表，按阈值触发组织操作。"""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    # ─── 生命周期 ─────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """启动后台轮询 (asyncio task)。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("OrganizationDetector 已启动 (conv≥%d, dir≥%d)", _CONV_THRESHOLD, _DIR_THRESHOLD)

    async def stop(self) -> None:
        """停止后台轮询。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("OrganizationDetector 已停止")

    # ─── 轮询 ─────────────────────────────────────

    async def _poll_loop(self) -> None:
        """轮询主循环。"""
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("OrganizationDetector 轮询异常")
            await asyncio.sleep(_POLL_INTERVAL)

    async def _poll_once(self) -> None:
        """单次轮询: 查询 pending organize 事件 → 分组计数 → 超阈值触发。"""
        repo = get_events_repo()
        events = repo.query(
            event_type="organize",
            status="pending",
            limit=_MAX_BATCH,
        )
        if not events:
            return

        # 按 source_type + source_id 分组计数
        conv_counter: Counter[str] = Counter()
        dir_counter: Counter[str] = Counter()
        user_by_src: dict[str, str] = {}

        for evt in events:
            user_by_src[evt.source_id] = evt.user_id
            if evt.source_type == "conversation":
                conv_counter[evt.source_id] += 1
            elif evt.source_type == "directory":
                dir_counter[evt.source_id] += 1

        # ── 触发对话级组织 ──
        for conv_id, count in conv_counter.items():
            if count >= _CONV_THRESHOLD:
                user_id = user_by_src.get(conv_id, "")
                if not user_id:
                    continue
                try:
                    await organization_service.organize_conversation(user_id, conv_id)
                    # 标记该 conv 的所有同批事件为 done
                    for evt in events:
                        if evt.source_id == conv_id:
                            repo.mark_done(evt.id)
                    # 触发父目录组织事件
                    data = get_data_repo().load(user_id)
                    conv = data.directory_nodes.get(conv_id)
                    if conv and conv.parent_id:
                        repo.insert(Event(
                            id=f"evt_{uuid.uuid4().hex[:12]}",
                            user_id=user_id,
                            event_type="organize",
                            source_type="directory",
                            source_id=conv.parent_id,
                            status="pending",
                        ))
                except Exception:
                    logger.exception("organize_conversation(%s) 失败", conv_id)

        # ── 触发目录级组织 ──
        for dir_id, count in dir_counter.items():
            if count >= _DIR_THRESHOLD:
                user_id = user_by_src.get(dir_id, "")
                if not user_id:
                    continue
                try:
                    await organization_service.organize_directory(user_id, dir_id)
                    for evt in events:
                        if evt.source_id == dir_id:
                            repo.mark_done(evt.id)
                except Exception:
                    logger.exception("organize_directory(%s) 失败", dir_id)


# 全局单例
organization_detector = OrganizationDetector()
