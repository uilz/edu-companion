"""Growth API — 成长记录的查询接口。

供 Today（最新成长）、Growth 页面（历史）、Profile（统计）消费。
"""

from fastapi import APIRouter, Depends, HTTPException

from app.domain.auth.dependencies import current_user_id
from app.domain.growth.service import GrowthService
from app.application.di import get_growth_service

router = APIRouter(prefix="/api/growth", tags=["growth"])


@router.get("/latest", response_model=dict)
async def get_latest_growth(
    user_id: str = Depends(current_user_id),
    service: GrowthService = Depends(get_growth_service),
):
    """获取最新一次 GrowthRecord。
    
    供 Today 页面显示上次学习后的成长。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    result = await service.get_latest_growth(user_id)
    if not result:
        return {"record": None}
    return {"record": result}


@router.get("/records", response_model=dict)
async def list_growth_records(
    user_id: str = Depends(current_user_id),
    service: GrowthService = Depends(get_growth_service),
    limit: int = 20,
):
    """获取 GrowthRecord 列表。

    供 Growth 页面展示成长历史。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    records = await service.list_growth_records(user_id, limit)
    return {"records": records, "total": len(records)}


@router.get("/summary", response_model=dict)
async def get_growth_summary(
    user_id: str = Depends(current_user_id),
    service: GrowthService = Depends(get_growth_service),
):
    """获取 Growth 摘要。

    供 Growth 页面顶部卡片、Profile 页面统计。
    包含 total_sessions、streak_days、total_gain_score 等。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    return await service.get_growth_summary(user_id)
