"""学习规划领域服务 — 日志增强版"""

import logging

logger = logging.getLogger(__name__)


class PlanningServiceImpl:
    def __init__(self, practice, event_bus):
        self._practice = practice
        self._bus = event_bus

    async def generate_plan(self, user_id):
        return {}

    async def on_answer_submitted(self, event):
        """事件: 答题 → 更新计划进度"""
        logger.info(
            "Planning: answer submitted user=%s skill=%s correct=%s",
            getattr(event, "user_id", "?"),
            getattr(event, "skill_id", "?"),
            getattr(event, "is_correct", "?"),
        )

    async def on_session_completed(self, event):
        """事件: 会话完成 → 触发计划重新生成"""
        user_id = getattr(event, "user_id", "?")
        session_id = getattr(event, "session_id", "?")

        logger.info(
            "Planning: session completed user=%s session=%s — triggering plan regeneration",
            user_id, session_id,
        )

        # Trigger plan regeneration asynchronously to avoid blocking
        try:
            import asyncio
            asyncio.create_task(self.generate_plan(user_id))
        except Exception as exc:
            logger.warning("Planning: failed to schedule plan regeneration: %s", exc)

    async def on_knowledge_updated(self, event):
        """事件: 知识升级 → 重生成学习计划"""
        logger.info(
            "Planning: knowledge updated user=%s skill=%s %s→%s",
            getattr(event, "user_id", "?"),
            getattr(event, "skill_id", "?"),
            getattr(event, "old_mastery", "?"),
            getattr(event, "new_mastery", "?"),
        )
        if getattr(event, "new_mastery", "") == "已掌握":
            await self.generate_plan(event.user_id)
