"""媒体搜索桩 — 原 domain/media/service.py"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MediaStub:
    PLATFORM_SEARCHERS = {"bilibili": "_search_bilibili"}
    DEFAULT_PLATFORMS = ["bilibili"]

    async def search(self, query: str, platforms: list[str] | None = None, page_size: int = 5) -> dict:
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
                    result[platform] = {"results": [], "total": 0, "error": str(e)[:100]}
            else:
                result[platform] = {"results": [], "total": 0, "error": f"未支持的平台: {platform}"}
        return result

    async def _search_bilibili(self, query: str, page_size: int = 5) -> dict:
        from app.infrastructure.media.bilibili_search import search_bilibili
        return await search_bilibili(
            query=f"{query} 教学", page=1, page_size=page_size,
            duration="2", order="totalrank",
        )

    async def recommend_for_error(self, skill_id: str, error_type: str, skill_name: str = "") -> list[dict]:
        query_parts = []
        if skill_name:
            query_parts.append(skill_name)
        error_modifiers = {"concept": "概念讲解", "calculation": "例题详解", "application": "综合应用"}
        modifier = error_modifiers.get(error_type, "讲解")
        query_parts.append(modifier)
        query = " ".join(query_parts) if query_parts else f"知识点{error_type}讲解"

        try:
            result = await self.search(query, page_size=3)
            bilibili_results = result.get("bilibili", {}).get("results", [])
            for item in bilibili_results:
                item["platform"] = "bilibili"
            return bilibili_results
        except Exception as e:
            logger.error("Media recommend failed: skill=%s error=%s", skill_id, e)
            return []

    async def on_error_recorded(self, event) -> None:
        skill_id = getattr(event, "skill_id", "?")
        error_type = getattr(event, "error_type", "unknown")
        skill_name = getattr(event, "skill_name", "") or ""
        try:
            videos = await self.recommend_for_error(
                skill_id=skill_id, error_type=error_type, skill_name=skill_name,
            )
            if videos:
                try:
                    event.media_recommendations = videos
                except Exception:
                    pass
        except Exception as e:
            logger.error("Media on_error_recorded failed: %s", e)
