"""媒体搜索领域服务 — 日志增强版"""

import logging

logger = logging.getLogger(__name__)


class MediaServiceImpl:
    async def search(self, query, platforms=None):
        return {}

    async def recommend_for_error(self, skill_id, error_type):
        return []

    async def on_error_recorded(self, event):
        """事件: 错题 → 推荐相关视频"""
        logger.info(
            "Media: error recorded user=%s skill=%s type=%s",
            getattr(event, "user_id", "?"),
            getattr(event, "skill_id", "?"),
            getattr(event, "error_type", "?"),
        )
