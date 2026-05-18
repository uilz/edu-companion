"""
知识图谱 + 前置知识卡控 REST API

端点:
  GET  /api/knowledge/graph          — 获取知识图谱 (nodes + edges + mastery)
  GET  /api/knowledge/prerequisites  — 获取指定技能的前置依赖
  POST /api/knowledge/check          — 检查用户是否可以练习某技能
  GET  /api/knowledge/blocked        — 获取用户被卡控的技能清单
  GET  /api/knowledge/ready          — 获取用户可练习的技能清单
  GET  /api/knowledge/path           — 获取最优学习路径
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.knowledge_trace import bkt_engine
from domain.knowledge.checker import PrerequisiteChecker
from domain.knowledge.prerequisites import (
    ALL_PREREQUISITES,
    SKILL_TO_SUBJECT,
    SUBJECT_SKILLS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识图谱"])


# ── Adapter: 将现有 BKT 引擎适配到 PrerequisiteChecker 接口 ──

class _BKTKnowledgeAdapter:
    """BKT 引擎 → PracticeService.get_knowledge_state 适配器"""
    async def get_knowledge_state(self, user_id: str, skill_id: str):
        state = bkt_engine.load_or_create(user_id, skill_id)
        return state.model_dump()


def _get_checker() -> PrerequisiteChecker:
    return PrerequisiteChecker(_BKTKnowledgeAdapter())


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/graph
# ═══════════════════════════════════════════════════════════

@router.get("/graph")
async def get_knowledge_graph(
    user_id: str = "default_user",
    subject: Optional[str] = None,
):
    """
    获取用户的知识图谱

    返回:
      nodes: 知识点节点 (含掌握度)
      edges: 前置依赖关系
    """
    checker = _get_checker()
    prerequisites = ALL_PREREQUISITES

    # 确定要显示的技能
    if subject and subject in SUBJECT_SKILLS:
        skills = SUBJECT_SKILLS[subject]
    else:
        skills = list(prerequisites.keys())

    # 节点
    nodes = []
    for skill_id in skills:
        state = bkt_engine.load_or_create(user_id, skill_id)
        result = await checker.can_practice(user_id, skill_id)

        nodes.append({
            "id": skill_id,
            "label": checker._skill_display_name(skill_id),
            "subject": SKILL_TO_SUBJECT.get(skill_id, "未知"),
            "mastery": round(state.p_known * 100, 1),
            "mastery_level": bkt_engine.get_mastery_level(state),
            "can_practice": result.can_practice,
            "blocked_by": result.blocked,
            "attempt_count": state.attempt_count,
        })

    # 边
    edges = []
    for skill_id, prereqs in prerequisites.items():
        if skill_id not in skills:
            continue
        for prereq_id in prereqs:
            edges.append({
                "from": prereq_id,
                "to": skill_id,
                "label": "前置",
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "subjects": list(SUBJECT_SKILLS.keys()),
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/prerequisites
# ═══════════════════════════════════════════════════════════

@router.get("/prerequisites")
async def get_prerequisites(skill_id: str = Query(..., description="知识点ID")):
    """获取指定技能的前置依赖"""
    checker = _get_checker()
    try:
        result = await checker.get_prerequisites(skill_id)
        return result
    except Exception:
        raise HTTPException(status_code=404, detail=f"未知技能: {skill_id}")


# ═══════════════════════════════════════════════════════════
# POST /api/knowledge/check
# ═══════════════════════════════════════════════════════════

from pydantic import BaseModel

class CheckRequest(BaseModel):
    user_id: str = "default_user"
    skill_ids: list[str]

@router.post("/check")
async def check_prerequisites(req: CheckRequest):
    """
    批量检查前置条件

    请求体: {"user_id": "u1", "skill_ids": ["calculus_derivative", "calculus_integral"]}
    返回: 每个技能的前置检查结果
    """
    checker = _get_checker()
    results = await checker.check_batch(req.user_id, req.skill_ids)
    return {
        "results": {sid: r.to_dict() for sid, r in results.items()},
        "all_pass": all(r.can_practice for r in results.values()),
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/blocked
# ═══════════════════════════════════════════════════════════

@router.get("/blocked")
async def get_blocked_skills(user_id: str = "default_user"):
    """获取用户被前置知识卡控的所有技能"""
    checker = _get_checker()
    blocked = await checker.get_blocked_skills(user_id)
    return {
        "blocked": blocked,
        "total": len(blocked),
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/ready
# ═══════════════════════════════════════════════════════════

@router.get("/ready")
async def get_ready_skills(
    user_id: str = "default_user",
    subject: Optional[str] = None,
):
    """获取用户当前可以练习的技能清单"""
    checker = _get_checker()
    skills = await checker.find_ready_skills(user_id, subject)
    return {
        "ready": skills,
        "total": len(skills),
        "subject": subject,
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/path
# ═══════════════════════════════════════════════════════════

@router.get("/path")
async def get_learning_path(
    user_id: str = "default_user",
    target_skill: str = Query(..., description="目标知识点ID"),
):
    """
    获取最优学习路径（拓扑排序 + 当前掌握度过滤）

    返回从用户当前已掌握知识到目标技能的最短路径
    """
    checker = _get_checker()
    prerequisites = ALL_PREREQUISITES

    if target_skill not in prerequisites:
        raise HTTPException(status_code=404, detail=f"未知技能: {target_skill}")

    # BFS 收集目标技能的所有传递前置
    all_prereqs: set[str] = set()

    def collect(skill_id: str):
        for p in prerequisites.get(skill_id, []):
            if p not in all_prereqs:
                all_prereqs.add(p)
                collect(p)

    collect(target_skill)

    # 过滤已掌握的
    path = []
    missing: list[str] = []
    for skill_id in sorted(all_prereqs, key=lambda s: checker._compute_depth(s)):
        state = bkt_engine.load_or_create(user_id, skill_id)
        if state.p_known >= 0.7:
            path.append({"skill_id": skill_id, "status": "已掌握",
                         "mastery": round(state.p_known * 100)})
        else:
            missing.append(skill_id)
            path.append({"skill_id": skill_id, "status": "待学习",
                         "mastery": round(state.p_known * 100)})

    # 目标技能本身
    target_state = bkt_engine.load_or_create(user_id, target_skill)
    path.append({"skill_id": target_skill, "status": "🎯 目标",
                 "mastery": round(target_state.p_known * 100)})

    return {
        "target": target_skill,
        "path": path,
        "total_steps": len(path),
        "mastered_count": sum(1 for p in path if p["status"] == "已掌握"),
        "remaining_count": len(missing),
        "remaining_skills": missing,
    }
