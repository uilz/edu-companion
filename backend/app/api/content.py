"""
内容搜索 REST API 端点
搜索和浏览学习内容（文章、视频、练习等）
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter

from app.core.learner_model import learner_engine
from app.schemas.learner import ContentItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/content", tags=["内容搜索"])


@router.get("/search", response_model=list[ContentItem])
async def search_content(
    query: str,
    subject: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 10,
) -> list[ContentItem]:
    """
    搜索学习内容

    支持关键词搜索，可按学科和内容类型筛选

    参数:
        query: 搜索关键词
        subject: 学科筛选
        content_type: 内容类型 (video/article/exercise/quiz)
        limit: 返回数量限制

    返回:
        匹配的内容列表（按相关性排序）
    """
    results = learner_engine.search_content(
        query=query,
        subject=subject,
        content_type=content_type,
        limit=limit,
    )
    return results


@router.get("/list", response_model=list[ContentItem])
async def list_content(
    subject: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 20,
) -> list[ContentItem]:
    """
    列出所有可用内容

    参数:
        subject: 学科筛选
        content_type: 内容类型筛选
        limit: 返回数量限制

    返回:
        内容列表
    """
    all_content: list[ContentItem] = []

    for items in learner_engine._content_store.values():
        all_content.extend(items)

    # 筛选
    if subject:
        all_content = [c for c in all_content if c.subject == subject]
    if content_type:
        all_content = [c for c in all_content if c.content_type == content_type]

    return all_content[:limit]


@router.get("/{content_id}", response_model=Optional[ContentItem])
async def get_content(content_id: str) -> Optional[ContentItem]:
    """
    获取单个内容详情

    参数:
        content_id: 内容ID

    返回:
        内容详情
    """
    for items in learner_engine._content_store.values():
        for item in items:
            if item.content_id == content_id:
                return item

    return None


@router.get("/subjects/list")
async def list_subjects() -> list[dict[str, str | int]]:
    """
    列出所有可用学科及其内容数量

    返回:
        学科列表
    """
    subjects: dict[str, int] = {}
    for subject, items in learner_engine._content_store.items():
        subjects[subject] = len(items)

    return [
        {"subject": subj, "content_count": count}
        for subj, count in subjects.items()
    ]
