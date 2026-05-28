"""
学习计划 REST API v2.0 — 自适应计划

改进: 使用 AdaptivePlanGenerator 替代旧 learner_model.generate_study_plan
- 支持前置卡控
- 难度自适应
- 计划快照/历史
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from shared.constants import DEFAULT_USER_ID
from app.services.adaptive_planner import adaptive_planner
from app.core.knowledge_trace import bkt_engine, get_all_cognitive_states, get_cognitive_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/study", tags=["学习计划"])


@router.post("/plan/generate")
async def generate_study_plan(
    user_id: str = DEFAULT_USER_ID,
    subject: Optional[str] = None,
    reason: str = "manual",
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
    db = __import__("app.db.database", fromlist=["get_db"]).get_db()
    db.upsert("plan_task_completions", {
        "user_id": user_id,
        "task_id": task_id,
        "completed_at": __import__("datetime").datetime.now().isoformat(),
    }, "(user_id, task_id)")
    return {"message": "任务标记完成", "task_id": task_id}


@router.get("/plan/{user_id}/progress")
async def get_plan_progress(user_id: str) -> dict[str, Any]:
    """获取计划进度"""
    plan = await adaptive_planner.generate(user_id=user_id, reason="progress_check")
    plan_data = plan.get("plan", {})
    items = plan_data.get("items", [])

    db = __import__("app.db.database", fromlist=["get_db"]).get_db()
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


# ── 计划历史/快照 ──

@router.get("/plan/{user_id}/history")
async def get_plan_history(user_id: str, limit: int = 5):
    """获取计划变更历史"""
    db = __import__("app.db.database", fromlist=["get_db"]).get_db()
    try:
        rows = db.fetchall(
            "SELECT * FROM plan_snapshots WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (user_id, limit),
        )
        return {
            "history": [
                {
                    "id": r.get("id"),
                    "reason": r.get("reason", ""),
                    "changes": r.get("changes_json"),
                    "plan": r.get("plan_json"),
                    "created_at": str(r.get("created_at", "")),
                }
                for r in rows
            ],
            "total": len(rows),
        }
    except Exception:
        return {"history": [], "total": 0, "message": "plan_snapshots 表不存在"}


# ── 手动触发重调 ──

@router.post("/plan/refresh")
async def refresh_plan(
    user_id: str = DEFAULT_USER_ID,
    force: bool = False,
):
    """
    手动刷新学习计划

    force=true: 强制重生成（即使没有知识变化）
    force=false: 仅在检测到变化时重生成
    """
    if not force:
        # 检查是否有变化
        old = adaptive_planner._get_last_plan(user_id)
        if old:
            latest = await adaptive_planner.generate(user_id, reason="refresh_check")
            new_skills = [it["skill_id"] for it in latest.get("plan", {}).get("items", [])]
            if set(old) == set(new_skills):
                return {
                    "refreshed": False,
                    "message": "计划无需更新，知识状态无显著变化",
                    "plan": latest.get("plan"),
                }

    result = await adaptive_planner.generate(user_id, reason="manual_refresh")
    return {
        "refreshed": True,
        "message": "计划已刷新",
        **result,
    }


# ── 知识图谱驱动的学习建议 ──

@router.get("/suggestions")
async def get_learning_suggestions(
    user_id: str = DEFAULT_USER_ID,
    subject: Optional[str] = None,
):
    """
    获取智能学习建议

    综合: BKT薄弱点 + 前置依赖链 + 最近正确率
    """
    states = get_all_cognitive_states(user_id)
    recs = bkt_engine.recommend_practice(states, top_n=10)

    # 分为三组
    urgent = []    # 接近掌握 → 差一点
    building = []  # 发展中
    new_topic = [] # 初学/未接触

    from domain.knowledge.checker import PrerequisiteChecker
    from domain.knowledge.prerequisites import SKILL_TO_SUBJECT

    class _Adapter:
        async def get_knowledge_state(self, uid, sid):
            # Phase 6: 优先 CognitiveNode
            try:
                from app.cognitive.storage import get_node
                node = get_node(sid, uid)
                if node and node.belief:
                    return {
                        "skill_id": sid,
                        "p_known": node.belief.proficiency_mean,
                        "attempt_count": node.practice_summary.total_attempts if node.practice_summary else 0,
                        "correct_count": node.practice_summary.correct_attempts if node.practice_summary else 0,
                        "source": "cognitive_node",
                    }
            except Exception:
                pass
            # 备降: CognitiveNode reader
            state = get_cognitive_state(uid, sid)
            return state.model_dump()

    checker = PrerequisiteChecker(_Adapter())

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
