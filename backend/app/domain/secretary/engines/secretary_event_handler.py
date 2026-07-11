"""秘书事件处理器 — 订阅领域事件，驱动诊断与情境更新

订阅事件:
  - CognitiveNodeMetadataChanged  → 触发学习路径调整
  - SessionCompleted              → 更新认知负荷统计 + 疲劳检查

使用方式:
    from app.infrastructure.event_bus import EventBus
    from domain.secretary.engines.secretary_event_handler import secretary_event_handler
    secretary_event_handler.subscribe(bus)
"""

from __future__ import annotations

import logging
from typing import Any

from shared.events import (
    AnswerSubmitted,
    CognitiveNodeMetadataChanged,
    ConversationNoteCreatedAsFlashcard,
    DomainEvent,
    PracticeAnswerBehaviorRecorded,
    SessionCompleted,
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
        bus.subscribe("CognitiveNodeMetadataChanged", self._on_cognitive_metadata_changed)
        bus.subscribe("AnswerSubmitted", self._on_answer_submitted)
        bus.subscribe("ConversationNoteCreatedAsFlashcard", self._on_conversation_note_created_as_flashcard)
        bus.subscribe("PracticeAnswerBehaviorRecorded", self._on_practice_behavior_recorded)
        self._subscribed = True
        logger.info("📡 秘书已订阅领域事件: SessionCompleted / CognitiveNodeMetadataChanged / AnswerSubmitted / ConversationNoteCreatedAsFlashcard / PracticeAnswerBehaviorRecorded")

    def unsubscribe(self) -> None:
        """取消订阅"""
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("SessionCompleted", self._on_session_completed)
        self._bus.unsubscribe("CognitiveNodeMetadataChanged", self._on_cognitive_metadata_changed)
        self._bus.unsubscribe("AnswerSubmitted", self._on_answer_submitted)
        self._bus.unsubscribe("ConversationNoteCreatedAsFlashcard", self._on_conversation_note_created_as_flashcard)
        self._bus.unsubscribe("PracticeAnswerBehaviorRecorded", self._on_practice_behavior_recorded)
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

    async def _on_answer_submitted(self, event: DomainEvent) -> None:
        """答题提交事件 → 低正确率时生成复习提案"""
        if not isinstance(event, AnswerSubmitted):
            return

        correctness = 1.0 if event.is_correct else 0.0
        atom_node_ids = event.cognitive_node_ids or []
        logger.debug("答题提交: user=%s correctness=%.2f nodes=%d",
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

    async def _on_cognitive_metadata_changed(self, event: DomainEvent) -> None:
        """CognitiveNode 元数据变化事件 → 触发学习路径调整"""
        if not isinstance(event, CognitiveNodeMetadataChanged):
            return

        logger.debug("CognitiveNode 元数据变化: user=%s node=%s fields=%s",
                     event.user_id, event.node_id, event.changed_fields)

        try:
            from .secretary_plan_bridge import plan_bridge
            await plan_bridge.planner.generate(
                event.user_id,
                reason=f"cognitive_metadata_change:{event.node_id}:{','.join(event.changed_fields)}",
            )
        except Exception as e:
            logger.debug("计划调整失败: %s", e)

    async def _on_conversation_note_created_as_flashcard(self, event: DomainEvent) -> None:
        """对话笔记转闪卡 → 生成复习计划提案"""
        if not isinstance(event, ConversationNoteCreatedAsFlashcard):
            return

        logger.debug("对话笔记转闪卡: user=%s note=%s", event.user_id, event.note_id)

        try:
            from ..models import Proposal
            front_preview = (event.front_text or "")[:30]
            proposal = Proposal(
                emoji="📝",
                title=f"为新闪卡安排复习计划",
                description=f"你刚从对话创建了一张闪卡「{front_preview}...」，是否将其加入今日复习？",
                action_type="planning",
                priority=2,
                payload={
                    "source": "conversation_note_flashcard",
                    "note_id": event.note_id,
                    "flashcard_linked_node_ids": event.linked_node_ids,
                },
                insight_source="conversation_note_created_as_flashcard",
                generated_by="secretary_event_handler",
            )
            if self._store:
                self._store.save_proposal(
                    proposal,
                    user_id=event.user_id,
                    session_id=f"note:{event.note_id}",
                )
                logger.info("对话笔记转闪卡触发计划提案: user=%s note=%s", event.user_id, event.note_id)
        except Exception as e:
            logger.debug("对话笔记转闪卡提案生成失败: %s", e)

    async def _on_practice_behavior_recorded(self, event: DomainEvent) -> None:
        """答题微行为 → 检测到高犹豫/多次改选时生成讲解/复习提案"""
        if not isinstance(event, PracticeAnswerBehaviorRecorded):
            return

        hesitation_ratio = 0.0
        if event.time_on_question_ms > 0:
            hesitation_ratio = event.hesitation_ms / event.time_on_question_ms

        logger.debug("答题微行为: user=%s attempt=%s hesitation=%.2f changes=%d",
                     event.user_id, event.attempt_id, hesitation_ratio, event.answer_change_count)

        try:
            from ..models import Proposal

            if hesitation_ratio > 0.4 and event.time_on_question_ms > 5000:
                proposal = Proposal(
                    emoji="🤔",
                    title="检测到答题犹豫，建议回顾相关概念",
                    description=f"本题答题过程中犹豫时间占比 {hesitation_ratio:.0%}，可能需要重新讲解或练习。",
                    action_type="review",
                    priority=3,
                    payload={
                        "source": "practice_behavior_hesitation",
                        "attempt_id": event.attempt_id,
                        "question_id": event.question_id,
                        "hesitation_ratio": hesitation_ratio,
                    },
                    insight_source="practice_answer_behavior:hesitation",
                    generated_by="secretary_event_handler",
                )
                if self._store:
                    self._store.save_proposal(
                        proposal,
                        user_id=event.user_id,
                        session_id=f"behavior:{event.attempt_id}",
                    )
                    logger.info("答题犹豫触发复习提案: user=%s attempt=%s", event.user_id, event.attempt_id)

            if event.answer_change_count >= 2:
                proposal = Proposal(
                    emoji="🔄",
                    title="多次改选答案，建议辨析易混点",
                    description=f"本题改选 {event.answer_change_count} 次，可能存在选项混淆，建议针对性练习。",
                    action_type="practice",
                    priority=3,
                    payload={
                        "source": "practice_behavior_indecision",
                        "attempt_id": event.attempt_id,
                        "question_id": event.question_id,
                        "answer_change_count": event.answer_change_count,
                    },
                    insight_source="practice_answer_behavior:indecision",
                    generated_by="secretary_event_handler",
                )
                if self._store:
                    self._store.save_proposal(
                        proposal,
                        user_id=event.user_id,
                        session_id=f"behavior:{event.attempt_id}",
                    )
                    logger.info("多次改选触发练习提案: user=%s attempt=%s", event.user_id, event.attempt_id)
        except Exception as e:
            logger.debug("答题微行为提案生成失败: %s", e)


# ── 全局实例 ──
secretary_event_handler = SecretaryEventHandler()
