"""学习规划桩 — 原 domain/planning/service.py"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PlanningStub:
    async def generate_plan(self, user_id):
        return {}

    async def get_daily_goal(self, user_id):
        return {}

    async def mark_task_complete(self, user_id, task_id):
        return {}

    async def get_plan_progress(self, user_id):
        return {}

    async def on_answer_submitted(self, event):
        logger.info(
            "Planning: answer submitted user=%s skill=%s correct=%s",
            getattr(event, "user_id", "?"),
            getattr(event, "skill_id", "?"),
            getattr(event, "is_correct", "?"),
        )

    async def on_session_completed(self, event):
        user_id = getattr(event, "user_id", "?")
        logger.info(
            "Planning: session completed user=%s — plan regeneration triggered",
            user_id,
        )
        try:
            import asyncio
            asyncio.create_task(self.generate_plan(user_id))
        except Exception as exc:
            logger.warning("Planning: failed to schedule plan regeneration: %s", exc)

    async def on_knowledge_updated(self, event):
        label = getattr(event, "label", "?") or getattr(event, "skill_id", "?")
        prof_after = getattr(event, "proficiency_after", 0)
        logger.info(
            "Planning: cognitive updated user=%s label=%s proficiency=%.3f",
            getattr(event, "user_id", "?"), label, prof_after,
        )
        if prof_after >= 0.95:
            await self.generate_plan(event.user_id)
