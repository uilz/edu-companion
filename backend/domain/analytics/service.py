"""
分析引擎领域服务 — 订阅事件而非被同步调用
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.events import AnswerSubmitted

if TYPE_CHECKING:
    from shared.protocols import PracticeService
    from infra.event_bus import EventBus

logger = logging.getLogger("domain.analytics")


class AnalyticsServiceImpl:
    """
    行为分析服务

    不再被 practice 同步调用，而是订阅 AnswerSubmitted 事件。
    """

    def __init__(self, practice: PracticeService, event_bus: EventBus):
        self._practice = practice
        self._bus = event_bus

    async def on_answer_submitted(self, event: AnswerSubmitted) -> None:
        """
        事件处理器: 答题提交 → 更新统计

        异步执行，不影响答题响应速度。
        """
        logger.debug(
            "Analytics: user=%s skill=%s correct=%s p=%.2f→%.2f",
            event.user_id, event.skill_id, event.is_correct,
            event.p_known_before, event.p_known_after
        )
        # TODO: 更新 daily_trend, hourly_heatmap 到统计表

    async def compute_streak(self, user_id: str) -> tuple[int, int]:
        return 0, 0

    async def find_best_hours(self, user_id: str) -> list[int]:
        return []

    async def compute_regularity(self, user_id: str) -> float:
        return 0.0
