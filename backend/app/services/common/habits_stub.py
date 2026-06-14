"""习惯养成桩 — 原 domain/habits/service.py"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from shared.events import AnswerSubmitted

logger = logging.getLogger(__name__)


class HabitsStub:
    def __init__(self):
        self._daily_stats: dict[str, dict[str, int]] = {}

    async def on_answer_submitted(self, event: AnswerSubmitted) -> None:
        from app.services.analytics.habit_formation import habit_formation as hf

        user = event.user_id
        today = datetime.now().strftime("%Y-%m-%d")
        if user not in self._daily_stats:
            self._daily_stats[user] = {"date": today, "questions": 0, "correct": 0}
        if self._daily_stats[user]["date"] != today:
            self._daily_stats[user] = {"date": today, "questions": 0, "correct": 0}
        self._daily_stats[user]["questions"] += 1
        if event.is_correct:
            self._daily_stats[user]["correct"] += 1

    async def check_daily_goal(self, user_id: str) -> dict[str, Any]:
        from app.services.analytics.habit_formation import habit_formation as hf
        from app.infrastructure.db.database import get_db

        db = get_db()
        today = datetime.now().strftime("%Y-%m-%d")
        attempts = db.fetchall(
            "SELECT * FROM practice_attempts WHERE user_id = %s AND created_at >= %s",
            (user_id, today),
        )
        today_q = len(attempts)
        today_c = sum(1 for a in attempts if a.get("is_correct"))

        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        session_rows = db.fetchall(
            "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
            (user_id, cutoff),
        )
        study_days = len(set(
            r["started_at"].isoformat()[:10] for r in session_rows if r.get("started_at")
        ))
        stat_rows = db.fetchall(
            "SELECT * FROM practice_sessions WHERE user_id = %s",
            (user_id,),
        )
        total_q = len(db.fetchall(
            "SELECT * FROM practice_attempts WHERE user_id = %s", (user_id,)
        ))

        goal = hf.check_daily_goal(
            today_questions=today_q,
            today_correct=today_c,
            today_accuracy=today_c / max(today_q, 1),
            current_streak=0,
            total_questions=total_q,
            study_days=study_days,
        )
        return goal.to_dict()

    async def get_pomodoro_suggestion(self, user_id: str) -> dict[str, Any]:
        from app.services.analytics.habit_formation import habit_formation as hf
        return hf.get_pomodoro_recommendation(fatigue_minute=None)

    async def get_tiny_habits(self, user_id: str) -> list[dict[str, Any]]:
        from app.services.analytics.habit_formation import habit_formation as hf
        return [h.to_dict() for h in hf.get_tiny_habits(current_streak=0)]
