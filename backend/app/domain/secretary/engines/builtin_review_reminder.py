"""内置模块: 复习提醒 (ReviewReminder)

功能: 定时检查需要复习的知识点，推送温习建议
触发条件:
  - 存在掌握度下降 > 15% 的知识点
  - 停滞天数 > 3 天
  - 遗忘风险 > 0.4
"""

from __future__ import annotations

import logging

from ..models import Proposal
from .context_engine import SessionContext
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
        from ..analysis import _get_nodes, find_overdue_reviews, detect_stagnant_topics

        nodes = _get_nodes(user_id)
        proposals: list[Proposal] = []

        # 1. 复习到期项
        try:
            overdue = find_overdue_reviews(user_id, nodes=nodes)
            for item in overdue[:3]:
                urgency = item.get("urgency", 0)
                mastery = item.get("mastery", 0)
                urgency_score = round(urgency * 10, 1)
                stale_days = round((1 - mastery / 100) * 30, 0) if mastery else 0
                proposals.append(Proposal(
                    emoji="📖",
                    title=f"复习提醒: {item.get('label', '')}",
                    description=f"紧迫度 {urgency_score}/10，掌握度 {mastery}%。建议安排 15 分钟快速回顾",
                    action_type="review",
                    priority=4 if urgency > 0.7 else 3,
                    payload={
                        "kp_id": item.get("node_id", ""),
                        "urgency": urgency,
                        "mastery": mastery,
                    },
                    insight_source="find_overdue_reviews",
                ))
        except Exception as e:
            logger.debug("复习到期检查: %s", e)

        # 2. 停滞知识点
        try:
            stagnant = detect_stagnant_topics(user_id, nodes=nodes)
            for item in stagnant[:2]:
                days_since = item.get("days_since", 0)
                if days_since > 5:
                    proposals.append(Proposal(
                        emoji="⏰",
                        title=f"停滞知识点: {item.get('label', '')}",
                        description=f"已 {days_since:.0f} 天未练习，建议安排专题复习",
                        action_type="review",
                        priority=3,
                        payload={
                            "kp_id": item.get("node_id", ""),
                            "stagnation_days": days_since,
                        },
                        insight_source="detect_stagnant_topics",
                    ))
        except Exception as e:
            logger.debug("停滞知识点检查: %s", e)

        return proposals
