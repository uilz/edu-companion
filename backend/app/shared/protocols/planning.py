"""
Learning Planning Service Protocol — 学习规划模块对外契约
"""

from __future__ import annotations

from typing import Protocol


class PlanningService(Protocol):
    """学习规划模块对外契约"""

    async def generate_plan(
        self,
        user_id: str,
        weeks: int = 4,
    ) -> dict:
        """生成学习计划"""
        ...

    async def get_daily_goal(
        self,
        user_id: str,
    ) -> dict:
        """获取今日学习目标"""
        ...

    async def mark_task_complete(
        self,
        user_id: str,
        task_id: str,
    ) -> dict:
        """标记任务完成"""
        ...

    async def refresh_plan(
        self,
        user_id: str,
    ) -> dict:
        """根据知识状态变化刷新计划"""
        ...

    async def get_suggestions(
        self,
        user_id: str,
    ) -> list[str]:
        """获取学习建议"""
        ...
