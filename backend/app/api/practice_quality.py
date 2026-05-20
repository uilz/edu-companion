"""
练习系统 — 题目质量监控 API
Phase 4D: 从 api/practice.py 拆分
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from app.db.database import get_db

router = APIRouter(prefix="/api/practice", tags=["practice-quality"])


@router.get("/quality")
async def get_quality_summary():
    """获取全量质量摘要"""
    from app.services.quality_analyzer import quality_analyzer
    summary = quality_analyzer.analyze_all()
    return summary.to_dict()


@router.get("/quality/worst")
async def get_worst_questions(limit: int = 10):
    """获取质量最差的题目列表"""
    from app.services.quality_analyzer import quality_analyzer
    db = get_db()
    rows = db.fetchall("SELECT question_id FROM questions WHERE status != 'retired'")
    results = []
    for r in rows:
        q = quality_analyzer.analyze_question(r["question_id"])
        if q and q.total_attempts >= quality_analyzer.MIN_ATTEMPTS:
            results.append(q)
    results.sort(key=lambda r: r.quality_score)
    worst = results[:limit]
    return {
        "worst": [r.to_dict() for r in worst],
        "total_analyzed": len(results),
        "threshold": quality_analyzer.MIN_ATTEMPTS,
    }


@router.post("/quality/apply")
async def apply_quality_actions(dry_run: bool = True):
    """执行质量分析建议动作"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.apply_actions(dry_run=dry_run)
    return result


@router.get("/quality/{question_id}")
async def get_question_quality(question_id: str):
    """获取单题质量分析"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.analyze_question(question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return result.to_dict()


@router.get("/quality/{question_id}/distractors")
async def get_distractor_analysis(question_id: str):
    """获取单题的干扰项分析"""
    from app.services.quality_analyzer import quality_analyzer
    result = quality_analyzer.analyze_question(question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {
        "question_id": question_id,
        "distractors": [d.to_dict() for d in result.distractors],
        "correct_answer": next(
            (d.option_letter for d in result.distractors if d.is_correct), ""
        ),
    }
