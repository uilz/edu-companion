"""Session API — 学习会话的 REST 接口。

所有学习 Session 通过此 API 管理。
Conversation 是 Session 的内部实现，不暴露独立 API。
"""

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.domain.auth.dependencies import current_user_id
from app.domain.session import SessionService, SessionDomainError
from app.domain.growth.service import GrowthService
from app.application.di import get_session_service, get_growth_service

router = APIRouter(prefix="/api/session", tags=["session"])


# ── 请求模型 ──

class CreateSessionRequest(BaseModel):
    title: str = ""
    focus: str = ""
    goal: str = ""
    estimated_minutes: int = 25
    recommendation_id: str | None = None
    mission_id: str | None = None


class TransitionStageRequest(BaseModel):
    new_stage: str  # "intro" | "learn" | "practice" | "reflect"


class SetMissionRequest(BaseModel):
    title: str
    estimated_minutes: int = 25
    steps: list[dict] = []  # [{order, description, type}]


class CompleteSessionRequest(BaseModel):
    reflection: dict | None = None  # {content, key_takeaways, next_steps}


# ── API 端点 ──

@router.post("", response_model=dict)
async def create_session(
    body: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """创建学习 Session。

    Today 页面点击"开始今天"时调用。
    关联 Conversation 作为内部交互组件。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        result = await service.create_session(
            user_id=user_id,
            title=body.title,
            focus=body.focus,
            goal=body.goal,
            estimated_minutes=body.estimated_minutes,
            recommendation_id=body.recommendation_id,
            mission_id=body.mission_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=list[dict])
async def list_active_sessions(
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """获取用户当前活跃的 Session 列表。"""
    if not user_id:
        return []
    return await service.list_active_sessions(user_id)


@router.get("/continue", response_model=dict)
async def get_continue_context(
    user_id: str = Depends(current_user_id),
    session_service: SessionService = Depends(get_session_service),
    growth_service: GrowthService = Depends(get_growth_service),
):
    """获取「继续昨天」上下文。

    优先级：
    1. 当前有活跃 Session → 继续当前学习（type=active_session）
    2. 最近有已完成的学习记录且不是今天 → 继续昨天主题（type=yesterday）
    3. 否则 → 无继续上下文（type=none）
    """
    if not user_id:
        return {"type": "none"}

    # 1. 优先返回活跃 Session
    active = await session_service.list_active_sessions(user_id)
    if active:
        s = active[0]
        return {
            "type": "active_session",
            "session_id": s["id"],
            "title": s["title"] or "学习 Session",
            "stage": s["stage"],
        }

    # 2. 否则基于最新 GrowthRecord 恢复昨天上下文
    latest = await growth_service.get_latest_growth(user_id)
    if not latest:
        return {"type": "none"}

    now_day = int(time.time() // 86400)
    record_day = int(latest.get("session_started_at", 0) // 86400)
    if record_day >= now_day:
        # 最新记录就是今天，不需要「继续昨天」
        return {"type": "none"}

    days_ago = now_day - record_day
    if days_ago == 1:
        date_label = "昨天"
    elif days_ago == 2:
        date_label = "前天"
    else:
        date_label = f"{days_ago}天前"

    skills = [
        g["skill"]
        for g in latest.get("skill_gains", [])
        if g.get("skill")
    ]

    return {
        "type": "yesterday",
        "session_id": latest.get("session_id", ""),
        "title": latest.get("session_title") or "一次学习",
        "key_takeaways": latest.get("key_takeaways", [])[:3],
        "reflection_snippet": latest.get("reflection_snippet", ""),
        "skills": skills,
        "date_label": date_label,
        "started_at": latest.get("session_started_at", 0),
    }


@router.get("/recent", response_model=list[dict])
async def list_recent_sessions(
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
    limit: int = 10,
):
    """获取用户最近的 Session 列表。"""
    if not user_id:
        return []
    return await service.list_recent_sessions(user_id, limit)


@router.get("/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """获取 Session 当前状态。"""
    result = await service.get_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.patch("/{session_id}/stage", response_model=dict)
async def transition_stage(
    session_id: str,
    body: TransitionStageRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """Session 阶段转移 (intro → learn → practice → reflect)。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        return await service.transition_stage(session_id, body.new_stage)
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{session_id}/mission", response_model=dict)
async def set_mission(
    session_id: str,
    body: SetMissionRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """设置 Session 的任务分解（intro 阶段调用）。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        return await service.set_mission(
            session_id=session_id,
            title=body.title,
            estimated_minutes=body.estimated_minutes,
            steps=body.steps,
        )
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{session_id}/complete", response_model=dict)
async def complete_session(
    session_id: str,
    body: CompleteSessionRequest | None = None,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """完成 Session。

    发布 LearningSessionCompleted 事件，Growth Engine 监听并生成 GrowthSummary。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        reflection = body.reflection if body else None
        return await service.complete_session(session_id, reflection)
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{session_id}/cancel", response_model=dict)
async def cancel_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """取消 Session。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        return await service.cancel_session(session_id)
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))
