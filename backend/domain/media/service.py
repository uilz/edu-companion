"""媒体搜索领域服务 — 日志增强版"""

import logging

logger = logging.getLogger(__name__)


class MediaServiceImpl:
    async def search(self, query, platforms=None):
        return {}

    async def recommend_for_error(self, skill_id, error_type):
        return []

    async def on_error_recorded(self, event):
        """事件: 错误 → 推荐相关视频（placeholder for future video recommendation）"""
        user_id = getattr(event, "user_id", "?")
        skill_id = getattr(event, "skill_id", "?")
        error_type = getattr(event, "error_type", "unknown")

        logger.info(
            "Media: error recorded user=%s skill=%s type=%s",
            user_id, skill_id, error_type,
        )

        # Placeholder: log media recommendation suggestion for future video matching
        logger.info(
            "MEDIA: Would recommend video for skill %s, error_type %s",
            skill_id, error_type,
        )
