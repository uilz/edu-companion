"""媒体搜索领域服务 — 接入 Bilibili + 多平台扩展

监听 ErrorRecorded 事件 → 自动推荐教学视频
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("media")


class MediaServiceImpl:
    """媒体搜索服务 — Bilibili 为主，预留多平台扩展"""

    # 平台配置：后续可扩展 YouTube、西瓜视频等
    PLATFORM_SEARCHERS = {
        "bilibili": "_search_bilibili",
    }
    DEFAULT_PLATFORMS = ["bilibili"]

    async def search(self, query: str, platforms: list[str] | None = None, page_size: int = 5) -> dict:
        """跨平台搜索教学视频

        Args:
            query: 搜索关键词
            platforms: 平台列表，默认 ['bilibili']，可扩展 ['bilibili', 'youtube', 'xigua']
            page_size: 每平台返回数量

        Returns:
            {platform: {results: [...], total: N}}
        """
        if not query or not query.strip():
            return {}

        platforms = platforms or self.DEFAULT_PLATFORMS
        result = {}

        for platform in platforms:
            method_name = self.PLATFORM_SEARCHERS.get(platform)
            if method_name:
                try:
                    method = getattr(self, method_name)
                    result[platform] = await method(query, page_size=page_size)
                except Exception as e:
                    logger.error("Media search failed for %s: %s", platform, e)
                    result[platform] = {"results": [], "total": 0, "error": str(e)[:100]}
            else:
                logger.warning("Unknown media platform: %s", platform)
                result[platform] = {"results": [], "total": 0, "error": f"未支持的平台: {platform}"}

        return result

    async def _search_bilibili(self, query: str, page_size: int = 5) -> dict:
        """Bilibili 视频搜索"""
        from app.services.materials.bilibili_search import search_bilibili
        return await search_bilibili(
            query=f"{query} 教学",
            page=1,
            page_size=page_size,
            duration="2",  # 中长视频 (10-30min) 更适合教学
            order="totalrank",
        )

    async def recommend_for_error(self, skill_id: str, error_type: str, skill_name: str = "") -> list[dict]:
        """根据错题推荐补救视频

        Args:
            skill_id: 知识点 ID
            error_type: 错误类型 (concept/calculation/application)
            skill_name: 知识点名称（用于搜索）

        Returns:
            [{bvid, title, author, cover, link, duration, played, platform: 'bilibili'}]
        """
        query_parts = []

        if skill_name:
            query_parts.append(skill_name)

        # 错误类型 → 搜索词增强
        error_modifiers = {
            "concept": "概念讲解",
            "calculation": "例题详解",
            "application": "综合应用",
        }
        modifier = error_modifiers.get(error_type, "讲解")
        query_parts.append(modifier)

        query = " ".join(query_parts) if query_parts else f"知识点{error_type}讲解"

        logger.info("Media recommend: skill=%s type=%s q=%s", skill_id, error_type, query)

        try:
            result = await self.search(query, page_size=3)
            bilibili_results = result.get("bilibili", {}).get("results", [])

            # 添加平台标记
            for item in bilibili_results:
                item["platform"] = "bilibili"

            logger.info(
                "Media recommend done: skill=%s found=%d",
                skill_id, len(bilibili_results),
            )
            return bilibili_results

        except Exception as e:
            logger.error("Media recommend failed: skill=%s error=%s", skill_id, e)
            return []

    async def on_error_recorded(self, event) -> None:
        """事件: 错题记录 → 异步搜索补救视频

        不再只记日志 — 真正搜索并记录结果到事件数据中，
        供前端错题详情页展示「推荐教学视频」。
        """
        user_id = getattr(event, "user_id", "?")
        skill_id = getattr(event, "skill_id", "?")
        error_type = getattr(event, "error_type", "unknown")
        skill_name = getattr(event, "skill_name", "") or ""

        logger.info(
            "Media: error recorded user=%s skill=%s type=%s → searching videos",
            user_id, skill_id, error_type,
        )

        try:
            videos = await self.recommend_for_error(
                skill_id=skill_id,
                error_type=error_type,
                skill_name=skill_name,
            )

            if videos:
                # 将推荐结果写回到事件对象上，让下游处理器可用
                # EventBus 是同步处理器，不影响错题主流程
                try:
                    event.media_recommendations = videos
                except Exception:
                    pass  # event 可能不可变，跳过

                logger.info(
                    "🎬 Media: recommended %d videos for skill=%s",
                    len(videos), skill_id,
                )
            else:
                logger.info("Media: no videos found for skill=%s", skill_id)

        except Exception as e:
            logger.error("Media on_error_recorded failed: skill=%s error=%s", skill_id, e)
