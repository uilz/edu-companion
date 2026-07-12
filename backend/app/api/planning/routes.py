"""Planning REST API

端点：
  - GET    /api/planning/daily                          日视图
  - GET    /api/planning/weekly                         周视图
  - GET    /api/planning/knowledge                      知识视图
  - GET    /api/planning/items                          计划项列表
  - POST   /api/planning/items                          创建计划项
  - PATCH  /api/planning/items/{id}                     更新计划项
  - DELETE /api/planning/items/{id}                     删除计划项
  - POST   /api/planning/items/{id}/complete            标记完成（触发回写）
  - POST   /api/planning/items/{id}/start               标记开始
  - POST   /api/planning/items/{id}/skip                标记跳过
  - POST   /api/planning/items/{id}/extend              标记延长
  - GET    /api/planning/goals                          查询目标
  - POST   /api/planning/goals                          创建目标
  - PATCH  /api/planning/goals/{id}                     更新目标
  - GET    /api/planning/reviews                        查询周期回顾
  - POST   /api/planning/reviews/generate               生成周期回顾
  - GET    /api/planning/view-layouts                   查询视图方案
  - POST   /api/planning/view-layouts                   创建视图方案
"""
from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.planning import (
    accept_confirmation as accept_confirmation_svc,
    build_daily_view,
    build_knowledge_view,
    build_weekly_view,
    complete_plan_item,
    create_confirmation as create_confirmation_svc,
    create_goal as create_goal_svc,
    create_plan_item,
    create_view_layout as create_view_layout_svc,
    delete_plan_item,
    dismiss_confirmation as dismiss_confirmation_svc,
    extend_plan_item,
    generate_review as generate_review_svc,
    get_goal,
    list_confirmations as list_confirmations_svc,
    list_goals as list_goals_svc,
    list_plan_items,
    list_reviews as list_reviews_svc,
    list_view_layouts as list_view_layouts_svc,
    skip_plan_item,
    start_plan_item,
    update_goal as update_goal_svc,
    update_plan_item,
)
from app.api.planning.schemas import (
    DailyViewResponse,
    KnowledgeViewResponse,
    PeriodicReviewCreate,
    PeriodicReviewResponse,
    PlanGoalCreate,
    PlanGoalResponse,
    PlanGoalUpdate,
    PlanItemComplete,
    PlanItemConfirmationCreate,
    PlanItemConfirmationResponse,
    PlanItemCreate,
    PlanItemResponse,
    PlanItemUpdate,
    StatusBarResponse,
    ViewLayoutCreate,
    ViewLayoutResponse,
    WeeklyViewResponse,
)
from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/planning", tags=["规划"])


# ── 辅助：转换 ──


def _to_item_response(d: dict) -> PlanItemResponse:
    return PlanItemResponse(**d)


def _to_goal_response(d: dict) -> PlanGoalResponse:
    return PlanGoalResponse(**d)


def _to_review_response(d: dict) -> PeriodicReviewResponse:
    return PeriodicReviewResponse(**d)


def _to_layout_response(d: dict) -> ViewLayoutResponse:
    return ViewLayoutResponse(**d)


# ── 视图聚合端点 ──


