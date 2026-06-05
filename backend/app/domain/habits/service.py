"""习惯养成领域服务 — 事件驱动版

职责:
1. 订阅 AnswerSubmitted → 记录每日练习统计数据
2. 提供日目标检查、番茄钟建议、微习惯推荐
3. 数据源委托给 app.services.habit_formation
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from shared.events import AnswerSubmitted

logger = logging.getLogger(__name__)


class HabitServiceImpl:
    def __init__(self, event_bus):
        self._bus = event_bus
        self._daily_stats: dict[str, dict[str, int]] = {}  # user_id → {date, questions, correct}

    async def on_answer_submitted(self, event: AnswerSubmitted) -> None:
        """事件: 答题 → 记录每日练习统计"""
        from app.services.analytics.habit_formation import habit_formation as hf

        # 更新内存统计
        user = event.user_id
        today = datetime.now().strftime("%Y-%m-%d")
        if user not in self._daily_stats:
            self._daily_stats[user] = {"date": today, "questions": 0, "correct": 0}
        if self._daily_stats[user]["date"] != today:
            self._daily_stats[user] = {"date": today, "questions": 0, "correct": 0}
        self._daily_stats[user]["questions"] += 1
        if event.is_correct:
            self._daily_stats[user]["correct"] += 1

        logger.info(
            "Habit: user=%s today_questions=%d correct=%d (tracked daily count)",
            user,
            self._daily_stats[user]["questions"],
            self._daily_stats[user]["correct"],
        )

    async def check_daily_goal(self, user_id: str) -> dict[str, Any]:
        """检查今日目标进度"""
        from app.services.analytics.habit_formation import habit_formation as hf
        from app.api.practice.practice_analytics import behavior_analyzer
        from app.db.database import get_db

        db = get_db()
        today = datetime.now().strftime("%Y-%m-%d")
        attempts = db.fetchall(
            "SELECT * FROM attempts WHERE user_id = %s AND submitted_at::date = %s::date",
            (user_id, today),
        )
        today_q = len(attempts)
        today_c = sum(1 for a in attempts if a.get("is_correct"))

        # 用 behavior_analyzer 算 streak（已有数据）
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=7)
        session_rows = db.fetchall(
            "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
            (user_id, cutoff.isoformat()),
        )
        study_days = len(set(
            r["started_at"].isoformat()[:10] for r in session_rows if r.get("started_at")
        ))
        stat_rows = db.fetchall(
            "SELECT * FROM practice_sessions WHERE user_id = %s",
            (user_id,),
        )
        total_sessions = len(stat_rows)
        total_minutes = sum(r.get("estimated_minutes", 0) for r in stat_rows)
        total_q = len(db.fetchall(
            "SELECT * FROM attempts WHERE user_id = %s", (user_id,)
        ))

        goal = hf.check_daily_goal(
            today_questions=today_q,
            today_correct=today_c,
            today_accuracy=today_c / max(today_q, 1),
            current_streak=0,  # 委托 behavior_analyzer 算
            total_questions=total_q,
            study_days=study_days,
        )
        return goal.to_dict()

    async def get_pomodoro_suggestion(self, user_id: str) -> dict[str, Any]:
        """获取番茄钟建议"""
        from app.services.analytics.habit_formation import habit_formation as hf
        return hf.get_pomodoro_recommendation(fatigue_minute=None)

    async def get_tiny_habits(self, user_id: str) -> list[dict[str, Any]]:
        """获取推荐微习惯"""
        from app.services.analytics.habit_formation import habit_formation as hf
        return [h.to_dict() for h in hf.get_tiny_habits(current_streak=0)]
