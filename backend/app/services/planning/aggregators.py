"""Planning 后端引擎聚合器 — 消费已有服务，不做调度决策"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def consume_status_bar(user_id: str) -> dict:
    """聚合顶部状态条：疲劳/压力/能量/习惯/番茄钟

    所有数据**消费**自秘书系统 + habit_formation + 0005 mood/stress，
    本函数不实现任何检测逻辑。
    """
    habit_level = "beginner"
    pomodoro = {"work_minutes": 25, "break_minutes": 5, "message": "建议标准番茄钟 25+5"}
    try:
        from app.services.analytics.habit_formation import habit_formation
        from app.infrastructure.db.database import get_db
        db = get_db()
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

    pressure_score = None
    energy_score = None
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
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


def consume_adaptive_recommendations(user_id: str) -> list[dict]:
    """消费 AdaptivePlanGenerator.generate()"""
    try:
        from app.services.analytics.adaptive_planner import adaptive_planner
        import asyncio
        try:
            asyncio.get_running_loop()
            return _fallback_recommendations(user_id)
        except RuntimeError:
            pass
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


def consume_brief_summary(user_id: str, on_date: date) -> dict:
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