@router.get("/daily", response_model=DailyViewResponse, summary="日视图")
async def get_daily_view(
    date: Optional[_date] = Query(default=None, description="YYYY-MM-DD；缺省=今天"),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    on_date = date or _date.today()
    data = build_daily_view(user_id, on_date)
    return DailyViewResponse(
        date=data["date"],
        status_bar=StatusBarResponse(**data["status_bar"]),
        timeline_items=[_to_item_response(x) for x in data["timeline_items"]],
        pending_pool=data["pending_pool"],
        adaptive_recommendations=data["adaptive_recommendations"],
        brief_summary=data["brief_summary"],
    )


@router.get("/weekly", response_model=WeeklyViewResponse, summary="周视图")
async def get_weekly_view(
    week_start: Optional[_date] = Query(default=None, description="周一日期；缺省=本周一"),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    today = _date.today()
    if week_start is None:
        week_start = today - timedelta(days=today.weekday())
    data = build_weekly_view(user_id, week_start)
    return WeeklyViewResponse(**data)


@router.get("/knowledge", response_model=KnowledgeViewResponse, summary="知识视图")
async def get_knowledge_view(
    selected_node_id: Optional[str] = Query(default=None),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    data = build_knowledge_view(user_id, selected_node_id)
    return KnowledgeViewResponse(
        nodes=data["nodes"],
        selected_node_id=data["selected_node_id"],
        selected_node_todos=[_to_item_response(x) for x in data["selected_node_todos"]],
    )


# ── 计划项 CRUD ──


@router.get("/items", summary="查询计划项")
async def list_items(
    date: Optional[_date] = Query(default=None),
    status: Optional[str] = Query(default=None),
    source_module: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=500),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    items = list_plan_items(user_id, date, status, source_module, limit)
    return {"items": [_to_item_response(x).model_dump(mode="json") for x in items], "total": len(items)}


@router.post("/items", response_model=PlanItemResponse, summary="创建计划项")
async def create_item(
    body: PlanItemCreate,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    item = create_plan_item(user_id, body.model_dump())
    if not item:
        raise HTTPException(status_code=500, detail="创建失败")
    return _to_item_response(item)


@router.patch("/items/{item_id}", response_model=PlanItemResponse, summary="更新计划项")
async def update_item(
    item_id: str,
    body: PlanItemUpdate,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    item = update_plan_item(user_id, item_id, body.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return _to_item_response(item)


@router.delete("/items/{item_id}", summary="删除计划项")
async def delete_item(
    item_id: str,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    ok = delete_plan_item(user_id, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return {"status": "deleted", "id": item_id}


@router.post("/items/{item_id}/complete", response_model=PlanItemResponse, summary="标记完成（触发回写）")
async def complete_item(
    item_id: str,
    body: PlanItemComplete,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        item = complete_plan_item(user_id, item_id, body.model_dump())
    except ValueError:
        raise HTTPException(status_code=404, detail="计划项不存在")
    if not item:
        raise HTTPException(status_code=500, detail="标记失败")
    return _to_item_response(item)


@router.post("/items/{item_id}/start", response_model=PlanItemResponse, summary="标记开始")
async def start_item(
    item_id: str,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    item = start_plan_item(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return _to_item_response(item)


@router.post("/items/{item_id}/skip", response_model=PlanItemResponse, summary="标记跳过")
async def skip_item(
    item_id: str,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    item = skip_plan_item(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return _to_item_response(item)


@router.post("/items/{item_id}/extend", response_model=PlanItemResponse, summary="延长")
async def extend_item(
    item_id: str,
    minutes: int = Query(default=15, ge=1, le=180),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    item = extend_plan_item(user_id, item_id, minutes)
    if not item:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return _to_item_response(item)


# ── 目标 ──


@router.get("/goals", summary="查询目标")
async def list_goals(
    status: Optional[str] = Query(default=None),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    goals = list_goals_svc(user_id, status)
    return {"goals": [_to_goal_response(x).model_dump(mode="json") for x in goals], "total": len(goals)}


@router.post("/goals", response_model=PlanGoalResponse, summary="创建目标")
async def create_goal(
    body: PlanGoalCreate,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    goal = create_goal_svc(user_id, body.model_dump())
    if not goal:
        raise HTTPException(status_code=500, detail="创建失败")
    return _to_goal_response(goal)


@router.patch("/goals/{goal_id}", response_model=PlanGoalResponse, summary="更新目标")
async def update_goal(
    goal_id: str,
    body: PlanGoalUpdate,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    goal = update_goal_svc(user_id, goal_id, body.model_dump(exclude_none=True))
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")
    return _to_goal_response(goal)


# ── 周期回顾 ──


@router.get("/reviews", summary="查询周期回顾")
async def list_reviews(
    limit: int = Query(default=20, le=100),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    reviews = list_reviews_svc(user_id, limit)
    return {"reviews": [_to_review_response(x).model_dump(mode="json") for x in reviews]}


@router.post("/reviews/generate", response_model=PeriodicReviewResponse, summary="生成周期回顾")
async def generate_review(
    body: PeriodicReviewCreate,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    review = generate_review_svc(user_id, body.model_dump())
    return _to_review_response(review)


# ── 视图方案 ──


@router.get("/view-layouts", summary="查询视图方案")
async def list_view_layouts(user_id: str = Depends(current_user_id)):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    layouts = list_view_layouts_svc(user_id)
    return {"layouts": [_to_layout_response(x).model_dump(mode="json") for x in layouts]}


@router.post("/view-layouts", response_model=ViewLayoutResponse, summary="创建视图方案")
async def create_view_layout(
    body: ViewLayoutCreate,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    layout = create_view_layout_svc(user_id, body.model_dump())
    return _to_layout_response(layout)


# ── 计划项确认请求 ──


def _to_confirmation_response(d: dict) -> PlanItemConfirmationResponse:
    return PlanItemConfirmationResponse(**d)


@router.get("/confirmations", summary="查询计划项确认请求")
async def list_confirmations(
    status: Optional[str] = Query(default=None),
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    confirmations = list_confirmations_svc(user_id, status)
    return {
        "confirmations": [_to_confirmation_response(x).model_dump(mode="json") for x in confirmations],
        "total": len(confirmations),
    }


@router.post("/confirmations", response_model=PlanItemConfirmationResponse, summary="创建计划项确认请求")
async def create_confirmation(
    body: PlanItemConfirmationCreate,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    confirmation = create_confirmation_svc(user_id, body.model_dump())
    return _to_confirmation_response(confirmation)


@router.post("/confirmations/{confirmation_id}/accept", response_model=PlanItemResponse, summary="接受计划项确认请求")
async def accept_confirmation(
    confirmation_id: str,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        item = accept_confirmation_svc(user_id, confirmation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_item_response(item)


@router.post("/confirmations/{confirmation_id}/dismiss", response_model=PlanItemConfirmationResponse, summary="忽略计划项确认请求")
async def dismiss_confirmation(
    confirmation_id: str,
    user_id: str = Depends(current_user_id),
):
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        confirmation = dismiss_confirmation_svc(user_id, confirmation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_confirmation_response(confirmation)
