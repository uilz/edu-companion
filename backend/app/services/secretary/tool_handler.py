"""
Secretary 工具处理器（从 tool_executor.py 迁出）
LLM 工具系统中的 diagnostic 处理器，调用 domain 层 SecretaryService。
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


async def handle_secretary_diagnose(params: dict) -> dict:
    """秘书诊断：分析学习状态，生成建议"""
    scope = params.get("scope", "quick")
    user_id = params.get("user_id", "")
    if not user_id:
        return {"error": "user_id required", "status": "failed"}

    try:
        from app.domain.secretary.secretary_service import SecretaryService
        svc = SecretaryService()

        if scope == "full":
            report, proposals = await svc.diagnose_and_suggest(user_id)
            return {
                "status": "ready",
                "scope": "full",
                "summary": report.summary,
                "weak_point_count": len(report.weak_points),
                "cognitive_load": report.cognitive_load,
                "proposals": [
                    {"title": p.title, "description": p.description,
                     "action_type": p.action_type, "priority": p.priority}
                    for p in proposals[:5]
                ],
            }
        else:
            assess = await svc.quick_assess(user_id)
            return {
                "status": "ready",
                "scope": "quick",
                "assessment": {
                    "summary": assess.get("summary", ""),
                    "weak_points": assess.get("weak_points", []),
                    "cognitive_load": assess.get("cognitive_load", 0),
                    "recent_progress": assess.get("recent_progress", ""),
                },
            }
    except Exception as e:
        logger.warning("秘书诊断失败: %s", e)
        return {"status": "failed", "error": str(e), "scope": scope}
