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
