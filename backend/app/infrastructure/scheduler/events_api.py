"""事件系统 API — 客户端驱动的聚合接口

服务端不再定时扫描聚合，而是提供：
1. GET  /api/events/raw       — 获取原始事件（供前端 Web Worker 聚合）
2. POST /api/events/aggregate — 客户端写入聚合结果
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["事件系统"])


# ── GET /raw — 获取原始事件 ──


@router.get("/raw")
async def get_raw_events(
    user_id: str = Depends(current_user_id),
    limit: int = 100,
    window_minutes: int = 60,
) -> dict:
    """获取指定时间窗口内的原始事件，供客户端聚合"""
    from app.infrastructure.db.database import get_db

    db = get_db()
    event_rows = db.fetchall(
        "SELECT e.id, e.event_type, e.payload, e.user_id, "
        "  e.stream_type, e.stream_id, e.created_at, e.importance "
        "FROM events e "
        "WHERE e.user_id = %s "
        "  AND e.created_at >= NOW() - (%s || ' minutes')::INTERVAL "
        "ORDER BY e.created_at ASC LIMIT %s",
        (user_id, str(window_minutes), limit),
    )
    events = [dict(r) for r in event_rows]
    for evt in events:
        if hasattr(evt.get("created_at"), "isoformat"):
            evt["created_at"] = evt["created_at"].isoformat()
        if isinstance(evt.get("payload"), str):
            import json
            try:
                evt["payload"] = json.loads(evt["payload"])
            except Exception:
                pass
    return {"ok": True, "events": events, "count": len(events)}


# ── POST /aggregate — 客户端写入聚合结果 ──


@router.post("/aggregate")
async def write_aggregate(
    body: dict[str, Any],
    user_id: str = Depends(current_user_id),
) -> dict:
    """客户端聚合完成后写入聚合事件"""
    from uuid import uuid4
    from app.infrastructure.db.events_repository import Event, get_events_repo
    from app.infrastructure.db.database import get_db

    repo = get_events_repo()
    db = get_db()
    aggregates = body.get("aggregates", [])
    written = 0

    for agg in aggregates:
        event_id = f"agg_{uuid4().hex[:12]}"
        dimension = agg.get("dimension", "mixed")
        window_minutes = agg.get("window_minutes", 60)
        payload = agg.get("payload", {})
        payload.update({
            "dimension": dimension,
            "window_minutes": window_minutes,
        })

        db_event = Event(
            id=event_id,
            user_id=user_id,
            event_type=agg.get("event_type", "EpisodeDigest"),
            stream_type="aggregate",
            stream_id=f"{dimension}:{window_minutes}m:{event_id}",
            source_type="client_aggregator",
            source_id="",
            status="done",
            payload=payload,
            summary=agg.get("summary", ""),
            importance=agg.get("importance", 0.5),
        )
        repo.insert(db_event)

        child_ids = agg.get("child_ids", [])
        for cid in child_ids:
            rid = f"rel_{uuid4().hex[:12]}"
            db.execute(
                "INSERT INTO event_relations (id, parent_id, child_id) "
                "VALUES (%s, %s, %s) ON CONFLICT (parent_id, child_id) DO NOTHING",
                (rid, event_id, cid),
            )
        written += 1

    logger.info("客户端写入 %d 条聚合事件 (user=%s)", written, user_id)
    return {"ok": True, "written": written}


# ── GET /tools/definitions — 工具定义（前端无需硬编码）──

_tools_router = APIRouter(prefix="/api/tools", tags=["工具定义"])


@_tools_router.get("/definitions")
async def get_tool_definitions() -> dict:
    """返回所有工具的显示名、图标、描述等信息，供前端加载"""
    from app.infrastructure.llm.tool_registry import get_tool_display_map, ALL_TOOL_INFO

    tools = []
    for name, info in ALL_TOOL_INFO.items():
        tools.append({
            "name": name,
            "zh_name": info.zh_name,
            "icon": info.icon,
            "description": info.description,
            "block_type": info.block_type,
            "is_slow": info.is_slow,
        })
    return {"ok": True, "tools": tools}
