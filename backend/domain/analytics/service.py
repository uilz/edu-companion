"""分析引擎领域服务 — 行为分析事件驱动版

职责:
1. 订阅 AnswerSubmitted → 更新统计（委托 app.services.behavior_analyzer）
2. 暴露 compute_streak / find_best_hours / compute_regularity
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from shared.events import AnswerSubmitted

logger = logging.getLogger("domain.analytics")


class AnalyticsServiceImpl:
    """行为分析服务"""

    def __init__(self, practice, event_bus):
        self._practice = practice
        self._bus = event_bus
        # In-memory daily behavior counters keyed by (user_id, date_str)
        self._daily_stats: dict[tuple[str, str], dict[str, Any]] = {}

    async def on_answer_submitted(self, event: AnswerSubmitted) -> None:
        """事件处理器: 答题提交 → 更新统计 + 追加内部行为计数"""
        from app.services.behavior_analyzer import behavior_analyzer

        logger.debug(
            "Analytics: user=%s skill=%s correct=%s",
            event.user_id, event.skill_id, event.is_correct,
        )
        # 更新内部行为计数器（daily answer count, accuracy, session duration）
        today = datetime.now().strftime("%Y-%m-%d")
        key = (event.user_id, today)
        stats = self._daily_stats.setdefault(key, {
            "answer_count": 0,
            "correct_count": 0,
            "total_time_spent": 0.0,
        })
        stats["answer_count"] += 1
        if event.is_correct:
            stats["correct_count"] += 1
        stats["total_time_spent"] += event.time_spent

        logger.info(
            "Analytics: daily counters user=%s date=%s count=%d correct=%d time=%.1fs",
            event.user_id, today, stats["answer_count"],
            stats["correct_count"], stats["total_time_spent"],
        )

    async def _gather_daily_data(self, user_id: str, days: int = 7) -> dict[str, Any]:
        """从 DB 聚合统计数据供 behavior_analyzer 使用"""
        from app.db.database import get_db
        from app.core.knowledge_trace import get_all_cognitive_states

        db = get_db()
        now = datetime.now()
        cutoff = (now - timedelta(days=days)).isoformat()

        attempt_rows = db.fetchall(
            "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
            (user_id, cutoff),
        )
        session_rows = db.fetchall(
            "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
            (user_id, cutoff),
        )

        daily_trend = []
        for i in range(days - 1, -1, -1):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_a = [a for a in attempt_rows if self._ds(a.get("submitted_at"))[:10] == day]
            daily_trend.append({
                "date": day[-5:],
                "questions": len(day_a),
                "correct": sum(1 for a in day_a if a.get("is_correct")),
                "accuracy": sum(1 for a in day_a if a.get("is_correct")) / max(len(day_a), 1),
            })

        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        hourly_heatmap = []
        for day_idx in range(7):
            for hour in [8, 10, 14, 16, 20, 22]:
                count = sum(
                    1 for a in attempt_rows
                    if a.get("submitted_at")
                    and (isinstance(a["submitted_at"], str)
                         and datetime.fromisoformat(a["submitted_at"]) or a["submitted_at"])
                    .weekday() == day_idx
                    and (isinstance(a["submitted_at"], str)
                         and datetime.fromisoformat(a["submitted_at"]) or a["submitted_at"])
                    .hour == hour
                )
                hourly_heatmap.append({
                    "day": day_idx + 1, "day_name": day_names[day_idx],
                    "hour": hour, "questions": count,
                })

        skill_states = get_all_cognitive_states(user_id)
        mastery_bars = [
            {"skill_id": sid, "p_known": round(s.p_known, 2)}
            for sid, s in skill_states.items() if s.attempt_count > 0
        ]

        return {
            "daily_trend": daily_trend,
            "hourly_heatmap": hourly_heatmap,
            "mastery_bars": mastery_bars,
            "total_sessions": len(session_rows),
            "total_minutes": sum(r.get("estimated_minutes", 0) for r in session_rows),
        }

    async def compute_streak(self, user_id: str) -> tuple[int, int]:
        """计算连续学习天数"""
        from app.services.behavior_analyzer import behavior_analyzer

        data = await self._gather_daily_data(user_id)
        report = behavior_analyzer.analyze(**data)
        return report.current_streak, report.longest_streak

    async def find_best_hours(self, user_id: str) -> list[int]:
        """找最佳学习时段"""
        from app.services.behavior_analyzer import behavior_analyzer

        data = await self._gather_daily_data(user_id)
        report = behavior_analyzer.analyze(**data)
        return report.best_study_hours or []

    async def compute_regularity(self, user_id: str) -> float:
        """计算学习规律性 (0-1)"""
        from app.services.behavior_analyzer import behavior_analyzer

        data = await self._gather_daily_data(user_id)
        report = behavior_analyzer.analyze(**data)
        return report.regularity_score

    @staticmethod
    def _ds(v) -> str:
        if v is None:
            return ""
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, str):
            return v
        return str(v)
