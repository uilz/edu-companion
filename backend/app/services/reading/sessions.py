"""Reading 会话服务 (sessions)

依据 docs/modules/reading/data-model.md §2 + ADR 0003
- 阅读会话表 reading_sessions
- 不更新 CognitiveNode.Belief（阅读是被动接收）
- 结束时触发 ReadingSessionEnded 事件
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.event_bus_utils import publish_event_safe

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return f"rs_{uuid.uuid4().hex[:12]}"


def _ensure_tables() -> None:
    from app.services.reading import _ensure_tables as _et
    _et()


def _row_to_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    out = dict(row)
    for col in ("chapters_visited", "linked_node_ids"):
        v = out.get(col)
        if isinstance(v, str):
            try:
                out[col] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                out[col] = []
    snapshot = out.get("state_snapshot")
    if isinstance(snapshot, str):
        try:
            out["state_snapshot"] = json.loads(snapshot)
        except (json.JSONDecodeError, TypeError):
            out["state_snapshot"] = {}
    return out


def _publish(event: Any) -> None:
    """发布事件 — 委托给 publish_event_safe (自动处理 sync/async 上下文)"""
    publish_event_safe(event)


# ── 会话 CRUD ──


def start_session(
    user_id: str,
    material_id: str,
    mode: str = "intensive",
) -> dict:
    """开始一个阅读会话。"""
    _ensure_tables()
    if mode not in ("intensive", "skim", "review"):
        raise ValueError(f"invalid mode: {mode}")
    from app.infrastructure.db.database import get_db
    db = get_db()
    sid = _uid()
    now = _now()
    db.execute(
        """
        INSERT INTO reading_sessions (
            id, user_id, material_id, mode, started_at,
            chapters_visited, annotations_created, notes_created,
            cards_generated, linked_node_ids, last_active_at
        ) VALUES (%s, %s, %s, %s, %s, '[]'::jsonb, 0, 0, 0, '[]'::jsonb, %s)
        """,
        (sid, user_id, material_id, mode, now, now),
    )
    from shared.events import ReadingSessionStarted
    _publish(ReadingSessionStarted(
        user_id=user_id, session_id=sid, material_id=material_id,
        mode=mode, started_at=now,  # type: ignore[arg-type]
    ))
    return get_session(user_id, sid) or {}


def get_session(user_id: str, session_id: str) -> dict | None:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM reading_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    return _row_to_dict(row)


def get_active_session(user_id: str, material_id: str) -> dict | None:
    """获取用户对某材料的最近未结束会话（用于中断恢复）。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        """SELECT * FROM reading_sessions
           WHERE user_id = %s AND material_id = %s AND ended_at IS NULL
           ORDER BY started_at DESC LIMIT 1""",
        (user_id, material_id),
    )
    return _row_to_dict(row)


