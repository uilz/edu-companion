"""秘书系统主服务入口 — 协调诊断、提案、黑板的全流程

使用方式:
    service = SecretaryService()
    report = await service.diagnose("user_xxx")
    proposals = service.suggest("user_xxx")
    await service.push_to_blackboard(session_id, proposals)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .models import (
    DiagnosisReport,
    Proposal,
    ScopeSpec,
)
from .engines.diagnosis import DiagnosisEngine
from .engines.proposal_service import ProposalGenerator
from shared.events import ConversationContextInjected

logger = logging.getLogger(__name__)


class SecretaryService:
    """秘书系统主入口"""

    def __init__(
        self,
        diagnosis_engine: DiagnosisEngine | None = None,
        proposal_generator: ProposalGenerator | None = None,
    ):
        self.diagnosis = diagnosis_engine or DiagnosisEngine()
        self.proposals = proposal_generator or ProposalGenerator()

    # ── 核心流程 ──

    async def diagnose(
        self,
        user_id: str,
        scope: ScopeSpec | None = None,
    ) -> DiagnosisReport:
        """执行诊断并返回报告"""
        report = await self.diagnosis.diagnose(user_id=user_id)
        logger.info(
            "诊断完成: user=%s weak=%d load=%.2f findings=%s",
            user_id,
            len(report.weak_points),
            report.cognitive_load,
            report.source_findings,
        )
        return report

    def suggest(
        self,
        user_id: str,
        report: DiagnosisReport | None = None,
        max_proposals: int = 5,
        multi_option: bool = False,
    ) -> list[Proposal] | list[list[Proposal]]:
        """生成学习建议"""
        if report:
            if multi_option:
                return self.proposals.generate_multi_option(report)
            return self.proposals.generate_from_diagnosis(report, max_proposals)
        return self.proposals.generate_from_analysis(
            user_id=user_id, max_proposals=max_proposals,
        )

    async def diagnose_and_suggest(
        self,
        user_id: str,
        scope: ScopeSpec | None = None,
        max_proposals: int = 5,
    ) -> tuple[DiagnosisReport, list[Proposal]]:
        """诊断 + 提案一步完成"""
        report = await self.diagnose(user_id=user_id, scope=scope)
        proposals = self.proposals.generate_from_diagnosis(report, max_proposals)
        return report, proposals

    # ── 黑板交互 ──

    async def push_to_blackboard(
        self,
        session_id: str,
        proposals: list[Proposal],
        report: DiagnosisReport | None = None,
    ) -> bool:
        """将提案推送到 Redis 黑板"""
        try:
            from app.core.blackboard import blackboard
            data = {
                "status": "ready",
                "proposals": [p.model_dump() for p in proposals],
                "timestamp": time.time(),
            }
            if report:
                data["report_summary"] = {
                    "weak_count": len(report.weak_points),
                    "cognitive_load": report.cognitive_load,
                    "summary": report.summary,
                }
            await blackboard.set(f"bb:secretary:{session_id}", data, ttl=300)
            return True
        except ImportError:
            logger.warning("blackboard module not available, skipped push")
            return False
        except Exception as e:
            logger.error(f"push_to_blackboard failed: {e}")
            return False

    async def read_from_blackboard(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        """从黑板读取当前会话的提案"""
        try:
            from app.core.blackboard import blackboard
            return await blackboard.get(f"bb:secretary:{session_id}")
        except ImportError:
            return None
        except Exception as e:
            logger.error(f"read_from_blackboard failed: {e}")
            return None

    # ── 快速评估 ──

    async def quick_assess(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """快速学习状态评估（轻量，无 LLM）"""
        return await self.diagnosis.quick_assess(user_id=user_id)

    # ── 对话上下文注入 ──

    async def get_conversation_context(
        self,
        user_id: str,
        conv_id: str | None = None,
        event_bus: Any | None = None,
    ) -> dict[str, Any]:
        """组装对话上下文包并发布 ConversationContextInjected 事件"""
        from app.infrastructure.db.proposal_store import ProposalStore
        from app.infrastructure.db.user_profile_store import user_profile_store

        # 1. 待处理提案
        proposals = ProposalStore().get_pending_proposals(user_id, limit=5)

        # 2. 活跃计划项
        due_plan_items: list[dict] = []
        active_goals: list[dict] = []
        try:
            from app.services.planning.items import list_plan_items
            from app.services.planning.goals import list_goals
            from datetime import date
            due_plan_items = list_plan_items(
                user_id=user_id,
                plan_date=date.today(),
                status="pending",
                limit=10,
            )
            active_goals = list_goals(user_id=user_id, status="active")
        except Exception as e:
            logger.debug("获取计划项失败: %s", e)

        # 3. 学习状态摘要
        summary = ""
        try:
            quick = await self.quick_assess(user_id=user_id)
            summary = quick.get("summary", "")
        except Exception as e:
            logger.debug("快速评估失败: %s", e)

        # 4. 建议话题
        suggested_topics: list[str] = []
        for p in proposals:
            if p.action_type in ("review", "practice"):
                label = (p.payload or {}).get("kp_id", "") or p.title
                if label:
                    suggested_topics.append(label)
        suggested_topics = suggested_topics[:5]

        # 5. 用户编排画像（用于响应风格提示）
        profile = user_profile_store.get_profile(user_id)
        response_style_hint = ""
        if profile.fatigue_score > 0.6:
            response_style_hint = "用户当前疲劳度较高，回复应简短、鼓励为主"
        elif profile.trust_score < 0.3:
            response_style_hint = "用户对秘书信任度较低，避免过度主动推销建议"

        payload = {
            "user_id": user_id,
            "conv_id": conv_id,
            "active_goals": active_goals[:3],
            "due_plan_items": due_plan_items[:5],
            "recent_learning_summary": summary,
            "suggested_topics": suggested_topics,
            "pending_proposals": [p.model_dump() for p in proposals],
            "available_tools": [
                {"tool_name": "start_practice", "when_to_use": "用户想练习薄弱点", "params": {"kp_id": "string"}},
                {"tool_name": "create_flashcard", "when_to_use": "用户想记录笔记", "params": {"front_text": "string", "back_text": "string"}},
                {"tool_name": "view_diagnosis", "when_to_use": "用户询问学习状态", "params": {}},
            ],
            "response_style_hint": response_style_hint,
            "should_avoid_proactive_suggestions": profile.fatigue_score > 0.7,
        }

        # 6. 发布事件
        if event_bus:
            try:
                await event_bus.publish(ConversationContextInjected(
                    user_id=user_id,
                    source_module="secretary",
                    conv_id=conv_id,
                    injection_type="learning_state",
                    payload=payload,
                ))
            except Exception as e:
                logger.debug("ConversationContextInjected 发布失败: %s", e)

        return payload
