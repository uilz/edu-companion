"""秘书事件处理器 — 订阅领域事件，驱动诊断与情境更新

订阅事件:
  - CognitiveNodeUpdated → 触发学习路径调整
  - SessionCompleted    → 更新认知负荷统计 + 疲劳检查

使用方式:
    from app.infrastructure.event_bus import EventBus
    from domain.secretary.engines.secretary_event_handler import secretary_event_handler
    secretary_event_handler.subscribe(bus)
"""

from __future__ import annotations

import logging
from typing import Any

from shared.events import (
    CognitiveNodeUpdated,
    DomainEvent,
    SessionCompleted,
    PracticeSubmitted,
)

logger = logging.getLogger(__name__)


class SecretaryEventHandler:
    """秘书事件处理器 — 订阅学习事件，驱动诊断与主动服务"""

    def __init__(self, store=None) -> None:
        self._bus = None
        self._subscribed = False
        self._store = store

    def subscribe(self, bus: Any) -> None:
        """订阅 EventBus 上的相关事件"""
        if self._subscribed:
            return
        self._bus = bus

        # 运行时类型检查 — 接受 EventBus 及 PersistentEventBus
        from app.infrastructure.event_bus import EventBus
        from app.infrastructure.persistent_event_bus import PersistentEventBus
        if not isinstance(bus, (EventBus, PersistentEventBus)):
            logger.warning("传入的对象不是 EventBus 实例（%s），跳过订阅",
                           type(bus).__module__)
            return

        bus.subscribe("SessionCompleted", self._on_session_completed)
        bus.subscribe("CognitiveNodeUpdated", self._on_cognitive_updated)
        bus.subscribe("PracticeSubmitted", self._on_practice_submitted)
        self._subscribed = True
        logger.info("📡 秘书已订阅领域事件: SessionCompleted / CognitiveNodeUpdated / PracticeSubmitted")

    def unsubscribe(self) -> None:
        """取消订阅"""
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("SessionCompleted", self._on_session_completed)
        self._bus.unsubscribe("CognitiveNodeUpdated", self._on_cognitive_updated)
        self._bus.unsubscribe("PracticeSubmitted", self._on_practice_submitted)
        self._subscribed = False
        logger.info("📡 秘书已取消事件订阅")

    # ── 事件处理器 ──

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
                    if self._store:
                        for p in proposals:
                            self._store.save_proposal(p, user_id=event.user_id,
                                                      session_id=f"session:{event.event_id}")
                    logger.info("会话完成触发疲劳建议: user=%s %d条", event.user_id, len(proposals))
        except Exception as e:
            logger.debug("会话完成处理失败: %s", e)

        # 行为触发 — 会话完成反思提案
        try:
            from .behavior_trigger import on_session_completed
            proposal = await on_session_completed(
                user_id=event.user_id,
                accuracy=event.accuracy,
                duration_minutes=event.duration_minutes,
                session_id=getattr(event, "event_id", ""),
            )
            if proposal:
                if self._store:
                    self._store.save_proposal(proposal, user_id=event.user_id,
                                              session_id=f"session:{getattr(event, 'event_id', '')}")
                logger.info("会话完成行为触发: user=%s proposal=%s", event.user_id, proposal.title)
        except Exception as e:
            logger.debug("会话完成行为触发失败: %s", e)

    async def _on_practice_submitted(self, event: DomainEvent) -> None:
        """练习提交事件 → 低正确率时生成复习提案"""
        if not isinstance(event, PracticeSubmitted):
            return

        payload = getattr(event, 'payload', {}) or {}
        correctness = getattr(event, 'correctness', payload.get('correctness', 0.0))
        atom_node_ids = getattr(event, 'atom_node_ids', payload.get('atom_node_ids', []))
        logger.debug("练习提交: user=%s correctness=%.2f nodes=%d",
                     event.user_id, correctness, len(atom_node_ids))

        try:
            from .behavior_trigger import on_practice_submitted
            proposal = await on_practice_submitted(
                user_id=event.user_id,
                atom_node_ids=atom_node_ids,
                correctness=correctness,
            )
            if proposal:
                if self._store:
                    self._store.save_proposal(proposal, user_id=event.user_id,
                                              session_id=f"practice:{getattr(event, 'event_id', '')}")
                logger.info("练习行为触发: user=%s proposal=%s", event.user_id, proposal.title)
        except Exception as e:
            logger.debug("练习行为触发失败: %s", e)

    async def _on_cognitive_updated(self, event: DomainEvent) -> None:
        """CognitiveNode 更新事件 → 触发学习路径调整"""
        if not isinstance(event, CognitiveNodeUpdated):
            return

        logger.debug("CognitiveNode 更新: user=%s label=%s %.3f→%.3f",
                     event.user_id, event.label,
                     event.proficiency_before, event.proficiency_after)

        try:
            from .secretary_plan_bridge import plan_bridge
            await plan_bridge.planner.generate(
                event.user_id,
                reason=f"cognitive_update:{event.label}:{event.proficiency_before:.2f}→{event.proficiency_after:.2f}",
            )
        except Exception as e:
            logger.debug("计划调整失败: %s", e)


# ── 全局实例 ──
secretary_event_handler = SecretaryEventHandler()
