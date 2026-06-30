"""
Admin API 路由 — 管理系统错误报告
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.admin_error import AdminError
from app.services.admin.error_service import admin_error_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/errors", response_model=list[AdminError])
async def list_errors(
    source: str | None = Query(None, description="按错误来源筛选"),
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
) -> list[AdminError]:
    """获取系统错误列表"""
    return admin_error_service.get_errors(source=source, limit=limit)


@router.get("/errors/unacknowledged-count")
async def unacknowledged_count() -> dict:
    """获取未确认错误数量"""
    return {"count": admin_error_service.get_unacknowledged_count()}


@router.post("/errors/{error_id}/acknowledge")
async def acknowledge_error(error_id: str) -> dict:
    """标记错误为已确认"""
    if not admin_error_service.acknowledge_error(error_id):
        raise HTTPException(status_code=404, detail=f"Error {error_id} not found")
    return {"status": "acknowledged", "error_id": error_id}
