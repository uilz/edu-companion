"""Planning Service — DB queries + 复用后端引擎数据组装

核心原则：
- 不重建调度/复习/疲劳/习惯分析逻辑
- 通过调用 AdaptivePlanGenerator / habit_formation / review_reminder / fatigue_manager /
  daily_brief / learning_profile 已有服务拿到数据后聚合
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from app.services.planning import _ensure_tables
from app.services.planning.completion_writer import planning_completion_writer
from app.infrastructure.event_bus_utils import publish_event_safe
from shared.events import (
    PlanningSourceModule,
    PlanItemCreated,
    PlanItemCompleted,
    PlanGoalCreated,
    PlanPeriodicReviewGenerated,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 内部 helpers
# ──────────────────────────────────────────────


def _row_to_plan_item(r: dict) -> dict:
    """normalize plan_items row → API dict"""
    linked = r.get("linked_node_ids")
    if isinstance(linked, str):
        try:
            linked = json.loads(linked)
        except (json.JSONDecodeError, TypeError):
            linked = []
    metadata = r.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "source_module": r["source_module"],
        "target_type": r["target_type"],
        "target_ref_id": r["target_ref_id"],
        "title": r["title"],
        "description": r.get("description", ""),
        "estimated_minutes": r.get("estimated_minutes") or 0,
        "actual_minutes": r.get("actual_minutes"),
        "linked_node_ids": linked or [],
        "priority": r.get("priority") or 0,
        "is_mood_rule_affected": bool(r.get("is_mood_rule_affected")),
        "status": r.get("status", "pending"),
        "scheduled_for": r.get("scheduled_for"),
        "started_at": r.get("started_at"),
        "completed_at": r.get("completed_at"),
        "skipped_at": r.get("skipped_at"),
        "plan_date": r.get("plan_date"),
        "metadata": metadata or {},
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }


def _row_to_goal(r: dict) -> dict:
    target = r.get("target_value") or 0
    current = r.get("current_value") or 0
    progress = min(1.0, current / target) if target > 0 else 0.0
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "title": r["title"],
        "description": r.get("description", ""),
        "target_module": r["target_module"],
        "target_metric": r["target_metric"],
        "target_value": target,
        "current_value": current,
        "deadline": r.get("deadline"),
        "status": r.get("status", "active"),
        "progress_pct": progress,
        "created_at": r.get("created_at"),
        "completed_at": r.get("completed_at"),
    }


def _row_to_review(r: dict) -> dict:
    data = r.get("summary_data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            data = {}
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "period_type": r["period_type"],
        "period_start": r["period_start"],
        "period_end": r["period_end"],
        "summary_data": data or {},
        "user_note": r.get("user_note", ""),
        "created_at": r.get("created_at"),
    }


def _row_to_view_layout(r: dict) -> dict:
    def _j(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return v or {}
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "name": r["name"],
        "view_type": r["view_type"],
        "filters": _j(r.get("filters")),
        "layout": _j(r.get("layout")),
        "is_default": bool(r.get("is_default")),
        "created_at": r.get("created_at"),
    }


# ──────────────────────────────────────────────
# 消费后端引擎（不重建）
# ──────────────────────────────────────────────


def _consume_status_bar(user_id: str) -> dict:
    """聚合顶部状态条：疲劳/压力/能量/习惯/番茄钟

    所有数据**消费**自秘书系统 + habit_formation + 0005 mood/stress，
    本函数不实现任何检测逻辑。
    """
    # 习惯等级（消费 habit_formation）
    habit_level = "beginner"
    pomodoro = {"work_minutes": 25, "break_minutes": 5, "message": "建议标准番茄钟 25+5"}
    try:
        from app.services.analytics.habit_formation import habit_formation
        from app.infrastructure.db.database import get_db
        db = get_db()
        today_questions = 0
        today_correct = 0
        study_days_row = db.fetchone(
            "SELECT COUNT(DISTINCT DATE(created_at)) as d, COUNT(*) as t FROM practice_attempts WHERE user_id=%s",
            (user_id,),
        )
        study_days = study_days_row["d"] if study_days_row else 0
        total_questions = study_days_row["t"] if study_days_row else 0
        habit_level = habit_formation.get_user_level(total_questions, study_days)
        pomodoro = habit_formation.get_pomodoro_recommendation(fatigue_drop_minute=45)
    except Exception as e:
        logger.debug("habit_formation 消费失败: %s", e)

    # 压力/能量（消费 0005 mood_stress → emotion_records 表）
    pressure_score = None
    energy_score = None
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        # Task #69 修复 C1: 表名 mood_stress_records → emotion_records
        # 列名: pressure_score / energy_score (存在), 时间列 created_at (非 recorded_at)
        try:
            row = db.fetchone(
                """SELECT pressure_score, energy_score
                   FROM emotion_records
                   WHERE user_id=%s
                   ORDER BY created_at DESC NULLS LAST LIMIT 1""",
                (user_id,),
            )
            if row:
                pressure_score = row.get("pressure_score")
                energy_score = row.get("energy_score")
        except Exception as e:
            logger.debug("emotion_records 查询失败（列可能不存在）: %s", e)
    except Exception as e:
        logger.debug("mood_stress 消费失败: %s", e)

    # 疲劳风险（消费 secretary fatigue_manager）
    fatigue_risk = "low"
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        try:
            row = db.fetchone(
                """SELECT payload FROM secretary_proposals
                   WHERE user_id=%s AND action_type IN ('fatigue_high','fatigue_warning','fatigue_break')
                     AND status IN ('pending','active')
                   ORDER BY created_at DESC LIMIT 1""",
                (user_id,),
            )
            if row and row.get("payload"):
                payload = row["payload"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = {}
                sev = (payload or {}).get("severity", "low")
                if sev in ("high", "critical"):
                    fatigue_risk = "high"
                elif sev == "medium":
                    fatigue_risk = "medium"
        except Exception:
            pass
    except Exception as e:
        logger.debug("fatigue_manager 消费失败: %s", e)

    return {
        "fatigue_risk": fatigue_risk,
        "pressure_score": pressure_score,
        "energy_score": energy_score,
        "habit_level": habit_level,
        "pomodoro_work_minutes": pomodoro.get("work_minutes", 25),
        "pomodoro_break_minutes": pomodoro.get("break_minutes", 5),
        "pomodoro_message": pomodoro.get("message", ""),
    }


def _consume_adaptive_recommendations(user_id: str) -> list[dict]:
    """消费 AdaptivePlanGenerator.generate()"""
    try:
        from app.services.analytics.adaptive_planner import adaptive_planner
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 在已有 event loop 中（HTTP 请求路径），改为同步生成器回退
            return _fallback_recommendations(user_id)
        except RuntimeError:
            loop = None
        if loop is None:
            result = asyncio.run(adaptive_planner.generate(user_id, reason="planning_view"))
    except Exception as e:
        logger.debug("adaptive_planner 消费失败: %s", e)
        return _fallback_recommendations(user_id)
    items = (result or {}).get("plan", {}).get("items", [])
    return items


def _fallback_recommendations(user_id: str) -> list[dict]:
    """回退实现：直接从 plan_snapshots 读最近一次"""
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        row = db.fetchone(
            "SELECT plan_json FROM plan_snapshots WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        if not row or not row.get("plan_json"):
            return []
        pj = row["plan_json"]
        if isinstance(pj, str):
            try:
                pj = json.loads(pj)
            except (json.JSONDecodeError, TypeError):
                return []
        return pj.get("items", [])
    except Exception as e:
        logger.debug("回退快照读取失败: %s", e)
        return []


def _consume_brief_summary(user_id: str, on_date: date) -> dict:
    """消费秘书 daily_brief"""
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        try:
            row = db.fetchone(
                """SELECT summary, payload FROM daily_briefs
                   WHERE user_id=%s AND DATE(created_at)=%s
                   ORDER BY created_at DESC LIMIT 1""",
                (user_id, on_date),
            )
            if row:
                payload = row.get("payload")
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = {}
                return {
                    "summary": row.get("summary", ""),
                    "payload": payload or {},
                }
        except Exception:
            pass
    except Exception as e:
        logger.debug("daily_brief 消费失败: %s", e)
    return {"summary": "", "payload": {}}


# ──────────────────────────────────────────────
# 计划项 CRUD
# ──────────────────────────────────────────────


def list_plan_items(
    user_id: str,
    plan_date: Optional[date] = None,
    status: Optional[str] = None,
    source_module: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    conds = ["user_id=%s"]
    params: list = [user_id]
    if plan_date is not None:
        conds.append("plan_date=%s")
        params.append(plan_date)
    if status:
        conds.append("status=%s")
        params.append(status)
    if source_module:
        conds.append("source_module=%s")
        params.append(source_module)
    sql = (
        f"SELECT * FROM plan_items WHERE {' AND '.join(conds)} "
        f"ORDER BY COALESCE(scheduled_for, '9999-12-31'::timestamptz), priority DESC, created_at DESC "
        f"LIMIT %s"
    )
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_plan_item(r) for r in rows]


def get_plan_item(user_id: str, plan_item_id: str) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_items WHERE id=%s AND user_id=%s",
        (plan_item_id, user_id),
    )
    return _row_to_plan_item(row) if row else None


def create_plan_item(user_id: str, body: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    pid = f"plan_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    plan_date = body.get("plan_date")
    if plan_date is None and body.get("scheduled_for"):
        plan_date = body["scheduled_for"].date() if isinstance(body["scheduled_for"], datetime) else None
    if isinstance(plan_date, str):
        try:
            plan_date = date.fromisoformat(plan_date)
        except ValueError:
            plan_date = None
    metadata = body.get("metadata", {})
    db.execute(
        """INSERT INTO plan_items
           (id, user_id, source_module, target_type, target_ref_id, title, description,
            estimated_minutes, linked_node_ids, priority, status, scheduled_for, plan_date, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', %s, %s, %s::jsonb)""",
        (
            pid, user_id,
            body["source_module"], body["target_type"], body["target_ref_id"],
            body["title"], body.get("description", ""),
            body.get("estimated_minutes", 0),
            json.dumps(body.get("linked_node_ids", []), ensure_ascii=False),
            body.get("priority", 0),
            body.get("scheduled_for"),
            plan_date,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    # 发布 PlanItemCreated 事件
    publish_event_safe(PlanItemCreated(
        user_id=user_id,
        plan_item_id=pid,
        source_module=body["source_module"],
        target_type=body["target_type"],
        target_ref_id=body["target_ref_id"],
        title=body["title"],
    ))

    return get_plan_item(user_id, pid)  # type: ignore[return-value]


def find_plan_item_by_request_id(user_id: str, request_id: str) -> dict | None:
    """按秘书请求 ID 查询已创建的计划项（幂等去重用）"""
    if not request_id:
        return None
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        row = db.fetchone(
            "SELECT * FROM plan_items WHERE user_id = %s AND metadata->>'request_id' = %s LIMIT 1",
            (user_id, request_id),
        )
    except Exception as e:
        logger.debug("按 request_id 查询 plan_item 失败: %s", e)
        return None
    return _row_to_plan_item(row) if row else None


def update_plan_item(user_id: str, plan_item_id: str, body: dict) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    sets: list[str] = []
    params: list = []
    for k in ("title", "description", "estimated_minutes", "priority", "status",
              "scheduled_for", "plan_date", "started_at", "skipped_at", "completed_at"):
        v = body.get(k)
        if v is None:
            continue
        sets.append(f"{k}=%s")
        params.append(v)
    if not sets:
        return get_plan_item(user_id, plan_item_id)
    sets.append("updated_at=NOW()")
    params.extend([plan_item_id, user_id])
    db.execute(
        f"UPDATE plan_items SET {', '.join(sets)} WHERE id=%s AND user_id=%s",
        tuple(params),
    )
    return get_plan_item(user_id, plan_item_id)


def start_plan_item(user_id: str, plan_item_id: str) -> Optional[dict]:
    """标记开始：status=in_progress, started_at=NOW()

    路由层先调用本方法更新 plan_items 状态（source of truth），
    再发布 PlanItemStarted 事件供其他模块订阅。
    """
    _ensure_tables()
    return update_plan_item(user_id, plan_item_id, {
        "status": "in_progress",
        "started_at": datetime.now(),
    })


def skip_plan_item(user_id: str, plan_item_id: str) -> Optional[dict]:
    """标记跳过：status=skipped, skipped_at=NOW()

    路由层先调用本方法更新 plan_items 状态（source of truth），
    再发布 PlanItemSkipped 事件供其他模块订阅。
    """
    _ensure_tables()
    return update_plan_item(user_id, plan_item_id, {
        "status": "skipped",
        "skipped_at": datetime.now(),
    })


def extend_plan_item(user_id: str, plan_item_id: str, extra_minutes: int) -> Optional[dict]:
    """延长：estimated_minutes += extra, status=extended

    路由层先调用本方法更新 plan_items 状态（source of truth），
    再发布 PlanItemExtended 事件供其他模块订阅。
    """
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    db.execute(
        """UPDATE plan_items
           SET estimated_minutes = COALESCE(estimated_minutes, 0) + %s,
               status = 'extended',
               updated_at = NOW()
           WHERE id = %s AND user_id = %s""",
        (extra_minutes, plan_item_id, user_id),
    )
    return get_plan_item(user_id, plan_item_id)


def complete_plan_item(user_id: str, plan_item_id: str, body: dict) -> dict:
    """标记完成：写入 plan_items + 写偏差 + 发布 PlanItemCompleted（由 completion_writer 路由回写）"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_items WHERE id=%s AND user_id=%s",
        (plan_item_id, user_id),
    )
    if not row:
        raise ValueError("plan_item not found")

    actual_minutes = int(body.get("actual_minutes") or 0)
    now = datetime.now()
    planned_minutes = row.get("estimated_minutes") or 0

    # 1) 更新 plan_items
    db.execute(
        """UPDATE plan_items SET status='completed', completed_at=%s,
           actual_minutes=%s, updated_at=NOW() WHERE id=%s""",
        (now, actual_minutes, plan_item_id),
    )

    # 2) 写偏差记录
    deviation_minutes = (actual_minutes or 0) - (planned_minutes or 0)
    dev_type = "timeout" if deviation_minutes > 0 else "early_complete" if deviation_minutes < 0 else "timeout"
    try:
        db.execute(
            """INSERT INTO plan_deviations
               (id, plan_item_id, user_id, deviation_type, planned_minutes, actual_minutes, deviation_minutes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (f"dev_{plan_item_id}_{int(now.timestamp())}", plan_item_id, user_id,
             dev_type, planned_minutes, actual_minutes, deviation_minutes),
        )
    except Exception as e:
        logger.debug("plan_deviations 写入失败: %s", e)

    # 3) 发布 PlanItemCompleted 事件（由 completion_writer 路由回写）
    linked = row.get("linked_node_ids") or []
    if isinstance(linked, str):
        try:
            linked = json.loads(linked)
        except (json.JSONDecodeError, TypeError):
            linked = []
    publish_event_safe(PlanItemCompleted(
        user_id=user_id,
        plan_item_id=plan_item_id,
        source_module=row.get("source_module", PlanningSourceModule.MANUAL.value),
        target_type=row.get("target_type", ""),
        target_ref_id=row.get("target_ref_id", ""),
        actual_minutes=actual_minutes,
        linked_node_ids=linked or [],
        completed_at=now,
    ))

    return get_plan_item(user_id, plan_item_id)  # type: ignore[return-value]


def delete_plan_item(user_id: str, plan_item_id: str) -> bool:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone("SELECT id FROM plan_items WHERE id=%s AND user_id=%s", (plan_item_id, user_id))
    if not row:
        return False
    db.execute("DELETE FROM plan_items WHERE id=%s", (plan_item_id,))
    return True


# ──────────────────────────────────────────────
# 视图聚合
# ──────────────────────────────────────────────


def build_daily_view(user_id: str, on_date: date) -> dict:
    """日视图：时间轴 + 待安排池 + 自适应推荐 + 日总结"""
    items = list_plan_items(user_id, plan_date=on_date)
    # 拆分时间轴 vs 待安排池
    timeline: list[dict] = []
    pool: list[dict] = []
    for it in items:
        if it["status"] in ("scheduled", "in_progress", "completed", "extended") and it.get("scheduled_for"):
            timeline.append(it)
        else:
            pool.append(it)
    # 待安排池补充：来自其他模块的待办（best-effort）
    pool.extend(_collect_pool_from_modules(user_id, on_date, exclude_ids=[x["id"] for x in items]))
    # 自适应推荐
    recs = _consume_adaptive_recommendations(user_id)
    # 日总结
    brief = _consume_brief_summary(user_id, on_date)
    # 顶部状态条
    status_bar = _consume_status_bar(user_id)
    return {
        "date": on_date,
        "status_bar": status_bar,
        "timeline_items": timeline,
        "pending_pool": pool,
        "adaptive_recommendations": recs,
        "brief_summary": brief,
    }


def _collect_pool_from_modules(user_id: str, on_date: date, exclude_ids: list[str]) -> list[dict]:
    """汇聚来自其他模块的待办（best-effort）

    数据源：
    - project_nodes 中 status='active' 的项
    - practice_sessions 今日进行中
    - reading 列表
    - language_room 练习目标
    """
    out: list[dict] = []
    excluded = set(exclude_ids or [])
    from app.infrastructure.db.database import get_db
    db = get_db()
    # 项目节点（best-effort）
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
        "summary": _consume_status_bar(user_id),
    }


def build_knowledge_view(user_id: str, selected_node_id: Optional[str] = None) -> dict:
    """知识视图：知识点 + 待办密度"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    # 节点 + 待办密度
    nodes: list[dict] = []
    try:
        rows = db.fetchall(
            """SELECT id, label, level, parent, deleted_at
               FROM knowledge_nodes
               WHERE user_id=%s AND deleted_at IS NULL
               ORDER BY level NULLS LAST, id LIMIT 200""",
            (user_id,),
        )
        # 每个节点聚合待办
        for r in rows:
            nid = r["id"]
            # 关联的 plan_items 数
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
        selected_todos = [_row_to_plan_item(r) for r in rows]
    return {
        "nodes": nodes,
        "selected_node_id": selected_node_id,
        "selected_node_todos": selected_todos,
    }


# ──────────────────────────────────────────────
# 目标 / 周期回顾
# ──────────────────────────────────────────────


def list_goals(user_id: str, status: Optional[str] = None) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    conds = ["user_id=%s"]
    params: list = [user_id]
    if status:
        conds.append("status=%s")
        params.append(status)
    rows = db.fetchall(
        f"SELECT * FROM plan_goals WHERE {' AND '.join(conds)} ORDER BY deadline ASC NULLS LAST",
        tuple(params),
    )
    return [_row_to_goal(r) for r in rows]


def create_goal(user_id: str, body: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    gid = f"plangoal_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    db.execute(
        """INSERT INTO plan_goals
           (id, user_id, title, description, target_module, target_metric, target_value, deadline)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            gid, user_id,
            body["title"], body.get("description", ""),
            body["target_module"], body["target_metric"], body["target_value"],
            body.get("deadline"),
        ),
    )
    # 发布 PlanGoalCreated
    publish_event_safe(PlanGoalCreated(
        user_id=user_id,
        goal_id=gid,
        title=body["title"],
        target_module=body["target_module"],
        target_metric=body["target_metric"],
        target_value=body["target_value"],
        deadline=str(body.get("deadline") or ""),
    ))
    return list_goals(user_id)[0] if False else get_goal(user_id, gid)  # type: ignore[return-value]


