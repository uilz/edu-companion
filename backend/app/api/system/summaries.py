"""
对话摘要 API — 查询对话历史摘要
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.common.summary_service import get_recent_summaries, build_condensed_context

router = APIRouter(prefix="/api/summaries", tags=["summaries"])


class ContextRequest(BaseModel):
    recent_turns: list[dict[str, str]] | None = None
    max_recent: int = 5


@router.get("/{conv_id}")
async def list_summaries(
    conv_id: str,
    limit: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    """获取对话摘要列表"""
    summaries = get_recent_summaries(conv_id, limit=limit)
    return {"conv_id": conv_id, "summaries": summaries, "count": len(summaries)}


@router.post("/{conv_id}/context")
async def get_condensed_context(
    conv_id: str,
    body: ContextRequest,
) -> dict[str, Any]:
    """获取裁剪后的 LLM 上下文"""
    context = build_condensed_context(
        conv_id,
        body.recent_turns or [],
        max_recent=body.max_recent,
    )
    return {"conv_id": conv_id, "context": context}
