"""
Analytics Service Protocol — 行为分析+习惯养成模块对外契约
"""

from __future__ import annotations

from typing import Protocol


class AnalyticsService(Protocol):
    """行为分析+习惯养成模块对外契约"""

    async def analyze_behavior(
        self,
        user_id: str,
    ) -> dict:
        """
        分析学习行为，返回:
        - streak: 连续学习天数
        - best_hours: 最佳学习时段
        - regularity: 规律性评分
        - fatigue_drop_minute: 疲劳下降时间点
        - current_streak: 当前连续天数
        """
        ...

    async def check_daily_goal(
        self,
        user_id: str,
    ) -> dict:
        """检查每日目标达成情况"""
        ...

    async def get_tiny_habits(
        self,
        streak_days: int,
    ) -> list[str]:
        """根据连续天数获取微习惯建议"""
        ...

    async def get_pomodoro_recommendation(
        self,
        fatigue_drop_minute: int,
    ) -> dict:
        """获取番茄钟建议"""
        ...

    async def on_answer_submitted(
        self,
        user_id: str,
        is_correct: bool,
        time_spent: float,
    ) -> None:
        """答题事件处理（事件驱动）"""
        ...
