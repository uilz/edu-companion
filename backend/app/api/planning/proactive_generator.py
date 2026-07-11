"""PlanningProactiveGenerator — 规划壳主动发现学习机会并向秘书建议建项

订阅：
  - CognitiveNodeMetadataChanged: 节点掌握度/调度变化 → 复习建议
  - SessionCompleted: 练习会话结束 → 针对性练习/横向拓展建议
  - FlashCardReviewed: 闪卡复习困难 → 再次复习建议
  - PlanGoalCreated: 新目标 → 目标拆解建议

不直接创建 plan item，而是发布 PlanItemSuggested 事件，由秘书编排器统一决策。
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from shared.events import (
    CognitiveNodeMetadataChanged,
    PlanItemSuggested,
    SessionCompleted,
)

logger = logging.getLogger(__name__)


class PlanningProactiveGenerator:
    """规划壳主动生成计划项建议"""

    def __init__(self) -> None:
        self._bus: Any | None = None
        self._subscribed = False

    def subscribe(self, bus: Any) -> None:
        if self._subscribed:
            return
        self._bus = bus
        bus.subscribe("CognitiveNodeMetadataChanged", self._on_cognitive_metadata_changed)
        bus.subscribe("SessionCompleted", self._on_session_completed)
        logger.info("PlanningProactiveGenerator: subscribed to CognitiveNodeMetadataChanged / SessionCompleted")

    def unsubscribe(self) -> None:
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("CognitiveNodeMetadataChanged", self._on_cognitive_metadata_changed)
        self._bus.unsubscribe("SessionCompleted", self._on_session_completed)
        self._subscribed = False
        logger.info("PlanningProactiveGenerator: unsubscribed")

    async def _publish_suggestion(self, suggestion: PlanItemSuggested) -> None:
        if not self._bus:
            return
        try:
            await self._bus.publish(suggestion)
            logger.debug(
                "已发布 PlanItemSuggested: user=%s suggestion_id=%s target=%s reason=%s",
                suggestion.user_id, suggestion.suggestion_id, suggestion.target_type, suggestion.reason,
            )
        except Exception as e:
            logger.debug("PlanItemSuggested 发布失败: %s", e)

    async def _on_cognitive_metadata_changed(self, event: Any) -> None:
        if not isinstance(event, CognitiveNodeMetadataChanged):
            return

        user_id = event.user_id
        node_id = event.node_id

        # 仅当变更字段与掌握度/调度相关时才处理
        relevant_fields = {"belief", "scheduling", "proficiency_mean", "next_review", "mastery_level"}
        if not relevant_fields.intersection(set(event.changed_fields or [])):
            return

        try:
            from app.domain.cognitive import get_repo
            repo = get_repo()
            node = repo.get_node(node_id, user_id)
            if not node:
                return

            proficiency = node.proficiency
            next_review = node.scheduling.next_review if node.scheduling else 0
            now = time.time()

            # 规则 1：掌握度低于阈值 → 建议复习
            if proficiency < 0.5:
                await self._publish_suggestion(PlanItemSuggested(
                    user_id=user_id,
                    source_module="planning",
                    suggestion_id=f"sug_{uuid4().hex[:12]}",
                    trigger_event_type="CognitiveNodeMetadataChanged",
                    trigger_event_id=getattr(event, "event_id", ""),
                    target_type="review",
                    target_ref_id=node_id,
                    title=f"复习薄弱知识点：{node.label or node_id}",
                    description=f"该知识点掌握度为 {proficiency:.0%}，建议安排复习。",
                    priority=3,
                    estimated_minutes=15,
                    linked_node_ids=[node_id],
                    reason="low_mastery",
                ))

            # 规则 2：进入复习窗口 → 建议复习
            elif next_review > 0 and next_review <= now:
                await self._publish_suggestion(PlanItemSuggested(
                    user_id=user_id,
                    source_module="planning",
                    suggestion_id=f"sug_{uuid4().hex[:12]}",
                    trigger_event_type="CognitiveNodeMetadataChanged",
                    trigger_event_id=getattr(event, "event_id", ""),
                    target_type="review",
                    target_ref_id=node_id,
                    title=f"复习到期知识点：{node.label or node_id}",
                    description="该知识点已到复习时间。",
                    priority=2,
                    estimated_minutes=10,
                    linked_node_ids=[node_id],
                    reason="review_due",
                ))
        except Exception as e:
            logger.debug("处理 CognitiveNodeMetadataChanged 生成计划建议失败: %s", e)

    async def _on_session_completed(self, event: Any) -> None:
        if not isinstance(event, SessionCompleted):
            return

        user_id = event.user_id
        accuracy = event.accuracy
        duration = event.duration_minutes

        # 规则 1：低正确率 → 建议复习薄弱点
        if accuracy < 0.5:
            await self._publish_suggestion(PlanItemSuggested(
                user_id=user_id,
                source_module="planning",
                suggestion_id=f"sug_{uuid4().hex[:12]}",
                trigger_event_type="SessionCompleted",
                trigger_event_id=getattr(event, "event_id", event.session_id),
                target_type="practice",
                target_ref_id=event.session_id,
                title="练习薄弱知识点",
                description=f"本次练习正确率 {accuracy:.0%}，建议针对性复习后再练习。",
                priority=3,
                estimated_minutes=20,
                linked_node_ids=[],
                reason="low_accuracy_session",
            ))

        # 规则 2：高正确率且时长足够 → 建议横向拓展
        if accuracy >= 0.8 and duration >= 20:
            await self._publish_suggestion(PlanItemSuggested(
                user_id=user_id,
                source_module="planning",
                suggestion_id=f"sug_{uuid4().hex[:12]}",
                trigger_event_type="SessionCompleted",
                trigger_event_id=getattr(event, "event_id", event.session_id),
                target_type="explore",
                target_ref_id=event.session_id,
                title="横向拓展相关知识点",
                description=f"本次练习正确率 {accuracy:.0%}，表现良好，可探索相关主题。",
                priority=1,
                estimated_minutes=25,
                linked_node_ids=[],
                reason="high_accuracy_expansion",
            ))


# 全局单例
planning_proactive_generator = PlanningProactiveGenerator()
