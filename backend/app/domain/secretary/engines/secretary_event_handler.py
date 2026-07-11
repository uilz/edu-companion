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
    PlanItemRequested,
    PlanItemSuggested,
    PracticeAnswerBehaviorRecorded,
    ProposalGenerated,
    SessionCompleted,
)

logger = logging.getLogger(__name__)


class SecretaryEventHandler:
    """秘书事件处理器 — 订阅学习事件，驱动诊断与主动服务"""

    def __init__(self, store=None) -> None:
        self._bus = None
        self._subscribed = False
        self._store = store
        self._silent_task_manager = None

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
        bus.subscribe("PlanItemSuggested", self._on_plan_item_suggested)
        self._subscribed = True
        logger.info("📡 秘书已订阅领域事件: SessionCompleted / CognitiveNodeMetadataChanged / AnswerSubmitted / ConversationNoteCreatedAsFlashcard / PracticeAnswerBehaviorRecorded / PlanItemSuggested")

    def unsubscribe(self) -> None:
        """取消订阅"""
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("SessionCompleted", self._on_session_completed)
        self._bus.unsubscribe("CognitiveNodeMetadataChanged", self._on_cognitive_metadata_changed)
        self._bus.unsubscribe("AnswerSubmitted", self._on_answer_submitted)
        self._bus.unsubscribe("ConversationNoteCreatedAsFlashcard", self._on_conversation_note_created_as_flashcard)
        self._bus.unsubscribe("PracticeAnswerBehaviorRecorded", self._on_practice_behavior_recorded)
        self._bus.unsubscribe("PlanItemSuggested", self._on_plan_item_suggested)
        self._subscribed = False
        logger.info("📡 秘书已取消事件订阅")

    # ── 内部工具 ──

    async def _schedule_silent_task(
        self,
        user_id: str,
        task_type: str,
        payload: dict | None = None,
        caused_by_event_id: str | None = None,
    ) -> None:
        """调度静默后台任务（不阻塞事件处理）"""
        if not self._silent_task_manager:
            return
        try:
            await self._silent_task_manager.schedule(
                user_id=user_id,
                task_type=task_type,
                payload=payload or {},
                caused_by_event_id=caused_by_event_id,
            )
        except Exception as e:
            logger.debug("调度静默任务失败: %s", e)

    async def _save_and_publish_proposal(
        self,
        proposal: Any,
        user_id: str,
        session_id: str | None = None,
        caused_by_event_id: str | None = None,
    ) -> str | None:
        """保存提案并发布 ProposalGenerated 事件"""
        if not self._store:
            return None

        # 补充因果链
        if caused_by_event_id and not proposal.caused_by_event_id:
            proposal.caused_by_event_id = caused_by_event_id

        proposal_id = self._store.save_proposal(proposal, user_id=user_id, session_id=session_id)

        # 发布 ProposalGenerated 事件
        if self._bus:
            try:
                await self._bus.publish(ProposalGenerated(
                    user_id=user_id,
                    source_module="secretary",
                    source_id=proposal_id,
                    proposal_id=proposal_id,
                    action_type=proposal.action_type,
                    target_module=proposal.payload.get("target_module", "") if proposal.payload else "",
                    target_ref_id=proposal.payload.get("target_ref_id", "") if proposal.payload else "",
                    title=proposal.title,
                    description=proposal.description,
                    priority=proposal.priority,
                    insight_source=proposal.insight_source or "",
                    linked_node_ids=proposal.payload.get("linked_node_ids", []) if proposal.payload else [],
                    payload=proposal.payload or {},
                    caused_by_event_id=proposal.caused_by_event_id,
                ))
            except Exception as e:
                logger.debug("ProposalGenerated 发布失败: %s", e)

        return proposal_id

    async def _request_plan_item(
        self,
        user_id: str,
        title: str,
        description: str,
        target_type: str,
        target_ref_id: str,
        linked_node_ids: list[str],
        triggered_by_proposal_id: str | None = None,
        requires_user_confirmation: bool = True,
        estimated_minutes: int = 10,
        priority: int = 2,
        proposed_scheduled_for: Any | None = None,
        request_id: str | None = None,
        suggestion_id: str | None = None,
    ) -> None:
        """向规划壳发布 PlanItemRequested 事件"""
        if not self._bus:
            return
        try:
            from uuid import uuid4
            metadata: dict[str, Any] = {"requested_by": "secretary"}
            if triggered_by_proposal_id:
                metadata["triggered_by_proposal_id"] = triggered_by_proposal_id
            if suggestion_id:
                metadata["suggestion_id"] = suggestion_id

            await self._bus.publish(PlanItemRequested(
                user_id=user_id,
                source_module="secretary",
                request_id=request_id or str(uuid4())[:12],
                target_type=target_type,
                target_ref_id=target_ref_id,
                title=title,
                description=description,
                priority=priority,
                linked_node_ids=linked_node_ids,
                requires_user_confirmation=requires_user_confirmation,
                estimated_minutes=estimated_minutes,
                proposed_scheduled_for=proposed_scheduled_for,
                metadata=metadata,
            ))
        except Exception as e:
            logger.debug("PlanItemRequested 发布失败: %s", e)

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
                    for p in proposals:
                        await self._save_and_publish_proposal(
                            p,
                            user_id=event.user_id,
                            session_id=f"session:{event.event_id}",
                            caused_by_event_id=getattr(event, "event_id", None),
                        )
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
                await self._save_and_publish_proposal(
                    proposal,
                    user_id=event.user_id,
                    session_id=f"session:{getattr(event, 'event_id', '')}",
                    caused_by_event_id=getattr(event, "event_id", None),
                )
                logger.info("会话完成行为触发: user=%s proposal=%s", event.user_id, proposal.title)
        except Exception as e:
            logger.debug("会话完成行为触发失败: %s", e)

        # 静默预计算：会话结束后生成每日简报与诊断
        try:
            await self._schedule_silent_task(
                user_id=event.user_id,
                task_type="generate_daily_brief",
                caused_by_event_id=getattr(event, "event_id", None),
            )
            await self._schedule_silent_task(
                user_id=event.user_id,
                task_type="compute_diagnosis",
                caused_by_event_id=getattr(event, "event_id", None),
            )
        except Exception as e:
            logger.debug("会话完成后调度静默任务失败: %s", e)

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
                await self._save_and_publish_proposal(
                    proposal,
                    user_id=event.user_id,
                    session_id=f"practice:{getattr(event, 'event_id', '')}",
                    caused_by_event_id=getattr(event, "event_id", None),
                )
                logger.info("练习行为触发: user=%s proposal=%s", event.user_id, proposal.title)
        except Exception as e:
            logger.debug("练习行为触发失败: %s", e)

        # 静默预计算：答题后准备复习列表
        try:
            await self._schedule_silent_task(
                user_id=event.user_id,
                task_type="prepare_review_list",
                payload={"source": "answer_submitted", "node_ids": atom_node_ids},
                caused_by_event_id=getattr(event, "event_id", None),
            )
            if not event.is_correct and atom_node_ids:
                await self._schedule_silent_task(
                    user_id=event.user_id,
                    task_type="pre_generate_quiz",
                    payload={"source": "answer_submitted", "kp_id": atom_node_ids[0]},
                    caused_by_event_id=getattr(event, "event_id", None),
                )
        except Exception as e:
            logger.debug("答题后调度静默任务失败: %s", e)

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

        # 静默预计算：认知状态变化后重新计算诊断
        try:
            await self._schedule_silent_task(
                user_id=event.user_id,
                task_type="compute_diagnosis",
                payload={"source": "cognitive_metadata_changed", "node_id": event.node_id},
                caused_by_event_id=getattr(event, "event_id", None),
            )
        except Exception as e:
            logger.debug("认知元数据变化后调度静默任务失败: %s", e)

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
            proposal_id = await self._save_and_publish_proposal(
                proposal,
                user_id=event.user_id,
                session_id=f"note:{event.note_id}",
                caused_by_event_id=getattr(event, "event_id", None),
            )
            logger.info("对话笔记转闪卡触发计划提案: user=%s note=%s", event.user_id, event.note_id)

            # 同时向规划壳请求创建复习计划项
            await self._request_plan_item(
                user_id=event.user_id,
                title=f"复习闪卡：{front_preview}...",
                description=f"从对话创建的闪卡「{front_preview}...」，建议安排复习。",
                target_type="flashcard",
                target_ref_id=event.flashcard_id or event.note_id,
                linked_node_ids=list(event.linked_node_ids or []),
                triggered_by_proposal_id=proposal_id or "",
                requires_user_confirmation=False,
            )
        except Exception as e:
            logger.debug("对话笔记转闪卡提案生成失败: %s", e)

        # 静默预计算：新闪卡加入复习列表
        try:
            await self._schedule_silent_task(
                user_id=event.user_id,
                task_type="prepare_review_list",
                payload={"source": "conversation_note_flashcard", "note_id": event.note_id},
                caused_by_event_id=getattr(event, "event_id", None),
            )
        except Exception as e:
            logger.debug("对话笔记转闪卡后调度静默任务失败: %s", e)

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
                await self._save_and_publish_proposal(
                    proposal,
                    user_id=event.user_id,
                    session_id=f"behavior:{event.attempt_id}",
                    caused_by_event_id=getattr(event, "event_id", None),
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
                await self._save_and_publish_proposal(
                    proposal,
                    user_id=event.user_id,
                    session_id=f"behavior:{event.attempt_id}",
                    caused_by_event_id=getattr(event, "event_id", None),
                )
                logger.info("多次改选触发练习提案: user=%s attempt=%s", event.user_id, event.attempt_id)

            # 静默预计算：微行为异常时预生成针对测验
            if event.question_id:
                await self._schedule_silent_task(
                    user_id=event.user_id,
                    task_type="pre_generate_quiz",
                    payload={"source": "practice_behavior", "question_id": event.question_id},
                    caused_by_event_id=getattr(event, "event_id", None),
                )
        except Exception as e:
            logger.debug("答题微行为提案生成失败: %s", e)

    async def _on_plan_item_suggested(self, event: DomainEvent) -> None:
        """规划壳主动建议 → 秘书编排器决策后发布 PlanItemRequested

        策略：
        - 疲劳度高时跳过非紧急建议（priority >= 3）
        - pending confirmation 超过上限时暂停新建议
        - 同一 suggestion_id 幂等去重
        - 所有请求默认需要用户确认
        """
        if not isinstance(event, PlanItemSuggested):
            return

        user_id = event.user_id
        suggestion_id = event.suggestion_id

        logger.debug(
            "收到 PlanItemSuggested: user=%s suggestion_id=%s target=%s reason=%s",
            user_id, suggestion_id, event.target_type, event.reason,
        )

        try:
            from app.api.planning import service as svc

            # 幂等去重：同一 suggestion_id 不重复发起请求
            existing = svc.find_confirmation_by_suggestion_id(user_id, suggestion_id)
            if existing:
                logger.debug("PlanItem suggestion_id=%s 已存在 confirmation，跳过", suggestion_id)
                return

            # 策略 1：疲劳过滤
            priority = event.priority
            try:
                from app.domain.secretary.analysis import predict_fatigue_risk
                fatigue = predict_fatigue_risk(user_id)
                if fatigue.get("risk_level") == "high" and priority >= 3:
                    logger.debug(
                        "用户疲劳度高，跳过非紧急建议: user=%s suggestion_id=%s",
                        user_id, suggestion_id,
                    )
                    return
            except Exception as e:
                logger.debug("疲劳评估失败，继续处理: %s", e)

            # 策略 2：pending confirmation 上限
            try:
                pending_count = svc.count_pending_confirmations(user_id)
                if pending_count >= 20:
                    logger.debug(
                        "pending confirmation 已达上限 %d，跳过建议: user=%s",
                        pending_count, user_id,
                    )
                    return
            except Exception as e:
                logger.debug("pending confirmation 计数失败，继续处理: %s", e)

            # 发布 PlanItemRequested，request_id 与 suggestion_id 绑定保证幂等
            await self._request_plan_item(
                user_id=user_id,
                title=event.title,
                description=event.description,
                target_type=event.target_type,
                target_ref_id=event.target_ref_id,
                linked_node_ids=list(event.linked_node_ids or []),
                requires_user_confirmation=True,
                estimated_minutes=event.estimated_minutes or 10,
                priority=priority,
                proposed_scheduled_for=event.proposed_scheduled_for,
                request_id=f"req_{suggestion_id}",
                suggestion_id=suggestion_id,
            )
            logger.info(
                "已将 PlanItemSuggested 转为 PlanItemRequested: user=%s suggestion_id=%s",
                user_id, suggestion_id,
            )
        except Exception as e:
            logger.debug("处理 PlanItemSuggested 失败: %s", e)


# ── 全局实例 ──
secretary_event_handler = SecretaryEventHandler()
