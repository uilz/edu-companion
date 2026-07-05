"""
InterestExplorer 信息源抓取器

按 docs/modules/interest-explorer/overview.md §5 + ADR 0007 实现:
- feedparser 解析 RSS/Atom
- httpx 异步 HTTP 客户端
- 4 种内置源 + 用户自定义 RSS/Atom + OPML 导入
- 严格不抓取任意 URL（决策 5）
- 抓取是定期调度，不通过事件总线（events.md §5）
- 抓取后写入 interest_push_records（链接级别去重）

内置源:
- arxiv:        arXiv API RSS (按 category 过滤)
- biorxiv:      bioRxiv RSS
- rss/atom:     学术新闻 + 博客 RSS/Atom
- opml:         用户上传 OPML 导入（一次性，不重复抓取）
- internal:     系统内部源 (KG 被忽视节点 / 阅读未完成材料 — 由 push_scheduler 处理)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import feedparser
import httpx

from app.services.interest import store
from shared.events import (
    InterestSourceFetched,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 内置源定义
# ═══════════════════════════════════════════

BUILTIN_SOURCES: list[dict] = [
    {
        "name": "arXiv Computer Science (cs.CL)",
        "type": "arxiv",
        "category": "预印本",
        "config": {
            "feed_url": "http://export.arxiv.org/rss/cs.CL",
            "default_category": "cs.CL",
        },
    },
    {
        "name": "arXiv Computer Science (cs.LG)",
        "type": "arxiv",
        "category": "预印本",
        "config": {
            "feed_url": "http://export.arxiv.org/rss/cs.LG",
            "default_category": "cs.LG",
        },
    },
    {
        "name": "arXiv Machine Learning (stat.ML)",
        "type": "arxiv",
        "category": "预印本",
        "config": {
            "feed_url": "http://export.arxiv.org/rss/stat.ML",
            "default_category": "stat.ML",
        },
    },
    {
        "name": "bioRxiv (q-bio)",
        "type": "biorxiv",
        "category": "预印本",
        "config": {
            "feed_url": "https://connect.biorxiv.org/biorxiv_xml.php?subject=q-bio",
        },
    },
    {
        "name": "Nature - Research Highlights",
        "type": "rss",
        "category": "学术新闻",
        "config": {
            "feed_url": "https://www.nature.com/nature.rss",
        },
    },
    {
        "name": "Science - Latest News",
        "type": "rss",
        "category": "学术新闻",
        "config": {
            "feed_url": "https://www.science.org/rss/news_current.xml",
        },
    },
    {
        "name": "Hacker News - Best",
        "type": "rss",
        "category": "技术博客",
        "config": {
            "feed_url": "https://hnrss.org/best",
        },
    },
]


@dataclass
class FetchedItem:
    """抓取到的单条内容（用于写入 interest_push_records）"""
    title: str
    url: str
    summary: str = ""
    author: str = ""
    published_at: Optional[datetime] = None
    extra: dict = field(default_factory=dict)


# ═══════════════════════════════════════════
# 抓取器主体
# ═══════════════════════════════════════════


class SourceFetcher:
    """信息源抓取器（feedparser + httpx）"""

    # 抓取超时
    DEFAULT_TIMEOUT = 30.0
    # User-Agent
    USER_AGENT = (
        "Mozilla/5.0 (compatible; EduCompanion-InterestExplorer/1.0)"
    )
    # 每次抓取最多保留条目数
    MAX_ITEMS_PER_FETCH = 50

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.DEFAULT_TIMEOUT,
                headers={"User-Agent": self.USER_AGENT},
                follow_redirects=True,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── 单源抓取 ──

    async def fetch_source(self, source: dict) -> list[FetchedItem]:
        """抓取一个信息源

        source: dict 包含 id / name / type / config / user_id
        """
        type_ = source.get("type")
        cfg = source.get("config") or {}
        if isinstance(cfg, str):
            import json
            try:
                cfg = json.loads(cfg)
            except Exception:
                cfg = {}

        try:
            if type_ in ("rss", "atom", "arxiv", "biorxiv"):
                feed_url = cfg.get("feed_url")
                if not feed_url:
                    return []
                return await self._fetch_feed(feed_url)
            if type_ == "opml":
                # OPML 是一次性导入，不重复抓取
                return []
            if type_ == "internal":
                # 内部源由 push_scheduler 处理
                return []
            logger.warning("不支持的信息源类型: %s", type_)
            return []
        except Exception as e:
            logger.warning("fetch_source 失败 (type=%s): %s", type_, e)
            raise

    async def _fetch_feed(self, feed_url: str) -> list[FetchedItem]:
        """用 httpx 拉取 + feedparser 解析"""
        client = await self._get_client()
        resp = await client.get(feed_url)
        resp.raise_for_status()
        raw = resp.text

        # feedparser 解析（同步，CPU 轻量，在线程池中执行）
        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(
            None, feedparser.parse, raw
        )

        items: list[FetchedItem] = []
        for entry in parsed.entries[: self.MAX_ITEMS_PER_FETCH]:
            title = (entry.get("title") or "").strip()
            url = (entry.get("link") or "").strip()
            if not title or not url:
                continue
            summary = (entry.get("summary") or entry.get("description") or "").strip()
            # 去掉 HTML 标签
            summary = _strip_html(summary)[: 1000]
            author = (entry.get("author") or "").strip()
            published_at = _parse_datetime(
                entry.get("published_parsed")
                or entry.get("updated_parsed")
            )
            items.append(FetchedItem(
                title=title,
                url=url,
                summary=summary,
                author=author,
                published_at=published_at,
            ))
        return items

    # ── 批量抓取 ──

    async def fetch_all_enabled(self) -> dict[str, Any]:
        """抓取所有启用的信息源

        数据流:
          1. 抓取到的原始条目写入 interest_fetched_items (跨用户共享的抓取缓存)
          2. 用户私有源 (interest_sources.user_id = x) 同时为该用户写入 interest_push_records
          3. 系统源 (interest_sources.user_id IS NULL) 不直接生成推送
             - 在 trigger_push 时按用户的订阅状态 + 标签匹配才物化为 push_records

        返回: {
          "source_results": [ {source_id, name, items_count, error} ... ],
          "total_items": int,
          "duration_ms": int,
        }
        """
        start = time.time()
        sources = store.list_sources(user_id=None, enabled_only=False)
        # 只抓取启用的
        sources = [s for s in sources if s.get("enabled")]

        results: list[dict] = []
        total_items = 0
        for source in sources:
            sid = source["id"]
            t0 = time.time()
            try:
                items = await self.fetch_source(source)
                items_count = len(items)
                results.append({
                    "source_id": sid,
                    "name": source.get("name"),
                    "items_count": items_count,
                    "error": None,
                    "duration_ms": int((time.time() - t0) * 1000),
                })
                # 1) 写入抓取缓存（所有源都写）
                if items:
                    store.upsert_fetched_items(
                        source_id=sid,
                        items=[
                            {
                                "title": it.title,
                                "url": it.url,
                                "summary": it.summary,
                                "author": it.author,
                                "published_at": it.published_at,
                            }
                            for it in items
                        ],
                    )
                # 2) 用户私有源：直接为该用户生成推送
                user_id = source.get("user_id")
                if user_id:
                    for item in items:
                        store.create_push_record(
                            user_id=user_id,
                            push_type="research_object",
                            title=item.title,
                            source_id=sid,
                            summary=item.summary,
                            url=item.url,
                            author=item.author,
                            published_at=item.published_at,
                        )
                store.update_source_fetch_status(sid, "success", None)
                total_items += items_count
            except Exception as e:
                results.append({
                    "source_id": sid,
                    "name": source.get("name"),
                    "items_count": 0,
                    "error": str(e),
                    "duration_ms": int((time.time() - t0) * 1000),
                })
                store.update_source_fetch_status(sid, "error", str(e)[: 500])

        return {
            "source_results": results,
            "total_items": total_items,
            "duration_ms": int((time.time() - start) * 1000),
        }


# ═══════════════════════════════════════════
# OPML 导入
# ═══════════════════════════════════════════


def parse_opml(opml_text: str) -> list[dict]:
    """解析 OPML 订阅列表

    仅提取 RSS/Atom 类型的订阅，跳过其他类型。
    返回 [{name, feed_url, type, category}] 列表。
    """
    items: list[dict] = []
    try:
        root = ET.fromstring(opml_text)
    except ET.ParseError as e:
        raise ValueError(f"OPML 解析失败: {e}")

    body = root.find("body")
    if body is None:
        return items

    def _walk(elem: ET.Element, inherited_category: str = "") -> None:
        for outline in elem.findall("outline"):
            attrs = dict(outline.attrib)
            title = attrs.get("title") or attrs.get("text") or ""
            xml_url = attrs.get("xmlUrl") or attrs.get("xmlurl")
            type_ = attrs.get("type", "").lower()
            category = attrs.get("category") or inherited_category

            if xml_url:
                # 跳过非 RSS/Atom 的 url
                if type_ and type_ not in ("rss", "atom"):
                    continue
                if not (xml_url.startswith("http://") or xml_url.startswith("https://")):
                    continue
                items.append({
                    "name": title or xml_url,
                    "feed_url": xml_url,
                    "type": "rss",
                    "category": category or None,
                })
            else:
                # 嵌套分组
                _walk(outline, category)

    _walk(body)
    return items


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════


_HTML_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    t = _HTML_RE.sub(" ", text)
    t = _WHITESPACE_RE.sub(" ", t)
    return t.strip()


def _parse_datetime(parsed_time: Any) -> Optional[datetime]:
    """feedparser 时间结构体 -> datetime"""
    if not parsed_time:
        return None
    try:
        from time import mktime
        return datetime.fromtimestamp(
            mktime(parsed_time), tz=timezone.utc
        )
    except Exception:
        return None


# ═══════════════════════════════════════════
# 模块单例
# ═══════════════════════════════════════════

_fetcher: SourceFetcher | None = None


def get_fetcher() -> SourceFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = SourceFetcher()
    return _fetcher
