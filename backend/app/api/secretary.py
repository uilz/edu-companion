"""秘书系统 API 端点

提供: 秘书偏好管理、提案查询/采纳、快照获取、简报
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..domain.secretary.secretary_service import SecretaryService
from ..domain.secretary.models import ScopeSpec, SecretaryPrefs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secretary", tags=["秘书系统"])


def _get_service() -> SecretaryService:
    """获取秘书服务实例（依赖注入）"""
    return SecretaryService()


@router.get("/preferences")
async def get_preferences(
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """获取用户秘书偏好"""
    # 从 user_data 读取（TODO: 接入 PG 持久化）
    return {
        "enabled_extensions": ["review_reminder", "fatigue_manager", "daily_brief"],
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "max_proactive_per_day": 5,
    }


@router.patch("/preferences")
async def update_preferences(
    prefs: SecretaryPrefs,
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """更新用户秘书偏好"""
    # TODO: 持久化到 PG user_data.metadata.secretary_prefs
    return {"status": "ok", "updated": prefs.model_dump()}


@router.get("/snapshot")
async def get_snapshot(
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """获取当前学习状态快照"""
    assess = await service.quick_assess(user_id=user_id)
    return {
        "cognitive_load": assess.get("cognitive_load", 0),
        "weak_count": assess.get("weak_count", 0),
        "stagnant_count": assess.get("stagnant_count", 0),
        "streak_days": assess.get("streak_days", 0),
        "summary": assess.get("summary", ""),
    }


@router.get("/daily-brief")
async def get_daily_brief(
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """获取今日简报"""
    report, proposals = await service.diagnose_and_suggest(
        user_id=user_id, max_proposals=3,
    )
    return {
        "report": {
            "weak_count": len(report.weak_points),
            "cognitive_load": report.cognitive_load,
            "highlight": report.highlight,
            "summary": report.summary,
        },
        "proposals": [p.model_dump() for p in proposals],
    }


@router.post("/diagnose")
async def run_diagnosis(
    user_id: str = "default_user",
    scope_level: str = "user",
    scope_node_id: str | None = None,
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """执行诊断"""
    scope = ScopeSpec(level=scope_level, node_id=scope_node_id) if scope_level != "user" else None
    report = await service.diagnose(user_id=user_id, scope=scope)
    return {
        "weak_points": [wp.model_dump() for wp in report.weak_points[:20]],
        "cognitive_load": report.cognitive_load,
        "highlight": report.highlight,
        "summary": report.summary,
        "source_findings": report.source_findings,
    }


@router.post("/suggest")
async def get_suggestions(
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
) -> list[dict]:
    """获取学习建议"""
    proposals = service.suggest(user_id=user_id, max_proposals=5)
    return [p.model_dump() for p in proposals]


@router.post("/diagnose-and-suggest")
async def diagnose_and_suggest(
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """诊断+建议一步完成"""
    report, proposals = await service.diagnose_and_suggest(
        user_id=user_id, max_proposals=5,
    )
    return {
        "report": {
            "weak_points": [wp.model_dump() for wp in report.weak_points[:20]],
            "cognitive_load": report.cognitive_load,
            "highlight": report.highlight,
            "summary": report.summary,
        },
        "proposals": [p.model_dump() for p in proposals],
    }


@router.post("/push-to-blackboard")
async def push_proposals_to_blackboard(
    session_id: str,
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """运行诊断并将提案推送到黑板（供 Orchestrator 读取）"""
    report, proposals = await service.diagnose_and_suggest(
        user_id=user_id, max_proposals=3,
    )
    ok = await service.push_to_blackboard(session_id, proposals, report)
    return {
        "success": ok,
        "proposal_count": len(proposals),
        "report_summary": report.summary,
    }
