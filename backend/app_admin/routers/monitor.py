"""系统监控 — analyst+ 权限

GET    /events/recent         最近事件流
GET    /events/stats          事件统计（按 type 聚合）
GET    /events/trend          事件趋势（按天聚合）
GET    /system/health         系统健康
GET    /system/errors         最近错误
GET    /system/logs           日志查看（psql 日志模拟）
PUT    /alerts/config         设置告警阈值
GET    /alerts/config         获取告警配置
GET    /alerts/check          检查当前是否触发告警
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


# ── 告警配置（内存存储 + 持久化到文件） ──

_ALERTS_FILE = os.path.join(os.path.dirname(__file__), "..", ".admin_alerts.json")

_DEFAULT_ALERTS = {
    "pending_events_threshold": 100,       # 待处理事件超过此值告警
    "db_size_gb_threshold": 1.0,           # DB 大小超过此 GB 告警
    "error_rate_threshold": 0.1,           # 错误率超过此值告警（未来用）
    "dau_drop_pct": 50,                    # DAU 环比下降超过此百分比告警
    "poll_interval_seconds": 60,           # 前端轮询间隔（秒）
}


def _load_alerts() -> dict:
    try:
        if os.path.exists(_ALERTS_FILE):
            with open(_ALERTS_FILE) as f:
                return {**_DEFAULT_ALERTS, **json.load(f)}
    except Exception:
        pass
    return dict(_DEFAULT_ALERTS)


def _save_alerts(cfg: dict):
    os.makedirs(os.path.dirname(_ALERTS_FILE) or ".", exist_ok=True)
    with open(_ALERTS_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


# ── Events ──

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
        where.append("event_type = %s")
    if user_id:
        params.append(user_id)
        where.append("user_id = %s")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    rows = repo.query(
        f"SELECT id AS event_id, event_type, user_id, "
        f"source_id AS node_id, "
        f"CASE WHEN status='pending' THEN FALSE ELSE TRUE END AS processed, "
        f"created_at AS timestamp, payload "
        f"FROM events{where_sql} ORDER BY created_at DESC LIMIT %s",
        tuple(params),
    ) or []
    return {"items": rows, "count": len(rows)}


@router.get("/events/stats")
async def event_stats(
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(require_role("analyst")),
):
    repo = _repo()
    rows = repo.query(
        "SELECT event_type, COUNT(*) AS cnt, "
        "  COUNT(*) FILTER (WHERE status = 'pending') AS pending "
        "FROM events "
        "WHERE created_at > NOW() - (%s || ' hours')::interval "
        "GROUP BY event_type ORDER BY cnt DESC",
        (str(hours),),
    ) or []
    return {"window_hours": hours, "by_type": rows}


@router.get("/events/trend")
async def event_trend(
    days: int = Query(7, ge=1, le=90),
    _: dict = Depends(require_role("analyst")),
):
    """事件趋势（按天聚合），用于前端折线图"""
    repo = _repo()
    rows = repo.query(
        "SELECT DATE(created_at) AS day, "
        "       COUNT(*) AS total, "
        "       COUNT(*) FILTER (WHERE status = 'pending') AS pending "
        "FROM events "
        "WHERE created_at > NOW() - (%s || ' days')::interval "
        "GROUP BY DATE(created_at) ORDER BY day",
        (str(days),),
    ) or []
    return {"days": days, "series": rows}


# ── System ──

@router.get("/system/health")
async def system_health(_: dict = Depends(require_role("analyst"))):
    repo = _repo()
    if not repo:
        raise HTTPException(503, "AdminRepository 不可用")

    rows = repo.query("""
        SELECT
            (SELECT COUNT(*) FROM users WHERE is_active = TRUE) AS active_users,
            (SELECT COUNT(*) FROM events WHERE status = 'pending') AS pending_events,
            (SELECT COUNT(*) FROM knowledge_nodes) AS nodes_total,
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
        "db_size_gb": round(int(info.get("db_bytes", 0) or 0) / 1024 / 1024 / 1024, 4),
        "pid": os.getpid(),
    }


@router.get("/system/errors")
async def recent_errors(
    limit: int = Query(30, ge=1, le=200),
    _: dict = Depends(require_role("analyst")),
):
    repo = _repo()
    rows = repo.query(
        "SELECT id AS event_id, event_type, user_id, source_id AS node_id, "
        "created_at AS timestamp, payload "
        "FROM events WHERE status = 'pending' "
        "ORDER BY created_at ASC LIMIT %s",
        (limit,),
    ) or []
    return {"pending_count": len(rows), "items": rows}


@router.get("/system/logs")
async def system_logs(
    lines: int = Query(50, ge=10, le=500),
    _: dict = Depends(require_role("analyst")),
):
    """查看最近 N 行 admin 后端日志"""
    import subprocess
    try:
        result = subprocess.run(
            ["journalctl", "-u", "edu-admin", "--no-pager", "-n", str(lines)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            logs = result.stdout.strip().split("\n")
        else:
            # fallback: 读取日志文件
            log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
            log_files = sorted(
                [f for f in os.listdir(log_dir) if f.startswith("admin_backend")],
                reverse=True,
            )
            if log_files:
                with open(os.path.join(log_dir, log_files[0])) as f:
                    all_lines = f.readlines()
                    logs = [l.rstrip() for l in all_lines[-lines:]]
            else:
                logs = ["(无日志文件)"]
    except Exception as e:
        logs = [f"(无法读取日志: {e})"]

    return {"lines": len(logs), "items": logs}


# ── Alert config ──

@router.get("/alerts/config")
async def get_alert_config(_: dict = Depends(require_role("analyst"))):
    return _load_alerts()


@router.put("/alerts/config")
async def update_alert_config(
    body: dict,
    _: dict = Depends(require_role("analyst")),
):
    current = _load_alerts()
    allowed_keys = set(_DEFAULT_ALERTS.keys())
    for k, v in body.items():
        if k in allowed_keys and isinstance(v, (int, float)):
            current[k] = v
    _save_alerts(current)
    logger.info("admin 更新告警配置: %s", body)
    return {"ok": True, "config": current}


@router.get("/alerts/check")
async def check_alerts(_: dict = Depends(require_role("analyst"))):
    """检查当前是否触发告警"""
    cfg = _load_alerts()
    health = await system_health(_)

    alerts = []

    # 待处理事件
    if health.get("pending_events", 0) > cfg.get("pending_events_threshold", 100):
        alerts.append({
            "level": "warning",
            "metric": "pending_events",
            "current": health["pending_events"],
            "threshold": cfg["pending_events_threshold"],
            "message": f"待处理事件 {health['pending_events']} 超过阈值 {cfg['pending_events_threshold']}",
        })

    # DB 大小
    if health.get("db_size_gb", 0) > cfg.get("db_size_gb_threshold", 1.0):
        alerts.append({
            "level": "warning",
            "metric": "db_size",
            "current": health["db_size_gb"],
            "threshold": cfg["db_size_gb_threshold"],
            "message": f"数据库大小 {health['db_size_gb']:.2f}GB 超过阈值 {cfg['db_size_gb_threshold']}GB",
        })

    return {
        "alerts": alerts,
        "alert_count": len(alerts),
        "config": cfg,
        "healthy": len(alerts) == 0,
    }
