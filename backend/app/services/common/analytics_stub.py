"""行为分析桩 — 原 domain/analytics/service.py"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from shared.events import AnswerSubmitted

logger = logging.getLogger(__name__)


class AnalyticsStub:
    def __init__(self):
        self._daily_stats: dict[tuple[str, str], dict[str, Any]] = {}

    async def on_answer_submitted(self, event: AnswerSubmitted) -> None:
        logger.debug(
            "Analytics: user=%s skill=%s correct=%s",
            event.user_id, event.skill_id, event.is_correct,
        )
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
        stats["total_time_spent"] += getattr(event, "response_time_seconds", 0.0)

    async def _gather_daily_data(self, user_id: str, days: int = 7) -> dict[str, Any]:
        from app.infrastructure.db.database import get_db
        db = get_db()
        now = datetime.now()
        cutoff = (now - timedelta(days=days)).isoformat()

        attempt_rows = db.fetchall(
            "SELECT * FROM practice_attempts WHERE user_id = %s AND created_at >= %s",
            (user_id, cutoff),
        )
        session_rows = db.fetchall(
            "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
            (user_id, cutoff),
        )

        daily_trend = []
        for i in range(days - 1, -1, -1):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_a = [a for a in attempt_rows if str(a.get("created_at", ""))[:10] == day]
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
                    if a.get("created_at")
                    and isinstance(a["created_at"], datetime) and a["created_at"].weekday() == day_idx
                    and isinstance(a["created_at"], datetime) and a["created_at"].hour == hour
                )
                hourly_heatmap.append({
                    "day": day_idx + 1, "day_name": day_names[day_idx],
                    "hour": hour, "questions": count,
                })

        try:
            from app.domain.cognitive import get_repo
            atoms = get_repo().get_nodes_by_level("atom", user_id) or []
            mastery_bars = [
                {"skill_id": n.id, "p_known": round(n.belief.proficiency_mean, 2)}
                for n in atoms if n.belief and n.belief.proficiency_mean is not None
            ]
        except Exception:
            mastery_bars = []

        return {
            "daily_trend": daily_trend,
            "hourly_heatmap": hourly_heatmap,
            "mastery_bars": mastery_bars,
            "total_sessions": len(session_rows),
            "total_minutes": sum(r.get("estimated_minutes", 0) or r.get("duration_seconds", 0) // 60 for r in session_rows),
        }

    async def compute_streak(self, user_id: str) -> tuple[int, int]:
        from app.services.analytics.behavior_analyzer import behavior_analyzer
        data = await self._gather_daily_data(user_id)
        report = behavior_analyzer.analyze(**data)
        return report.current_streak, report.longest_streak

    async def find_best_hours(self, user_id: str) -> list[int]:
        from app.services.analytics.behavior_analyzer import behavior_analyzer
        data = await self._gather_daily_data(user_id)
        report = behavior_analyzer.analyze(**data)
        return report.best_study_hours or []

    async def compute_regularity(self, user_id: str) -> float:
        from app.services.analytics.behavior_analyzer import behavior_analyzer
        data = await self._gather_daily_data(user_id)
        report = behavior_analyzer.analyze(**data)
        return report.regularity_score
