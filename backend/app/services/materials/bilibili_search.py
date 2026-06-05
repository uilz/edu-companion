"""
Bilibili 视频搜索 API

使用 Bilibili 公开搜索 API，无需 token。
搜索教学/讲解类内容。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def search_bilibili(
    query: str,
    page: int = 1,
    page_size: int = 10,
    duration: Optional[str] = None,  # 0=全部 1=短(<10min) 2=中(10-30min) 3=长(>30min)
    order: str = "totalrank",  # totalrank=综合, click=播放, pubdate=最新, dm=弹幕
) -> dict:
    """
    搜索 Bilibili 视频。

    返回:
        { results: [...], total: N }
        每条 result: { bvid, title, author, cover, link, duration, played, danmaku, description }
    """
    import httpx
    import re

    if not query or not query.strip():
        return {"results": [], "total": 0, "error": "搜索词不能为空"}

    params = {
        "search_type": "video",
        "keyword": query.strip(),
        "page": page,
        "page_size": min(page_size, 30),
        "order": order,
    }
    if duration:
        params["duration"] = duration

    url = "https://api.bilibili.com/x/web-interface/search/type"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com/",
            })
            data = resp.json()

        if data.get("code") != 0:
            logger.warning("Bilibili API 返回错误: %s", data.get("message", "unknown"))
            return {"results": [], "total": 0, "error": data.get("message", "搜索失败")}

        videos = data.get("data", {}).get("result", [])
        results = []
        for v in videos[:page_size]:
            bvid = v.get("bvid", "")
            results.append({
                "bvid": bvid,
                "title": _clean_title(v.get("title", "")),
                "author": v.get("author", ""),
                "cover": v.get("pic", ""),
                "link": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
                "duration": v.get("duration", ""),
                "played": _format_play_count(v.get("play", 0)),
                "danmaku": v.get("video_review", 0),
                "description": v.get("description", ""),
            })

        total = data.get("data", {}).get("numResults", 0)
        logger.info("Bilibili 搜索: q=%s, results=%d", query, len(results))
        return {"results": results, "total": total}

    except httpx.TimeoutException:
        logger.warning("Bilibili API 超时: q=%s", query)
        return {"results": [], "total": 0, "error": "搜索超时，请稍后重试"}
    except Exception as e:
        logger.error("Bilibili 搜索异常: %s", e)
        return {"results": [], "total": 0, "error": f"搜索异常: {str(e)[:50]}"}


def _clean_title(raw: str) -> str:
    """清除标题中的 HTML 标签"""
    import re
    text = re.sub(r"<[^>]+>", "", raw)
    return text.strip()


def _format_play_count(count) -> str:
    """格式化播放量"""
    try:
        n = int(count)
        if n >= 10000:
            return f"{n / 10000:.1f}万"
        if n >= 1000:
            return f"{n / 1000:.1f}千"
        return str(n)
    except (ValueError, TypeError):
        return str(count)
