"""秘书事件处理器 — 订阅领域事件，驱动诊断与情境更新

订阅事件:
  - AnswerSubmitted     → 错题驱动诊断刷新
  - SessionCompleted    → 更新认知负荷统计 + 疲劳检查
  - KnowledgeStateUpdated → 触发学习路径调整

使用方式:
    from app.infra.event_bus import EventBus
    from domain.secretary.engines.secretary_event_handler import secretary_event_handler
    secretary_event_handler.subscribe(bus)
"""

from __future__ import annotations

import logging
from typing import Any

from app.shared.events import (
    AnswerSubmitted,
    DomainEvent,
    KnowledgeStateUpdated,
    SessionCompleted,
)

logger = logging.getLogger(__name__)


class SecretaryEventHandler:
    """秘书事件处理器 — 订阅学习事件，驱动诊断与主动服务"""

    def __init__(self) -> None:
        self._bus = None
        self._subscribed = False

    def subscribe(self, bus: Any) -> None:
        """订阅 EventBus 上的相关事件"""
        if self._subscribed:
            return
        self._bus = bus

        from app.infra.event_bus import EventBus
        if not isinstance(bus, EventBus):
            logger.warning("传入的对象不是 EventBus 实例，跳过订阅")
            return

        bus.subscribe("AnswerSubmitted", self._on_answer_submitted)
        bus.subscribe("SessionCompleted", self._on_session_completed)
        bus.subscribe("KnowledgeStateUpdated", self._on_knowledge_updated)
        self._subscribed = True
        logger.info("📡 秘书已订阅领域事件: AnswerSubmitted / SessionCompleted / KnowledgeStateUpdated")

    def unsubscribe(self) -> None:
        """取消订阅"""
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("AnswerSubmitted", self._on_answer_submitted)
        self._bus.unsubscribe("SessionCompleted", self._on_session_completed)
        self._bus.unsubscribe("KnowledgeStateUpdated", self._on_knowledge_updated)
        self._subscribed = False
        logger.info("📡 秘书已取消事件订阅")

    # ── 事件处理器 ──

    async def _on_answer_submitted(self, event: DomainEvent) -> None:
        """答题提交事件 → 如果答错，触发诊断刷新 + 弱项检测"""
        if not isinstance(event, AnswerSubmitted):
            return
        if event.is_correct:
            return  # 答对不触发

        logger.debug("答题错误触发诊断: user=%s skill=%s", event.user_id, event.skill_id)

        try:
            from ...secretary_service import SecretaryService
            from ...proposal_store import ProposalStore

            service = SecretaryService()
            store = ProposalStore()

            # 快速诊断
            report = await service.diagnose(user_id=event.user_id)

            if report.weak_points:
                # 为前 2 个薄弱点生成提案
                proposals = service.suggest(report=report, max_proposals=2)
                for p in proposals:
                    store.save_proposal(p, user_id=event.user_id, session_id=f"event:{event.event_id}")

                # 黑板推送
                await service.push_to_blackboard(f"event:{event.event_id}", proposals, report)
                logger.info("错题诊断完成: user=%s 生成 %d 条提案", event.user_id, len(proposals))
        except Exception as e:
            logger.debug("错题诊断失败(可能是冷启动): %s", e)

    async def _on_session_completed(self, event: DomainEvent) -> None:
        """会话完成事件 → 更新认知负荷 + 检查疲劳信号"""
        if not isinstance(event, SessionCompleted):
            return

        logger.debug("会话完成: user=%s accuracy=%.2f duration=%dmin",
                     event.user_id, event.accuracy, event.duration_minutes)

        try:
            # 低正确率 + 长时间 → 触发疲劳管理
            if event.accuracy < 0.4 and event.duration_minutes > 30:
                from .builtin_fatigue_manager import FatigueManagerModule
                from .context_engine import ContextEngine

                ctx = await ContextEngine().assess(event.user_id)
                fm = FatigueManagerModule()
                proposals = await fm.run_check(event.user_id, ctx)

                if proposals:
                    from ...proposal_store import ProposalStore
                    store = ProposalStore()
                    for p in proposals:
                        store.save_proposal(p, user_id=event.user_id,
                                            session_id=f"session:{event.event_id}")
                    logger.info("会话完成触发疲劳建议: user=%s %d条", event.user_id, len(proposals))
        except Exception as e:
            logger.debug("会话完成处理失败: %s", e)

    async def _on_knowledge_updated(self, event: DomainEvent) -> None:
        """知识状态更新事件 → 触发学习路径调整"""
        if not isinstance(event, KnowledgeStateUpdated):
            return

        logger.debug("知识状态更新: user=%s skill=%s %s→%s",
                     event.user_id, event.skill_id,
                     event.old_mastery, event.new_mastery)

        try:
            from .secretary_plan_bridge import plan_bridge
            await plan_bridge.planner.generate(
                event.user_id,
                reason=f"knowledge_upgrade:{event.skill_id}:{event.old_mastery}→{event.new_mastery}",
            )
        except Exception as e:
            logger.debug("计划调整失败: %s", e)


# ── 全局实例 ──
secretary_event_handler = SecretaryEventHandler()
