"""
学习计划 REST API — 自适应计划

改进: 使用 AdaptivePlanGenerator 替代旧 learner_model.generate_study_plan
- 支持前置卡控
- 难度自适应
- 计划快照/历史
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.domain.auth.dependencies import current_user_id
from shared.constants import recommend_practice_items
from app.services.analytics.adaptive_planner import adaptive_planner
from datetime import datetime
from shared.knowledge_trace import get_all_cognitive_states, get_cognitive_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/study", tags=["学习计划"])


@router.post("/plan/generate")
async def generate_study_plan(
    user_id: str = Depends(current_user_id),
    subject: Optional[str] = None,
    reason: str = "manual",
    dir_id: Optional[str] = None,
):
    """
    生成自适应学习计划

    - 基于 BKT 知识状态 + 前置依赖链
    - 难度自适应：根据近7日正确率微调
    - 时间预算：根据习惯等级分配任务量
    """
    try:
        result = await adaptive_planner.generate(
            user_id=user_id,
            reason=reason,
            subject=subject,
            dir_id=dir_id,
        )
        return result
    except Exception as e:
        logger.error("生成学习计划失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")


@router.get("/plan/{user_id}")
async def get_study_plan(user_id: str):
    """获取当前学习计划（如无则自动生成）"""
    result = await adaptive_planner.generate(user_id=user_id, reason="auto")
    return result


@router.put("/plan/{user_id}/{task_id}/complete")
async def complete_task(user_id: str, task_id: str) -> dict[str, Any]:
    """标记任务完成"""
    # 标记完成（计划数据从plan_snapshots表读）
    from app.infrastructure.db.database import get_db
    db = get_db()
    db.upsert("plan_task_completions", {
        "user_id": user_id,
        "task_id": task_id,
        "completed_at": datetime.now().isoformat(),
    }, "(user_id, task_id)")
    return {"message": "任务标记完成", "task_id": task_id}


@router.get("/plan/{user_id}/progress")
async def get_plan_progress(user_id: str) -> dict[str, Any]:
    """获取计划进度"""
    plan = await adaptive_planner.generate(user_id=user_id, reason="progress_check")
    plan_data = plan.get("plan", {})
    items = plan_data.get("items", [])

    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT task_id FROM plan_task_completions WHERE user_id = %s",
        (user_id,),
    )
    completed_ids = {r["task_id"] for r in rows}

    total = len(items)
    completed = sum(1 for it in items if it["task_id"] in completed_ids)

    return {
        "has_plan": True,
        "total_tasks": total,
        "completed_tasks": completed,
        "completion_rate": completed / max(total, 1),
        "estimated_total_minutes": plan_data.get("estimated_total_minutes", 0),
        "habit_level": plan_data.get("habit_level", "beginner"),
        "week_number": plan_data.get("week_number", 0),
    }


# ── 知识图谱驱动的学习建议 ──

@router.get("/suggestions")
async def get_learning_suggestions(
    user_id: str = Depends(current_user_id),
    subject: Optional[str] = None,
    dir_id: Optional[str] = None,
):
    """
    获取智能学习建议

    综合: BKT薄弱点 + 前置依赖链 + 最近正确率
    """
    states = get_all_cognitive_states(user_id)
    recs = recommend_practice_items(states, top_n=10)

    # 分为三组
    urgent = []    # 接近掌握 → 差一点
    building = []  # 发展中
    new_topic = [] # 初学/未接触

    from app.domain.knowledge.checker import PrerequisiteChecker
    from app.domain.knowledge.prerequisites import SKILL_TO_SUBJECT

    from app.services.knowledge.knowledge_state import get_knowledge_state as _canonical_get_ks

    class _Adapter:
        async def get_knowledge_state(self, uid, sid):
            return await _canonical_get_ks(uid, sid)

    checker = PrerequisiteChecker(_Adapter())
    if dir_id:
        checker.load_from_knowledge_tree(user_id, dir_id)

    for rec in recs:
        sid = rec["skill_id"]
        if subject and SKILL_TO_SUBJECT.get(sid) != subject:
            continue
        entry = {
            "skill_id": sid,
            "label": checker._skill_display_name(sid),
            "level": rec["level"],
            "p_known": rec["p_known"],
            "subject": SKILL_TO_SUBJECT.get(sid, "未知"),
        }
        if rec["level"] == "接近掌握":
            urgent.append(entry)
        elif rec["level"] == "发展中":
            building.append(entry)
        else:
            new_topic.append(entry)

    return {
        "urgent": urgent[:3],       # 差一点掌握 → 优先突破
        "building": building[:3],   # 正在学 → 稳步推进
        "new_topic": new_topic[:3], # 新主题 → 可选扩展
        "suggestion": (
            f"建议优先突破「{urgent[0]['label']}」"
            if urgent else
            f"继续推进「{building[0]['label']}」"
            if building else
            "选择一个新主题开始学习吧 🌱"
        ),
    }