def get_goal(user_id: str, goal_id: str) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM plan_goals WHERE id=%s AND user_id=%s",
        (goal_id, user_id),
    )
    return _row_to_goal(row) if row else None


def update_goal(user_id: str, goal_id: str, body: dict) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    sets: list[str] = []
    params: list = []
    for k in ("title", "description", "target_value", "current_value", "deadline", "status"):
        v = body.get(k)
        if v is None:
            continue
        sets.append(f"{k}=%s")
        params.append(v)
    if not sets:
        return get_goal(user_id, goal_id)
    sets.append("updated_at=NOW()")
    params.extend([goal_id, user_id])
    db.execute(
        f"UPDATE plan_goals SET {', '.join(sets)} WHERE id=%s AND user_id=%s",
        tuple(params),
    )
    return get_goal(user_id, goal_id)


def list_reviews(user_id: str, limit: int = 20) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM plan_periodic_reviews WHERE user_id=%s ORDER BY period_start DESC LIMIT %s",
        (user_id, limit),
    )
    return [_row_to_review(r) for r in rows]


def generate_review(user_id: str, body: dict) -> dict:
    """生成周期回顾（聚合 plan_items / brief / goal 数据）"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rid = f"review_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    period_type = body["period_type"]
    period_start = body["period_start"]
    period_end = body["period_end"]
    # 汇总数据
    items_count = db.fetchone(
        """SELECT COUNT(*) as c, SUM(estimated_minutes) as m, SUM(actual_minutes) as am
           FROM plan_items
           WHERE user_id=%s AND plan_date BETWEEN %s AND %s""",
        (user_id, period_start, period_end),
    )
    completed_count = db.fetchone(
        """SELECT COUNT(*) as c FROM plan_items
           WHERE user_id=%s AND plan_date BETWEEN %s AND %s AND status='completed'""",
        (user_id, period_start, period_end),
    )
    by_module = db.fetchall(
        """SELECT source_module, COUNT(*) as c, SUM(actual_minutes) as m
           FROM plan_items
           WHERE user_id=%s AND plan_date BETWEEN %s AND %s
           GROUP BY source_module""",
        (user_id, period_start, period_end),
    )
    summary = {
        "items_total": items_count["c"] if items_count else 0,
        "items_completed": completed_count["c"] if completed_count else 0,
        "estimated_minutes": items_count["m"] if items_count else 0,
        "actual_minutes": items_count["am"] if items_count else 0,
        "by_module": [
            {"source_module": r["source_module"], "count": r["c"], "minutes": r["m"] or 0}
            for r in by_module
        ],
    }
    db.execute(
        """INSERT INTO plan_periodic_reviews
           (id, user_id, period_type, period_start, period_end, summary_data, user_note)
           VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)""",
        (rid, user_id, period_type, period_start, period_end,
         json.dumps(summary, ensure_ascii=False), body.get("user_note", "")),
    )
    # 发布事件
    publish_event_safe(PlanPeriodicReviewGenerated(
        user_id=user_id,
        review_id=rid,
        period_type=period_type,
        period_start=str(period_start),
        period_end=str(period_end),
        summary_data=summary,
    ))
    row = db.fetchone("SELECT * FROM plan_periodic_reviews WHERE id=%s", (rid,))
    return _row_to_review(row) if row else {"id": rid, "summary_data": summary}


# ──────────────────────────────────────────────
# 视图方案
# ──────────────────────────────────────────────


def list_view_layouts(user_id: str) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM plan_view_layouts WHERE user_id=%s ORDER BY is_default DESC, created_at DESC",
        (user_id,),
    )
    return [_row_to_view_layout(r) for r in rows]


def create_view_layout(user_id: str, body: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    lid = f"vlayout_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{user_id}"
    if body.get("is_default"):
        # 取消其它默认
        db.execute(
            "UPDATE plan_view_layouts SET is_default=FALSE WHERE user_id=%s",
            (user_id,),
        )
    db.execute(
        """INSERT INTO plan_view_layouts
           (id, user_id, name, view_type, filters, layout, is_default)
           VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)""",
        (
            lid, user_id, body["name"], body["view_type"],
            json.dumps(body.get("filters") or {}, ensure_ascii=False),
            json.dumps(body.get("layout") or {}, ensure_ascii=False),
            body.get("is_default", False),
        ),
    )
    row = db.fetchone("SELECT * FROM plan_view_layouts WHERE id=%s", (lid,))
    return _row_to_view_layout(row) if row else {"id": lid}
