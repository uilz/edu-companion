"""
学习计划 REST API 端点
管理个性化学习计划的生成和查询
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.core.learner_model import learner_engine
from app.schemas.learner import StudyPlan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/study", tags=["学习计划"])


@router.post("/plan/generate", response_model=StudyPlan)
async def generate_study_plan(
    user_id: str,
    subject: Optional[str] = None,
) -> StudyPlan:
    """
    为用户生成个性化学习计划

    根据用户的知识状态、掌握程度和学习历史，
    自动生成下周的学习任务安排

    参数:
        user_id: 用户ID
        subject: 指定学科（可选）

    返回:
        生成的学习计划
    """
    try:
        # 确保用户画像存在
        profile = learner_engine.get_or_create_profile(user_id)

        # 如果指定了学科，添加到用户学科列表
        if subject and subject not in profile.subjects:
            profile.subjects.append(subject)

        # 生成学习计划
        plan = learner_engine.generate_study_plan(user_id)
        logger.info("为用户 %s 生成学习计划，共 %d 项", user_id, len(plan.items))
        return plan

    except Exception as e:
        logger.error("生成学习计划失败: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"生成学习计划失败: {str(e)}",
        )


@router.get("/plan/{user_id}", response_model=Optional[StudyPlan])
async def get_study_plan(user_id: str) -> StudyPlan:
    """
    获取用户当前的学习计划

    如果用户还没有学习计划，会自动调用生成接口

    参数:
        user_id: 用户ID

    返回:
        当前学习计划
    """
    plan = learner_engine.get_study_plan(user_id)

    if not plan:
        # 自动创建
        plan = learner_engine.generate_study_plan(user_id)

    return plan


@router.put("/plan/{user_id}/{task_id}/complete")
async def complete_task(
    user_id: str,
    task_id: str,
) -> dict[str, Any]:
    """
    标记学习计划中的某个任务为已完成

    参数:
        user_id: 用户ID
        task_id: 任务ID

    返回:
        更新后的状态信息
    """
    plan = learner_engine.get_study_plan(user_id)

    if not plan:
        raise HTTPException(status_code=404, detail="未找到学习计划")

    # 查找并更新任务
    task_found = False
    for item in plan.items:
        if item.task_id == task_id:
            item.completed = True
            task_found = True
            break

    if not task_found:
        raise HTTPException(status_code=404, detail=f"未找到任务: {task_id}")

    # 统计进度
    total = len(plan.items)
    completed = sum(1 for item in plan.items if item.completed)

    return {
        "message": "任务标记为完成",
        "task_id": task_id,
        "progress": f"{completed}/{total}",
        "completion_rate": completed / total if total > 0 else 0.0,
    }


@router.get("/plan/{user_id}/progress")
async def get_plan_progress(user_id: str) -> dict[str, Any]:
    """
    获取学习计划的完成进度

    参数:
        user_id: 用户ID

    返回:
        进度统计信息
    """
    plan = learner_engine.get_study_plan(user_id)

    if not plan:
        return {
            "has_plan": False,
            "message": "暂无学习计划",
        }

    total = len(plan.items)
    completed = sum(1 for item in plan.items if item.completed)
    total_minutes = sum(item.estimated_minutes for item in plan.items)
    completed_minutes = sum(
        item.estimated_minutes for item in plan.items if item.completed
    )

    return {
        "has_plan": True,
        "total_tasks": total,
        "completed_tasks": completed,
        "completion_rate": completed / total if total > 0 else 0.0,
        "estimated_total_minutes": total_minutes,
        "completed_minutes": completed_minutes,
        "week_number": plan.week_number,
    }
