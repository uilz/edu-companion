"""题目质量监控"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/quality")
async def get_quality_summary():
    """获取全量质量摘要"""
    from app.services.analytics.quality_analyzer import quality_analyzer
    summary = quality_analyzer.analyze_all()
    return summary.to_dict()


@router.post("/quality/apply")
async def apply_quality_actions(dry_run: bool = True):
    """执行质量分析建议动作"""
    from app.services.analytics.quality_analyzer import quality_analyzer
    result = quality_analyzer.apply_actions(dry_run=dry_run)
    return result


@router.get("/quality/detail/{question_id}")
async def get_question_quality(question_id: str):
    """获取单题质量分析"""
    from app.services.analytics.quality_analyzer import quality_analyzer
    result = quality_analyzer.analyze_question(question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return result.to_dict()