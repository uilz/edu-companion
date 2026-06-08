"""系统监控 — analyst+ 权限

GET /events/recent     最近事件流（cognitive_events 实时尾）
GET /events/stats      事件统计（按 type 聚合）
GET /system/health     系统健康（DB / 进程 / 表大小）
GET /system/errors     最近错误日志
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


@router.get("/events/recent")
async def recent_events(
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    _: dict = Depends(require_role("analyst")),
):
    repo = _repo()
    where = []
    params: list = []
    if event_type:
        params.append(event_type)
        where.append(f"event_type = %s")
    if user_id:
        params.append(user_id)
        where.append(f"user_id = %s")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    rows = repo.query(
        f"SELECT event_id, event_type, user_id, node_id, processed, timestamp, payload "
        f"FROM cognitive_events{where_sql} ORDER BY timestamp DESC LIMIT %s",
        tuple(params),
    ) or []
    return {"items": rows, "count": len(rows)}


@router.get("/events/stats")
async def event_stats(
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(require_role("analyst")),
):
    """最近 N 小时事件统计（按 type 聚合）"""
    repo = _repo()
    rows = repo.query(
        "SELECT event_type, COUNT(*) AS cnt, "
        "  COUNT(*) FILTER (WHERE processed = FALSE) AS pending "
        "FROM cognitive_events "
        "WHERE timestamp > NOW() - (%s || ' hours')::interval "
        "GROUP BY event_type ORDER BY cnt DESC",
        (str(hours),),
    ) or []
    return {"window_hours": hours, "by_type": rows}


@router.get("/system/health")
async def system_health(_: dict = Depends(require_role("analyst"))):
    """系统健康：DB 关键表行数 / 待处理事件数 / 进程 uptime"""
    repo = _repo()
    if not repo:
        raise HTTPException(503, "AdminRepository 不可用")

    rows = repo.query("""
        SELECT
            (SELECT COUNT(*) FROM users WHERE is_active = TRUE) AS active_users,
            (SELECT COUNT(*) FROM cognitive_events WHERE processed = FALSE) AS pending_events,
            (SELECT COUNT(*) FROM cognitive_nodes) AS nodes_total,
            (SELECT COUNT(*) FROM conversation_user_meta) AS user_metas,
            (SELECT pg_database_size(current_database())) AS db_bytes,
            (SELECT NOW()) AS now_ts
    """)
    info = rows[0] if rows else {}

    return {
        "status": "ok",
        "now": str(info.get("now_ts") or ""),
        "active_users": int(info.get("active_users", 0) or 0),
        "pending_events": int(info.get("pending_events", 0) or 0),
        "nodes_total": int(info.get("nodes_total", 0) or 0),
        "user_metas": int(info.get("user_metas", 0) or 0),
        "db_size_bytes": int(info.get("db_bytes", 0) or 0),
        "db_size_mb": round(int(info.get("db_bytes", 0) or 0) / 1024 / 1024, 2),
        "pid": os.getpid(),
    }


@router.get("/system/errors")
async def recent_errors(
    limit: int = Query(30, ge=1, le=200),
    _: dict = Depends(require_role("analyst")),
):
    """最近 N 条未处理事件（疑似错误/积压）"""
    repo = _repo()
    rows = repo.query(
        "SELECT event_id, event_type, user_id, node_id, timestamp, payload "
        "FROM cognitive_events WHERE processed = FALSE "
        "ORDER BY timestamp ASC LIMIT %s",
        (limit,),
    ) or []
    return {"pending_count": len(rows), "items": rows}
