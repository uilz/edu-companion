"""
Achievement Service Protocol — 成就系统模块对外契约
"""

from __future__ import annotations

from typing import Protocol


class AchievementService(Protocol):
    """成就系统模块对外契约"""

    async def check_all(
        self,
        user_id: str,
        stats: dict,
        existing: dict | None = None,
    ) -> list[dict]:
        """检查所有成就条件"""
        ...

    async def get_achievements(
        self,
        user_id: str,
    ) -> dict:
        """获取用户成就列表"""
        ...

    async def on_session_completed(
        self,
        user_id: str,
        session_id: str,
        total_questions: int,
        correct_count: int,
    ) -> None:
        """会话完成事件处理"""
        ...