def list_sessions(
    user_id: str,
    material_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    conds = ["user_id = %s"]
    params: list[Any] = [user_id]
    if material_id:
        conds.append("material_id = %s")
        params.append(material_id)
    where = " AND ".join(conds)
    rows = db.fetchall(
        f"SELECT * FROM reading_sessions WHERE {where} "
        f"ORDER BY started_at DESC LIMIT %s",
        tuple(params) + (limit,),
    )
    return [_row_to_dict(r) for r in rows]  # type: ignore[misc]


def _compute_progress_pct(state_snapshot: Optional[dict]) -> float:
    """从 state_snapshot 推断进度百分比，兜底 0.0。"""
    if not state_snapshot:
        return 0.0
    explicit = state_snapshot.get("progress_pct")
    if isinstance(explicit, (int, float)) and 0.0 <= float(explicit) <= 1.0:
        return float(explicit)
    last_chunk_index = state_snapshot.get("last_chunk_index")
    total_chunks = state_snapshot.get("total_chunks")
    if (
        isinstance(last_chunk_index, int)
        and isinstance(total_chunks, int)
        and total_chunks > 0
    ):
        return min(1.0, (last_chunk_index + 1) / total_chunks)
    return 0.0


def update_session_activity(
    user_id: str,
    session_id: str,
    *,
    chapter_visited: Optional[str] = None,
    state_snapshot: Optional[dict] = None,
    progress_pct: Optional[float] = None,
    annotations_delta: int = 0,
    notes_delta: int = 0,
    cards_delta: int = 0,
    node_linked: Optional[str] = None,
) -> dict | None:
    """更新会话活动（增量统计）并发布 MaterialProgressUpdated。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = get_session(user_id, session_id)
    if not existing:
        return None
    sets: list[str] = ["last_active_at = %s"]
    params: list[Any] = [_now()]
    if chapter_visited:
        visited = list(existing.get("chapters_visited") or [])
        if chapter_visited not in visited:
            visited.append(chapter_visited)
        sets.append("chapters_visited = %s::jsonb")
        params.append(json.dumps(visited, ensure_ascii=False))
    merged_snapshot: Optional[dict] = None
    if state_snapshot is not None:
        merged_snapshot = {**(existing.get("state_snapshot") or {}), **state_snapshot}
        sets.append("state_snapshot = %s::jsonb")
        params.append(json.dumps(merged_snapshot, ensure_ascii=False, default=str))
    if annotations_delta:
        sets.append("annotations_created = annotations_created + %s")
        params.append(int(annotations_delta))
    if notes_delta:
        sets.append("notes_created = notes_created + %s")
        params.append(int(notes_delta))
    if cards_delta:
        sets.append("cards_generated = cards_generated + %s")
        params.append(int(cards_delta))
    if node_linked:
        nodes = list(existing.get("linked_node_ids") or [])
        if node_linked not in nodes:
            nodes.append(node_linked)
        sets.append("linked_node_ids = %s::jsonb")
        params.append(json.dumps(nodes, ensure_ascii=False))
    params.extend([session_id, user_id])
    db.execute(
        f"UPDATE reading_sessions SET {', '.join(sets)} "
        f"WHERE id = %s AND user_id = %s",
        tuple(params),
    )
    updated = get_session(user_id, session_id)
    # 发布 MaterialProgressUpdated（阅读进度审计事件）
    pct = progress_pct if progress_pct is not None else _compute_progress_pct(merged_snapshot)
    last_chunk_id = ""
    last_offset = 0
    if merged_snapshot:
        last_chunk_id = merged_snapshot.get("last_chunk_id", "")
        last_offset = merged_snapshot.get("last_offset", 0)
    from shared.events import MaterialProgressUpdated
    _publish(MaterialProgressUpdated(
        user_id=user_id,
        source_module="reading",
        material_id=existing.get("material_id", ""),
        session_id=session_id,
        progress_pct=float(pct),
        last_chunk_id=str(last_chunk_id),
        last_offset=int(last_offset),
        updated_at=_now(),
    ))
    return updated


def end_session(
    user_id: str,
    session_id: str,
    duration_seconds: Optional[float] = None,
) -> dict | None:
    """结束会话 + 发布 ReadingSessionEnded 事件。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = get_session(user_id, session_id)
    if not existing:
        return None
    now = _now()
    if duration_seconds is None:
        # 自动计算
        started = existing.get("started_at")
        if isinstance(started, datetime):
            # DB 返回的 TIMESTAMP 是 tz-naive, 而 _now() 是 tz-aware,
            # 直接相减会抛 TypeError. 这里把 started 强制视为 UTC.
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            delta = (now - started).total_seconds()
            duration_seconds = max(0.0, delta)
        else:
            duration_seconds = 0.0
    db.execute(
        "UPDATE reading_sessions SET ended_at = %s, duration_seconds = %s, last_active_at = %s "
        "WHERE id = %s AND user_id = %s",
        (now, int(duration_seconds), now, session_id, user_id),
    )
    from shared.events import ReadingSessionEnded
    _publish(ReadingSessionEnded(
        user_id=user_id,
        session_id=session_id,
        material_id=existing.get("material_id", ""),
        duration_seconds=float(duration_seconds),
        annotations_count=int(existing.get("annotations_created") or 0),
        notes_count=int(existing.get("notes_created") or 0),
        cards_generated=int(existing.get("cards_generated") or 0),
        linked_node_ids=list(existing.get("linked_node_ids") or []),
        ended_at=now,
    ))
    return get_session(user_id, session_id)


def change_mode(
    user_id: str,
    session_id: str,
    new_mode: str,
) -> dict | None:
    """切换阅读模式（精读/略读/回顾） + 发布 ReadingModeChanged 事件。"""
    if new_mode not in ("intensive", "skim", "review"):
        raise ValueError(f"invalid mode: {new_mode}")
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = get_session(user_id, session_id)
    if not existing:
        return None
    old_mode = existing.get("mode", "intensive")
    if old_mode == new_mode:
        return existing
    db.execute(
        "UPDATE reading_sessions SET mode = %s, last_active_at = %s "
        "WHERE id = %s AND user_id = %s",
        (new_mode, _now(), session_id, user_id),
    )
    from shared.events import ReadingModeChanged
    _publish(ReadingModeChanged(
        user_id=user_id, session_id=session_id,
        old_mode=old_mode,  # type: ignore[arg-type]
        new_mode=new_mode,  # type: ignore[arg-type]
        changed_at=_now(),
    ))
    return get_session(user_id, session_id)


def resume_session(
    user_id: str,
    session_id: str,
    last_chunk_id: str = "",
) -> dict | None:
    """恢复会话 + 发布 ReadingSessionResumed 事件。"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    existing = get_session(user_id, session_id)
    if not existing:
        return None
    db.execute(
        "UPDATE reading_sessions SET last_active_at = %s WHERE id = %s AND user_id = %s",
        (_now(), session_id, user_id),
    )
    from shared.events import ReadingSessionResumed
    _publish(ReadingSessionResumed(
        user_id=user_id, session_id=session_id,
        last_chunk_id=last_chunk_id, resumed_at=_now(),
    ))
    return get_session(user_id, session_id)
