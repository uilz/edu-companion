"""秘书系统 API 端点

提供: 秘书偏好管理、提案查询/采纳/拒绝/暂缓、快照获取、简报、LLM 提案生成
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..domain.secretary.secretary_service import SecretaryService
from ..domain.secretary.models import Proposal, ScopeSpec, SecretaryPrefs
from ..domain.secretary.proposal_store import ProposalStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secretary", tags=["秘书系统"])

# ── 依赖 ──


def _get_service() -> SecretaryService:
    return SecretaryService()


def _get_store() -> ProposalStore:
    return ProposalStore()


# ── 偏好 ──


@router.get("/preferences")
async def get_preferences(
    user_id: str = "default_user",
) -> dict:
    """获取用户秘书偏好"""
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
) -> dict:
    """更新用户秘书偏好"""
    return {"status": "ok", "updated": prefs.model_dump()}


# ── 诊断与快照 ──


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


# ── 提案 CRUD ──


@router.get("/proposals/pending")
async def get_pending_proposals(
    user_id: str = "default_user",
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取待处理提案"""
    await _ensure_db_schema(store)
    proposals = store.get_pending_proposals(user_id=user_id)
    return [p.model_dump() for p in proposals]


@router.get("/proposals/history")
async def get_proposal_history(
    user_id: str = "default_user",
    days: int = 7,
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取提案历史"""
    return store.get_history(user_id=user_id, days=days)


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: str,
    user_id: str = "default_user",
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """采纳提案"""
    ok = store.update_status(proposal_id, "accepted", user_id, {"action": "user_accepted", "timestamp": __import__('time').time()})
    if not ok:
        raise HTTPException(404, "提案不存在或已处理")
    return {"status": "accepted"}


@router.post("/proposals/{proposal_id}/dismiss")
async def dismiss_proposal(
    proposal_id: str,
    user_id: str = "default_user",
    reason: str = "",
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """忽略提案"""
    store.update_status(proposal_id, "dismissed", user_id, {"action": "user_dismissed", "reason": reason})
    return {"status": "dismissed"}


@router.post("/proposals/{proposal_id}/snooze")
async def snooze_proposal(
    proposal_id: str,
    user_id: str = "default_user",
    minutes: int = 60,
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """暂缓提案"""
    from datetime import datetime, timezone, timedelta
    store._get_db().execute(
        "UPDATE secretary_proposals SET status = 'snoozed', snoozed_until = %s WHERE id = %s AND user_id = %s",
        (datetime.now(timezone.utc) + timedelta(minutes=minutes), proposal_id, user_id),
    )
    return {"status": "snoozed", "snoozed_until_minutes": minutes}


# ── LLM 生成 ──


@router.post("/generate-llm-proposals")
async def generate_llm_proposals(
    user_id: str = "default_user",
    service: SecretaryService = Depends(_get_service),
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """使用 LLM 生成润色提案"""
    # 1. 诊断
    report = await service.diagnose(user_id=user_id)

    # 2. LLM 润色提案
    from ..domain.secretary.engines.llm_proposal_generator import LLMProposalGenerator
    # 尝试获取 LLM 服务
    llm = None
    try:
        from app.services.llm_service import llm_service
        llm = llm_service
    except Exception:
        pass

    gen = LLMProposalGenerator(llm_service=llm)
    proposals = await gen.generate_suggestion(report, max_proposals=3)

    # 3. 持久化
    for p in proposals:
        store.save_proposal(p, user_id=user_id, session_id="api")

    return [p.model_dump() for p in proposals]


# ── 黑板推送 ──


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


# ── 辅助 ──

async def _ensure_db_schema(store: ProposalStore):
    """确保数据库表存在"""
    try:
        db = store._get_db()
        db.execute(
            "SELECT 1 FROM secretary_proposals LIMIT 1"
        )
    except Exception:
        # 表不存在，创建
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "db", "secretary_schema.sql"
        )
        if os.path.exists(schema_path):
            with open(schema_path) as f:
                db.execute(f.read())
            logger.info("✅ created secretary_proposals table")
