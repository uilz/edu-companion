"""
Media Search Service Protocol — 媒体搜索模块对外契约
"""

from __future__ import annotations

from typing import Protocol


class MediaService(Protocol):
    """媒体搜索模块对外契约"""

    async def search(
        self,
        query: str,
        platforms: list[str] | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """多平台搜索（B站/百度/Bing/小红书）"""
        ...

    async def get_video_recommendation(
        self,
        skill_id: str,
        error_type: str | None = None,
    ) -> list[dict]:
        """根据错题推荐视频"""
        ...
