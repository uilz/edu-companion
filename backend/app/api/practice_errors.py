"""
练习系统 — 错题本 + 错因分析 API
Phase 4D: 从 api/practice.py 拆分
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from app.shared.constants import DEFAULT_USER_ID
from app.db.database import get_db
from app.core.knowledge_trace import bkt_engine

router = APIRouter(prefix="/api/practice", tags=["practice-errors"])


@router.get("/errors")
async def get_error_book(
    resolved: Optional[bool] = None,
    skill_id: Optional[str] = None,
    limit: int = 20,
):
    """获取错题本"""
    db = get_db()
    conditions = ["user_id = %s"]
    params = [DEFAULT_USER_ID]
    if resolved is not None:
        conditions.append("is_resolved = %s"); params.append(resolved)
    if skill_id:
        conditions.append("skill_id = %s"); params.append(skill_id)
    sql = f"SELECT * FROM error_book WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    total = db.fetchone("SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s", (DEFAULT_USER_ID,))
    unresolved = db.fetchone("SELECT COUNT(*) as cnt FROM error_book WHERE user_id = %s AND is_resolved = FALSE", (DEFAULT_USER_ID,))
    return {"entries": [dict(r) for r in rows], "total": total["cnt"] if total else 0, "unresolved_count": unresolved["cnt"] if unresolved else 0}


@router.post("/errors/{entry_id}/review")
async def review_error(entry_id: str, is_correct: bool = True):
    """复习错题"""
    db = get_db()
    entry = db.fetchone("SELECT * FROM error_book WHERE entry_id = %s", (entry_id,))
    if not entry:
        raise HTTPException(status_code=404, detail="Error entry not found")
    new_count = entry["review_count"] + 1
    db.execute("UPDATE error_book SET review_count = %s, is_resolved = %s WHERE entry_id = %s", (new_count, is_correct, entry_id))
    return {"entry_id": entry_id, "review_count": new_count, "is_resolved": is_correct}


@router.get("/errors/due")
async def get_due_errors():
    """获取待复习错题"""
    db = get_db()
    rows = db.fetchall("SELECT * FROM error_book WHERE user_id = %s AND is_resolved = FALSE ORDER BY created_at LIMIT 10", (DEFAULT_USER_ID,))
    return {"due": [dict(r) for r in rows], "total_due": len(rows)}


@router.post("/errors/{entry_id}/analyze")
async def analyze_error_entry(entry_id: str):
    """LLM 深度分析单条错题的错因"""
    from app.services.error_attribution import analyze_error

    db = get_db()
    entry = db.fetchone(
        "SELECT * FROM error_book WHERE entry_id = %s", (entry_id,)
    )
    if not entry:
        raise HTTPException(404, "错题记录不存在")
    entry = dict(entry)

    # 已有归因则直接返回
    attribution = entry.get("attribution")
    if attribution:
        if isinstance(attribution, str):
            import json as _json
            attribution = _json.loads(attribution)
        return {"entry_id": entry_id, "attribution": attribution}

    # LLM 分析
    result = await analyze_error(
        question_text=entry.get("question_text", ""),
        user_answer=entry.get("user_answer", ""),
        correct_answer=entry.get("correct_answer", ""),
        error_type=entry.get("error_type", ""),
        skill_id=entry.get("skill_id", ""),
    )

    # 存入数据库
    import json as _json
    db.execute(
        "UPDATE error_book SET attribution = %s WHERE entry_id = %s",
        (_json.dumps(result, ensure_ascii=False), entry_id),
    )

    return {"entry_id": entry_id, "attribution": result}


@router.get("/errors/stats")
async def get_error_attribution_stats():
    """错因分布统计"""
    from app.services.error_attribution import get_error_stats

    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM error_book WHERE user_id = %s AND is_resolved = FALSE",
        (DEFAULT_USER_ID,),
    )
    entries = [dict(r) for r in rows]
    stats = get_error_stats(entries)
    return stats
