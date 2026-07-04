"""
CognitiveEventsAdapter — CognitiveEventRecord ↔ Event 适配器

单一事件真相源：所有 cognitive 事件都通过 EventsRepository 持久化到 events 表。
本适配器提供 CognitiveEventRecord (领域层) 与 Event (基础设施层) 之间的转换。

设计原则：
- 不创建第二套存储
- 所有 insert/mark_status 都委托给 EventsRepository (PostgreSQL)
- 进程内维护简单内存索引用于快速 query
- DI 容器可注入替代实现（用于测试）

修复 (2026-07-04)：
- 之前 `_get_repo()` 回退到 `container.event_bus`，但 EventBus 没有
  `insert` / `mark_status` 方法，导致 `submit_practice` 静默失败
"""

from __future__ import annotations

import copy
import logging
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CognitiveEventsAdapter:
    """cognitive 事件仓储：单例 in-memory 索引 + PostgreSQL 持久化

    对外接口:
        insert(CognitiveEventRecord)   — 持久化事件
        mark_status(id, status, msg)   — 标记事件状态
        mark_done(id, summary="")      — 标记完成
        get_unprocessed_events(limit)  — 拉取 pending
        mark_event_processed(id)       — 标记 processed (兼容旧 API)
        query_events(node_id, type, lim) — 条件查询
    """

    def __init__(self):
        # 内存索引 — 用于快速 lookup (不替代 DB)
        self._by_id: dict[str, Any] = {}
        self._by_user: dict[str, list[str]] = {}

    # ── 写入 ──

    def insert(self, event: Any) -> None:
        """插入事件 — 先写内存索引，再尝试持久化到 DB

        持久化失败不阻塞（业务事件可降级为内存记录）
        """
        eid = getattr(event, "id", None) or f"cog_evt_{uuid.uuid4().hex[:12]}"
        if not getattr(event, "id", None):
            event.id = eid
        self._by_id[eid] = copy.copy(event)
        self._by_user.setdefault(event.user_id, []).append(eid)

        try:
            from app.infrastructure.db.events_repository import (
                Event,
                EventsRepository,
            )
            db_event = Event(
                id=eid,
                user_id=event.user_id,
                event_type=event.event_type,
                source_type=event.source_type or "cognitive",
                source_id=event.source_id or "",
                status="done",
                payload=event.payload or {},
            )
            EventsRepository().insert(db_event)
        except Exception as exc:
            logger.debug("CognitiveEventsAdapter 持久化降级为内存: %s", exc)

    def mark_status(self, event_id: str, status: str, status_msg: str = "") -> None:
        """更新事件状态"""
        rec = self._by_id.get(event_id)
        if rec is not None:
            rec.status = status
        try:
            from app.infrastructure.db.events_repository import EventsRepository
            EventsRepository().mark_status(event_id, status, status_msg)
        except Exception as exc:
            logger.debug("mark_status 持久化降级: %s", exc)

    def mark_done(self, event_id: str, result_summary: str = "") -> None:
        """标记事件完成"""
        self.mark_status(event_id, "done", result_summary)

    # ── 查询 ──

    def get_unprocessed_events(self, limit: int = 100) -> list[Any]:
        """从内存索引读取 pending 事件"""
        return [self._by_id[k] for k in list(self._by_id.keys())[-limit:]
                if getattr(self._by_id[k], "status", "done") == "pending"][:limit]

    def mark_event_processed(self, event_id: str) -> None:
        """兼容旧 API"""
        self.mark_done(event_id)

    def query_events(
        self,
        node_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[Any]:
        """内存条件查询 — 按 node_id/event_type 过滤"""
        results: list[Any] = []
        for rec in reversed(list(self._by_id.values())):
            if node_id and rec.payload.get("node_id") != node_id:
                continue
            if event_type and rec.event_type != event_type:
                continue
            results.append(rec)
            if len(results) >= limit:
                break
        return results

    def append_event(self, event: Any) -> None:
        """兼容旧 API — 等价 insert"""
        self.insert(event)

    # ── 测试辅助 ──

    def clear(self) -> None:
        self._by_id.clear()
        self._by_user.clear()


# ── 全局单例 ──

_adapter: Optional[CognitiveEventsAdapter] = None


def get_cognitive_events_adapter() -> CognitiveEventsAdapter:
    global _adapter
    if _adapter is None:
        _adapter = CognitiveEventsAdapter()
    return _adapter


def reset_cognitive_events_adapter() -> None:
    """测试辅助：重置单例"""
    global _adapter
    _adapter = None
