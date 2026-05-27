"""知识图谱领域服务 — 日志增强版"""

import logging

logger = logging.getLogger(__name__)


class KnowledgeGraphServiceImpl:
    def __init__(self, practice, event_bus):
        self._practice = practice
        self._bus = event_bus

    async def on_answer_submitted(self, event):
        """事件: 答题 → 图谱掌握度（由 CognitiveNode 实际处理）"""
        logger.info(
            "Knowledge: user=%s skill=%s correct=%s (tracked via CognitiveNode)",
            getattr(event, "user_id", "?"),
            getattr(event, "skill_id", "?"),
            getattr(event, "is_correct", "?"),
        )

    async def on_error_recorded(self, event):
        """事件: 错题 → 标记薄弱知识点"""
        logger.info(
            "Knowledge: error recorded user=%s skill=%s type=%s",
            getattr(event, "user_id", "?"),
            getattr(event, "skill_id", "?"),
            getattr(event, "error_type", "?"),
        )

    async def get_graph(self, user_id):
        return {}

    async def can_practice(self, user_id, skill_id):
        return True, None

    async def find_learning_path(self, user_id, target_skill):
        return []
