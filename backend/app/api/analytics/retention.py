"""
学情分析 API — 遗忘曲线

端点:
  GET /api/analytics/retention  — 获取遗忘曲线（艾宾浩斯估算）
"""
from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends

from app.domain.auth.dependencies import current_user_id
from app.domain.knowledge.checker import PrerequisiteChecker
from app.domain.knowledge.prerequisites import SKILL_TO_SUBJECT
from app.services.knowledge.knowledge_state import get_knowledge_state as _canonical_get_ks
from shared.constants import get_mastery_label
from shared.knowledge_trace import get_cognitive_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["学情分析"])


class _BKTKnowledgeAdapter:
    """BKT 引擎 → PracticeService.get_knowledge_state 适配器"""
    async def get_knowledge_state(self, user_id: str, skill_id: str):
        return await _canonical_get_ks(user_id, skill_id)


def _get_checker() -> PrerequisiteChecker:
    return PrerequisiteChecker(_BKTKnowledgeAdapter())


@router.get("/retention")
async def get_retention_curve(user_id: str = Depends(current_user_id)):
    """
    获取遗忘曲线（艾宾浩斯估算）。
    """
    checker = _get_checker()
    prerequisites = checker._prerequisites

    skills = []
    for skill_id in prerequisites:
        state = get_cognitive_state(user_id, skill_id)
        if state.attempt_count == 0:
            continue
        S = max(1.0, state.p_known * 30 + math.log(state.attempt_count + 1) * 5)
        points = []
        for days in [0, 1, 3, 7, 14, 30, 60, 90]:
            retention = round(math.exp(-days / S) * 100, 1)
            points.append({"day": days, "retention": min(retention, 100)})
        skills.append({
            "skill_id": skill_id,
            "label": checker._skill_display_name(skill_id),
            "subject": SKILL_TO_SUBJECT.get(skill_id, "未知"),
            "mastery": round(state.p_known * 100, 1),
            "attempt_count": state.attempt_count,
            "curve": points,
        })

    skills.sort(key=lambda s: s["mastery"])
    return {
        "user_id": user_id,
        "skills": skills,
        "total": len(skills),
        "avg_retention_7d": round(
            sum(s["curve"][3]["retention"] for s in skills) / max(len(skills), 1), 1
        ) if skills else 0,
        "at_risk": [s for s in skills if s["curve"][3]["retention"] < 50],
    }
