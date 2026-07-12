"""Planning — 视图聚合服务（日/周/知识视图）"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Optional

from app.services.planning import _ensure_tables
from app.services.planning._converters import row_to_plan_item
from app.services.planning.aggregators import (
    consume_adaptive_recommendations,
    consume_brief_summary,
    consume_status_bar,
)
from app.services.planning.items import list_plan_items
from shared.events import PlanningSourceModule

logger = logging.getLogger(__name__)


def build_daily_view(user_id: str, on_date: date) -> dict:
    """日视图：时间轴 + 待安排池 + 自适应推荐 + 日总结"""
    items = list_plan_items(user_id, plan_date=on_date)
    timeline: list[dict] = []
    pool: list[dict] = []
    for it in items:
        if it["status"] in ("scheduled", "in_progress", "completed", "extended") and it.get("scheduled_for"):
            timeline.append(it)
        else:
            pool.append(it)
    pool.extend(_collect_pool_from_modules(user_id, on_date, exclude_ids=[x["id"] for x in items]))
    recs = consume_adaptive_recommendations(user_id)
    brief = consume_brief_summary(user_id, on_date)
    status_bar = consume_status_bar(user_id)
    return {
        "date": on_date,
        "status_bar": status_bar,
        "timeline_items": timeline,
        "pending_pool": pool,
        "adaptive_recommendations": recs,
        "brief_summary": brief,
    }


def _collect_pool_from_modules(user_id: str, on_date: date, exclude_ids: list[str]) -> list[dict]:
    """汇聚来自其他模块的待办（best-effort）"""
    out: list[dict] = []
    excluded = set(exclude_ids or [])
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        rows = db.fetchall(
            """SELECT id, title, status, estimated_minutes FROM project_nodes
               WHERE user_id=%s AND status='active' LIMIT 10""",
            (user_id,),
        )
        for r in rows:
            if r["id"] in excluded:
                continue
            out.append({
                "id": f"pool_proj_{r['id']}",
                "source_module": PlanningSourceModule.PROJECT.value,
                "target_type": "project_node",
                "target_ref_id": r["id"],
                "title": r.get("title") or f"项目节点 {r['id']}",
                "estimated_minutes": r.get("estimated_minutes") or 30,
                "status": "pending",
            })
    except Exception as e:
        logger.debug("project_nodes 池子读取失败: %s", e)
    return out


def build_weekly_view(user_id: str, week_start: date) -> dict:
    """周视图：7 天 + 总计"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    week_end = week_start + timedelta(days=6)
    rows = db.fetchall(
        """SELECT plan_date, status, estimated_minutes, actual_minutes
           FROM plan_items
           WHERE user_id=%s AND plan_date BETWEEN %s AND %s""",
        (user_id, week_start, week_end),
    )
    by_day: dict[date, dict] = {}
    for i in range(7):
        d = week_start + timedelta(days=i)
        by_day[d] = {"date": d, "item_count": 0, "total_minutes": 0, "completed_count": 0}
    for r in rows:
        d = r.get("plan_date")
        if not d:
            continue
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                continue
        bucket = by_day.setdefault(d, {"date": d, "item_count": 0, "total_minutes": 0, "completed_count": 0})
        bucket["item_count"] += 1
        bucket["total_minutes"] += (r.get("estimated_minutes") or 0)
        if r.get("status") == "completed":
            bucket["completed_count"] += 1
    days = [by_day[week_start + timedelta(days=i)] for i in range(7)]
    total_minutes = sum(d["total_minutes"] for d in days)
    total_completed = sum(d["completed_count"] for d in days)
    return {
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
        "totals": {
            "total_minutes": total_minutes,
            "total_completed": total_completed,
            "total_items": sum(d["item_count"] for d in days),
        },
        "summary": consume_status_bar(user_id),
    }


def build_knowledge_view(user_id: str, selected_node_id: Optional[str] = None) -> dict:
    """知识视图：知识点 + 待办密度"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    nodes: list[dict] = []
    try:
        rows = db.fetchall(
            """SELECT id, label, level, parent, deleted_at
               FROM knowledge_nodes
               WHERE user_id=%s AND deleted_at IS NULL
               ORDER BY level NULLS LAST, id LIMIT 200""",
            (user_id,),
        )
        for r in rows:
            nid = r["id"]
            count_row = db.fetchone(
                """SELECT COUNT(*) as c FROM plan_items
                   WHERE user_id=%s AND linked_node_ids @> %s::jsonb
                     AND status IN ('pending','scheduled','in_progress')""",
                (user_id, json.dumps([nid])),
            )
            todo_count = count_row["c"] if count_row else 0
            nodes.append({
                "id": nid,
                "label": r.get("label") or nid,
                "level": r.get("level", "atom"),
                "parent": r.get("parent") or "",
                "todo_count": todo_count,
            })
    except Exception as e:
        logger.debug("knowledge_nodes 读取失败: %s", e)
    selected_todos: list[dict] = []
    if selected_node_id:
        rows = db.fetchall(
            """SELECT * FROM plan_items
               WHERE user_id=%s AND linked_node_ids @> %s::jsonb
               ORDER BY priority DESC, plan_date ASC NULLS LAST LIMIT 50""",
            (user_id, json.dumps([selected_node_id])),
        )
        selected_todos = [row_to_plan_item(r) for r in rows]
    return {
        "nodes": nodes,
        "selected_node_id": selected_node_id,
        "selected_node_todos": selected_todos,
    }
