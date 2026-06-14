"""
EventsRepository — 通用事件记录存储层

独立于 cognitive 模块, 多个模块 (cognitive/secretary/practice) 共用。
使用 psycopg2 连接池, 复用 app.db.database 的 16 个便捷方法。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.infrastructure.db.database import get_db

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# Event 模型
# ═══════════════════════════════════════════

class Event(BaseModel):
    """统一事件记录 — 取代旧 CognitiveEvent"""
    id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    user_id: str
    event_type: str
    source_type: str                          # conversation | practice | secretary | manual | system
    source_id: str = ""
    status: str = "done"                      # pending | processing | done | failed
    status_msg: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_ats: list[float] = Field(default_factory=lambda: [time.time()])


# ═══════════════════════════════════════════
# 序列化
# ═══════════════════════════════════════════

def _to_json(obj) -> str:
    """Pydantic → JSON 字符串"""
    if obj is None:
        return json.dumps(None)
    if isinstance(obj, list):
        return "[" + ",".join(_to_json(item).strip() for item in obj) + "]"
    if hasattr(obj, "model_dump_json"):
        return obj.model_dump_json()
    return json.dumps(obj, ensure_ascii=False, default=str)


def _ts_to_pg(ts: float) -> str:
    """Unix 时间戳 → PostgreSQL TIMESTAMPTZ"""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _ts_array_to_pg(ts_list: list[float]) -> str:
    """[ts, ...] → PostgreSQL TIMESTAMPTZ[] 文本"""
    items = ", ".join(_ts_to_pg(ts) for ts in ts_list)
    return "{" + items + "}"


def _row_to_event(row: dict) -> Event:
    """DB 行 → Event"""
    return Event(
        id=row["id"],
        user_id=row["user_id"],
        event_type=row["event_type"],
        source_type=row["source_type"],
        source_id=row.get("source_id", ""),
        status=row.get("status", "done"),
        status_msg=row.get("status_msg", ""),
        payload=row.get("payload", {}) or {},
        created_at=row["created_at"].timestamp() if hasattr(row["created_at"], "timestamp") else time.time(),
        updated_ats=[],
    )


# ═══════════════════════════════════════════
# EventsRepository
# ═══════════════════════════════════════════

class EventsRepository:
    """通用事件存储仓库"""

    def insert(self, event: Event) -> None:
        """插入事件 (幂等)"""
        db = get_db()
        data = {
            "id": event.id,
            "user_id": event.user_id,
            "event_type": event.event_type,
            "source_type": event.source_type,
            "source_id": event.source_id,
            "status": event.status,
            "status_msg": event.status_msg,
            "payload": _to_json(event.payload),
            "created_at": _ts_to_pg(event.created_at),
            "updated_ats": _ts_array_to_pg(event.updated_ats),
        }
        db.execute(
            "INSERT INTO events (id, user_id, event_type, source_type, source_id, "
            "status, status_msg, payload, created_at, updated_ats) "
            "VALUES (%(id)s, %(user_id)s, %(event_type)s, %(source_type)s, %(source_id)s, "
            "%(status)s, %(status_msg)s, %(payload)s::jsonb, %(created_at)s::timestamptz, "
            "%(updated_ats)s::timestamptz[]) "
            "ON CONFLICT (id) DO NOTHING",
            data,
        )

    def get(self, event_id: str) -> Optional[Event]:
        """按 ID 查询事件"""
        db = get_db()
        row = db.fetchone("SELECT * FROM events WHERE id = %s", (event_id,))
        if not row:
            return None
        return _row_to_event(row)

    def query(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Event]:
        """按条件查询事件"""
        conditions = ["user_id = %s"]
        params: list[Any] = [user_id]
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        if source_type:
            conditions.append("source_type = %s")
            params.append(source_type)
        if source_id:
            conditions.append("source_id = %s")
            params.append(source_id)
        if status:
            conditions.append("status = %s")
            params.append(status)
        sql = (
            f"SELECT * FROM events WHERE {' AND '.join(conditions)} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s"
        )
        params.extend([limit, offset])
        db = get_db()
        rows = db.fetchall(sql, tuple(params))
        return [_row_to_event(r) for r in rows]

    def mark_status(
        self,
        event_id: str,
        status: str,
        status_msg: str = "",
    ) -> None:
        """更新事件状态 (追加 updated_ats)"""
        now = _ts_to_pg(time.time())
        db = get_db()
        db.execute(
            "UPDATE events SET status = %s, status_msg = %s, "
            "updated_ats = updated_ats || %s::timestamptz "
            "WHERE id = %s",
            (status, status_msg, now, event_id),
        )

    def mark_done(self, event_id: str, result_summary: str = "") -> None:
        """标记为 done, 可选写入结果摘要"""
        if result_summary:
            now = _ts_to_pg(time.time())
            db = get_db()
            db.execute(
                "UPDATE events SET status = 'done', "
                "payload = jsonb_set(payload, '{result_summary}', %s::jsonb, true), "
                "updated_ats = updated_ats || %s::timestamptz "
                "WHERE id = %s",
                (json.dumps(result_summary), now, event_id),
            )
        else:
            self.mark_status(event_id, "done")

    def count_pending_by_source(
        self, user_id: str, source_type: str, source_id: str
    ) -> int:
        """统计指定来源的未处理事件数"""
        db = get_db()
        row = db.fetchone(
            "SELECT COUNT(*) AS cnt FROM events "
            "WHERE user_id = %s AND source_type = %s AND source_id = %s "
            "AND status = 'pending'",
            (user_id, source_type, source_id),
        )
        return row["cnt"] if row else 0


# ── 全局单例 ──

_repo: Optional[EventsRepository] = None


def get_events_repo() -> EventsRepository:
    global _repo
    if _repo is None:
        _repo = EventsRepository()
    return _repo
