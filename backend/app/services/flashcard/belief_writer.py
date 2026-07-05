"""
BeliefWriter — 复习自评结果回写 CognitiveNode.Belief

依据 docs/modules/flashcard/events.md §3.2 / §3.4 / ADR 0002 决策 1, 3, 4:

- 触发器: FlashCardReviewed 事件
- 行为: 对每个 linked_node_id, 按 node_link_roles 计算权重:
    - primary   → 1.0 权重
    - secondary → 0.3 权重
- 实际 Belief 增量 = 0.1 * 权重
- 仅自评 "difficult"(困难) / "easy"(简单) 时更新, "good"(良好) 不更新
- 通过 CognitiveNodeLinked 事件通知, 不直接调用 CognitiveNodeUpdated
- 错题卡 (source='practice_error'): 自评 easy → 联动 ErrorBookEntry.is_resolved
- 不直接 UPDATE knowledge_nodes.belief, 而是发布事件让知识图谱消费者执行
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from shared.events import (
    CognitiveNodeLinked,
    FlashCardReviewed,
    ErrorBookEntryReviewed,
    ErrorBookEntryResolved,
)

logger = logging.getLogger(__name__)

# ── 权重表 (依据 events.md §3.2) ─────────────────────────────────────

PRIMARY_WEIGHT = 1.0
SECONDARY_WEIGHT = 0.3
BASE_CONTRIBUTION = 0.1            # 复习自评最大贡献 (weight=1.0 时)


class BeliefWriter:
    """
    FlashCardReviewed → CognitiveNode.Belief 增量更新 (经事件总线)

    设计原则:
    - 不直接写 knowledge_nodes.belief 字段 (避免与 cognitive engine 冲突)
    - 通过 CognitiveNodeLinked(target_ref_type='flashcard', action='updated')
      通知知识图谱消费者执行 update_belief_from_evidence
    - 错题卡 (source='practice_error'): 额外发布 ErrorBookEntryResolved (easy 时)
    """

    def __init__(self, event_bus=None):
        self._bus = event_bus  # 延迟注入, 避免循环导入

    def set_event_bus(self, event_bus) -> None:
        self._bus = event_bus

    @staticmethod
    def compute_node_weights(event: FlashCardReviewed) -> list[tuple[str, float]]:
        """为每个 linked_node_id 计算权重 (primary=1.0, secondary=0.3, 默认 0.3)"""
        weights: list[tuple[str, float]] = []
        for node_id in event.linked_node_ids:
            role = event.node_link_roles.get(node_id, "secondary")
            weight = PRIMARY_WEIGHT if role == "primary" else SECONDARY_WEIGHT
            weights.append((node_id, weight))
        return weights

    @classmethod
    def compute_belief_delta(cls, event: FlashCardReviewed) -> list[dict[str, Any]]:
        """计算每个关联知识点的 Belief 增量

        返回: [{"node_id": ..., "alpha_delta": ..., "beta_delta": ...}, ...]
        "good" 时返回空列表 (不更新 Belief)
        """
        if event.self_assessment == "good":
            return []

        weights = cls.compute_node_weights(event)
        deltas: list[dict[str, Any]] = []
        for node_id, weight in weights:
            contribution = BASE_CONTRIBUTION * weight
            if event.self_assessment == "easy":
                deltas.append({
                    "node_id": node_id,
                    "alpha_delta": contribution,
                    "beta_delta": 0.0,
                })
            elif event.self_assessment == "difficult":
                deltas.append({
                    "node_id": node_id,
                    "alpha_delta": 0.0,
                    "beta_delta": contribution,
                })
        return deltas

    async def write_belief(self, event: FlashCardReviewed) -> list[CognitiveNodeLinked]:
        """
        主入口: 复习事件 → 触发 Belief 回写

        关键设计 (依据 events.md):
        - 通过 CognitiveNodeLinked (不是 CognitiveNodeUpdated) 通知
        - 不直接 UPDATE knowledge_nodes.belief
        - 知识图谱消费者订阅 CognitiveNodeLinked 后调用 update_belief_from_evidence
        """
        if self._bus is None:
            logger.warning("BeliefWriter.event_bus 未注入, 跳过 Belief 回写")
            return []

        if event.self_assessment == "good":
            logger.debug(
                "FlashCardReviewed self_assessment=good, 不更新 Belief (card_id=%s)",
                event.card_id,
            )
            return []

        deltas = self.compute_belief_delta(event)
        if not deltas:
            return []

        published: list[CognitiveNodeLinked] = []
        for d in deltas:
            link_event = CognitiveNodeLinked(
                user_id=event.user_id,
                node_id=d["node_id"],
                link_type="flashcard_review",
                target_ref_type="flashcard",
                target_ref_id=event.card_id,
                action="updated",
            )
            try:
                await self._bus.publish(link_event)
                published.append(link_event)
                logger.info(
                    "📊 Belief 回写: card=%s node=%s alpha+=%s beta+=%s (assessment=%s)",
                    event.card_id, d["node_id"], d["alpha_delta"], d["beta_delta"],
                    event.self_assessment,
                )
            except Exception:
                logger.exception("发布 CognitiveNodeLinked 失败: node=%s", d["node_id"])

        return published

    async def sync_error_book(
        self,
        event: FlashCardReviewed,
        card: dict[str, Any] | None = None,
    ) -> list[ErrorBookEntryReviewed | ErrorBookEntryResolved]:
        """
        错题卡双向同步 (events.md §3.4):
        - 自评 difficult → 不更新 ErrorBookEntry (只 review_count++)
        - 自评 good      → review_count++, is_resolved 保持
        - 自评 easy      → is_resolved = true

        识别条件: source='practice_error' OR 存在 error_book_entry_id
        """
        if self._bus is None:
            return []
        if not card:
            return []
        # 错题卡识别: source 字段 或 绑定错题条目
        is_practice_error = (
            card.get("source") == "practice_error"
            or bool(card.get("error_book_entry_id"))
            or card.get("cross_module_source") == "practice_error"
        )
        if not is_practice_error:
            return []
        error_entry_id = card.get("error_book_entry_id")
        if not error_entry_id:
            return []

        published = []
        # 总是发送 ErrorBookEntryReviewed (review_count 增量)
        reviewed = ErrorBookEntryReviewed(
            user_id=event.user_id,
            error_entry_id=error_entry_id,
            self_assessment=event.self_assessment,
            review_count=int(card.get("review_count", 0)) + 1,
            is_resolved=card.get("is_resolved", False),
        )
        try:
            await self._bus.publish(reviewed)
            published.append(reviewed)
        except Exception:
            logger.exception("发布 ErrorBookEntryReviewed 失败: error_entry=%s", error_entry_id)

        # easy 时额外发送 Resolved
        if event.self_assessment == "easy":
            resolved = ErrorBookEntryResolved(
                user_id=event.user_id,
                error_entry_id=error_entry_id,
                resolution_method="auto_after_review",
            )
            try:
                await self._bus.publish(resolved)
                published.append(resolved)
                logger.info("✅ 错题卡 easy → 标记 ErrorBookEntry.is_resolved: %s", error_entry_id)
            except Exception:
                logger.exception("发布 ErrorBookEntryResolved 失败: error_entry=%s", error_entry_id)

        return published


# ── 全局单例 ──

_writer: BeliefWriter | None = None


def get_belief_writer() -> BeliefWriter:
    global _writer
    if _writer is None:
        _writer = BeliefWriter()
    return _writer
