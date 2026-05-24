"""内置模块: 复习提醒 (ReviewReminder)

功能: 定时检查需要复习的知识点，推送温习建议
触发条件:
  - 存在掌握度下降 > 15% 的知识点
  - 停滞天数 > 3 天
  - 遗忘风险 > 0.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..models import Proposal, ScopedInsight, SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


class ReviewReminderModule(SecretaryModule):
    """复习提醒模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="review_reminder",
            display_name="复习提醒",
            emoji="🔁",
            description="定期提醒复习已学知识点，防止遗忘",
            default_enabled=True,
            run_interval_seconds=600,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """检查是否需要复习提醒"""
        from ...analysis import find_overdue_reviews, detect_stagnant_topics
        from ...models import ScopeSpec, AnalyzeOptions

        options = AnalyzeOptions(threshold=0.4, max_items=5, sort_by="urgency")
        scope = ScopeSpec(level="user")

        proposals: list[Proposal] = []

        # 1. 复习到期项
        try:
            overdue = find_overdue_reviews(user_id, scope, options)
            for item in overdue.items[:3]:
                urgency = round(item.norm_urgency * 10, 1)
                proposals.append(Proposal(
                    emoji="📖",
                    title=f"复习提醒: {item.label}",
                    description=f"已停滞 {item.primary_value:.0f} 天，紧迫度 {urgency}/10。建议安排 15 分钟快速回顾",
                    action_type="review",
                    priority=4 if item.norm_urgency > 0.7 else 3,
                    payload={
                        "kp_id": item.node_id,
                        "urgency": item.norm_urgency,
                        "stagnation_days": item.primary_value,
                    },
                    insight_source="find_overdue_reviews",
                ))
        except Exception as e:
            logger.debug("复习到期检查: %s", e)

        # 2. 停滞知识点
        try:
            stagnant = detect_stagnant_topics(user_id, scope, options)
            for item in stagnant.items[:2]:
                if item.norm_urgency > 0.5:
                    proposals.append(Proposal(
                        emoji="⏰",
                        title=f"停滞知识点: {item.label}",
                        description="多天未练习，建议安排专题复习",
                        action_type="review",
                        priority=3,
                        payload={
                            "kp_id": item.node_id,
                            "stagnation_days": item.primary_value,
                        },
                        insight_source="detect_stagnant_topics",
                    ))
        except Exception as e:
            logger.debug("停滞知识点检查: %s", e)

        return proposals
