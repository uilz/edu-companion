"""
EventStore — 统一事件存储

所有用户可感知的系统操作都通过 EventStore.append() 写入，
形成单一真相源。提供 append/query/stream/replay/search 接口。

用法:
    store = EventStore()
    event_id = await store.append(event, stream_type="conversation", stream_id="c1")
    events = await store.stream("conversation", "c1")
    similar = await store.search_similar("三角函数", user_id="u1")
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
from typing import Any, Optional

from shared.events import DomainEvent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# EventRecord — 存储层事件记录
# ═══════════════════════════════════════════

class EventRecord:
    """事件存储记录 — 轻量数据容器, 不依赖 Pydantic"""

    __slots__ = (
        "id", "user_id", "event_type", "stream_type", "stream_id",
        "source_type", "source_id", "parent_event_id", "correlation_id",
        "status", "status_msg", "payload", "summary", "importance",
        "embedding", "created_at", "updated_ats",
    )

    def __init__(
        self,
        id: str = "",
        user_id: str = "",
        event_type: str = "",
        stream_type: str = "",
        stream_id: str = "",
        source_type: str = "",
        source_id: str = "",
        parent_event_id: str = "",
        correlation_id: str = "",
        status: str = "done",
        status_msg: str = "",
        payload: dict | None = None,
        summary: str = "",
        importance: float = 0.0,
        embedding: list[float] | None = None,
        created_at: float = 0.0,
        updated_ats: list[float] | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.event_type = event_type
        self.stream_type = stream_type
        self.stream_id = stream_id
        self.source_type = source_type
        self.source_id = source_id
        self.parent_event_id = parent_event_id
        self.correlation_id = correlation_id
        self.status = status
        self.status_msg = status_msg
        self.payload = payload or {}
        self.summary = summary
        self.importance = importance
        self.embedding = embedding or []
        self.created_at = created_at
        self.updated_ats = updated_ats or []

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}

    @classmethod
    def from_row(cls, row: dict) -> EventRecord:
        created_at = row.get("created_at")
        if hasattr(created_at, "timestamp"):
            created_at = created_at.timestamp()
        elif created_at is None:
            created_at = time.time()
        else:
            created_at = float(created_at)

        embedding = row.get("embedding")
        if embedding is not None:
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            elif isinstance(embedding, str):
                try:
                    embedding = json.loads(embedding)
                except Exception:
                    embedding = None

        return cls(
            id=row.get("id", ""),
            user_id=row.get("user_id", ""),
            event_type=row.get("event_type", ""),
            stream_type=row.get("stream_type") or row.get("source_type", ""),
            stream_id=row.get("stream_id") or row.get("source_id", ""),
            source_type=row.get("source_type", ""),
            source_id=row.get("source_id", ""),
            parent_event_id=row.get("parent_event_id") or "",
            correlation_id=row.get("correlation_id") or "",
            status=row.get("status", "done"),
            status_msg=row.get("status_msg", ""),
            payload=row.get("payload", {}) or {},
            summary=row.get("summary") or "",
            importance=float(row.get("importance", 0.0)),
            embedding=embedding,
            created_at=created_at,
            updated_ats=[],
        )


# ═══════════════════════════════════════════
# EventStore
# ═══════════════════════════════════════════

class EventStore:
    """统一事件存储 — 所有事件的唯一写入入口"""

    def __init__(self):
        self._embedding_fn = None

    def _get_embedding_fn(self):
        if self._embedding_fn is not None:
            return self._embedding_fn
        try:
            from app.infrastructure.llm.embedding_engine import compute_embedding
            self._embedding_fn = compute_embedding
        except Exception:
            self._embedding_fn = lambda _: None
        return self._embedding_fn

    def _get_repo(self):
        from app.infrastructure.db.events_repository import get_events_repo
        return get_events_repo()

    # ── 写入 ──

    async def append(
        self,
        event: DomainEvent,
        *,
        stream_type: str = "",
        stream_id: str = "",
        parent_event_id: str = "",
        correlation_id: str = "",
        summary: str = "",
        importance: float = 0.0,
        compute_embedding: bool = False,
    ) -> str:
        """写入事件 → 返回 event_id

        Args:
            event: DomainEvent 实例
            stream_type: 流类型 (conversation|practice|knowledge|secretary|system)
            stream_id: 流内实体ID
            parent_event_id: 因果链 (哪个事件触发了这个)
            correlation_id: 跨域关联ID
            summary: AI生成摘要
            importance: 0~1 重要性评分
            compute_embedding: 是否计算向量嵌入 (summary 或 payload 摘要)
        """
        repo = self._get_repo()
        event_type = type(event).__name__

        user_id = getattr(event, "user_id", "") or "system"
        source_type = getattr(event, "source_type", "") or "system"
        source_id = getattr(event, "source_id", "") or ""

        # stream 默认与 source 一致
        st = stream_type or source_type
        sid = stream_id or source_id

        # 向量嵌入
        embedding = None
        if compute_embedding:
            embedding_text = summary or self._build_embedding_text(event, event_type)
            if embedding_text:
                embedding = await self._compute_embedding_async(embedding_text)

        from app.infrastructure.db.events_repository import Event
        db_event = Event(
            user_id=user_id,
            event_type=event_type,
            stream_type=st,
            stream_id=sid,
            source_type=source_type,
            source_id=source_id,
            parent_event_id=parent_event_id,
            correlation_id=correlation_id,
            status="done",
            payload=asdict(event),
            summary=summary,
            importance=importance,
            embedding=embedding,
        )
        repo.insert(db_event)
        return db_event.id

    def _build_embedding_text(self, event: DomainEvent, event_type: str) -> str:
        """从事件 payload 构建 embedding 文本"""
        d = asdict(event)
        parts = [event_type]
        for key in ("label", "question", "answer", "content", "skill_id", "node_id"):
            if d.get(key):
                parts.append(str(d[key]))
        return " ".join(parts)

    async def _compute_embedding_async(self, text: str) -> list[float] | None:
        fn = self._get_embedding_fn()
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, fn, text)
        except Exception:
            return None

    # ── 查询 ──

    async def query(
        self,
        user_id: str,
        *,
        stream_type: str = "",
        stream_id: str = "",
        event_type: str = "",
        source_type: str = "",
        source_id: str = "",
        since: float = 0.0,
        until: float = 0.0,
        min_importance: float = 0.0,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EventRecord]:
        """条件查询事件"""
        conditions = ["user_id = %s"]
        params: list[Any] = [user_id]

        if stream_type:
            conditions.append("stream_type = %s")
            params.append(stream_type)
        if stream_id:
            conditions.append("stream_id = %s")
            params.append(stream_id)
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        if source_type:
            conditions.append("source_type = %s")
            params.append(source_type)
        if source_id:
            conditions.append("source_id = %s")
            params.append(source_id)
        if since:
            from datetime import datetime, timezone
            conditions.append("created_at >= %s::timestamptz")
            params.append(datetime.fromtimestamp(since, tz=timezone.utc).isoformat())
        if until:
            from datetime import datetime, timezone
            conditions.append("created_at <= %s::timestamptz")
            params.append(datetime.fromtimestamp(until, tz=timezone.utc).isoformat())
        if min_importance:
            conditions.append("importance >= %s")
            params.append(min_importance)

        sql = (
            f"SELECT * FROM events WHERE {' AND '.join(conditions)} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s"
        )
        params.extend([limit, offset])

        from app.infrastructure.db.database import get_db
        db = get_db()
        rows = db.fetchall(sql, tuple(params))
        return [EventRecord.from_row(dict(r)) for r in rows]

    async def stream(
        self, stream_type: str, stream_id: str, limit: int = 100
    ) -> list[EventRecord]:
        """获取指定流的所有事件 (按时间正序)"""
        from app.infrastructure.db.database import get_db
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM events WHERE stream_type = %s AND stream_id = %s "
            "ORDER BY created_at ASC LIMIT %s",
            (stream_type, stream_id, limit),
        )
        return [EventRecord.from_row(dict(r)) for r in rows]

    async def replay(
        self,
        user_id: str,
        since: float,
        until: float = 0.0,
        event_types: list[str] | None = None,
        limit: int = 200,
    ) -> list[EventRecord]:
        """时间范围回放事件"""
        from datetime import datetime, timezone
        from app.infrastructure.db.database import get_db

        conditions = [
            "user_id = %s",
            "created_at >= %s::timestamptz",
        ]
        params: list[Any] = [
            user_id,
            datetime.fromtimestamp(since, tz=timezone.utc).isoformat(),
        ]

        if until:
            conditions.append("created_at <= %s::timestamptz")
            params.append(datetime.fromtimestamp(until, tz=timezone.utc).isoformat())

        if event_types:
            placeholders = ", ".join(["%s"] * len(event_types))
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(event_types)

        sql = (
            f"SELECT * FROM events WHERE {' AND '.join(conditions)} "
            f"ORDER BY created_at ASC LIMIT %s"
        )
        params.append(limit)

        db = get_db()
        rows = db.fetchall(sql, tuple(params))
        return [EventRecord.from_row(dict(r)) for r in rows]

    # ── 因果链 ──

    async def get_parent_chain(
        self, event_id: str, max_depth: int = 10
    ) -> list[EventRecord]:
        """获取事件的因果链 (从当前事件追溯到根)"""
        from app.infrastructure.db.database import get_db
        db = get_db()
        chain = []
        current = event_id
        for _ in range(max_depth):
            row = db.fetchone(
                "SELECT * FROM events WHERE id = %s", (current,)
            )
            if not row:
                break
            record = EventRecord.from_row(dict(row))
            chain.append(record)
            current = record.parent_event_id
            if not current:
                break
        return chain

    async def get_correlated(
        self, correlation_id: str, limit: int = 50
    ) -> list[EventRecord]:
        """获取同一 correlation_id 的所有跨域事件"""
        from app.infrastructure.db.database import get_db
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM events WHERE correlation_id = %s "
            "ORDER BY created_at ASC LIMIT %s",
            (correlation_id, limit),
        )
        return [EventRecord.from_row(dict(r)) for r in rows]

    # ── 语义搜索 ──

    async def search_similar(
        self,
        query: str,
        user_id: str = "",
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> list[EventRecord]:
        """语义搜索相似事件 (pgvector 余弦距离)

        对 query 计算 embedding，用 pgvector <-> 操作符排序。
        """
        embedding = await self._compute_embedding_async(query)
        if not embedding:
            return []

        # pgvector 期望的格式: [0.1, 0.2, ...]
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

        from app.infrastructure.db.database import get_db
        db = get_db()

        conditions = ["embedding IS NOT NULL"]
        params: list[Any] = [vec_str]

        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
        if min_importance:
            conditions.append("importance >= %s")
            params.append(min_importance)

        params.append(limit)

        sql = (
            f"SELECT *, embedding <-> %s::vector AS _distance "
            f"FROM events WHERE {' AND '.join(conditions)} "
            f"ORDER BY _distance ASC LIMIT %s"
        )

        try:
            rows = db.fetchall(sql, tuple(params))
            return [EventRecord.from_row(dict(r)) for r in rows]
        except Exception as e:
            logger.warning("pgvector 搜索失败: %s", e)
            return []

    # ── 统计 ──

    async def count(
        self,
        user_id: str,
        stream_type: str = "",
        stream_id: str = "",
        event_type: str = "",
    ) -> int:
        """统计事件数量"""
        conditions = ["user_id = %s"]
        params: list[Any] = [user_id]
        if stream_type:
            conditions.append("stream_type = %s")
            params.append(stream_type)
        if stream_id:
            conditions.append("stream_id = %s")
            params.append(stream_id)
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)

        from app.infrastructure.db.database import get_db
        db = get_db()
        row = db.fetchone(
            f"SELECT COUNT(*) AS cnt FROM events WHERE {' AND '.join(conditions)}",
            tuple(params),
        )
        return row["cnt"] if row else 0

    async def get_latest(
        self, user_id: str, event_type: str = "", limit: int = 1
    ) -> EventRecord | None:
        """获取最近一条事件"""
        results = await self.query(
            user_id, event_type=event_type, limit=limit
        )
        return results[0] if results else None


# ── 全局单例 ──

_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    global _store
    if _store is None:
        _store = EventStore()
    return _store