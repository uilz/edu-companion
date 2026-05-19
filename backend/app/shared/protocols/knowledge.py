"""
Knowledge Graph Service Protocol — 知识图谱模块对外契约
"""

from __future__ import annotations

from typing import Protocol


class KnowledgeGraphService(Protocol):
    """知识图谱模块对外契约"""

    async def get_graph(
        self,
        user_id: str,
        subject: str | None = None,
    ) -> dict:
        """获取知识图谱（节点+边+BKT掌握度注入）"""
        ...

    async def get_prerequisites(
        self,
        skill_id: str,
    ) -> list[str]:
        """获取前置知识点"""
        ...

    async def can_practice(
        self,
        user_id: str,
        skill_id: str,
    ) -> bool:
        """检查知识点是否满足前置条件"""
        ...

    async def get_learning_path(
        self,
        user_id: str,
        skill_id: str | None = None,
    ) -> list[dict]:
        """获取推荐学习路径"""
        ...

    async def on_answer_submitted(
        self,
        user_id: str,
        skill_id: str,
        old_mastery: str,
        new_mastery: str,
        p_known_before: float,
        p_known_after: float,
    ) -> None:
        """答题事件处理 — 检测知识点升级"""
        ...

    async def on_knowledge_updated(
        self,
        user_id: str,
        skill_id: str,
        old_mastery: str,
        new_mastery: str,
    ) -> None:
        """知识状态更新事件"""
        ...

    async def get_skill_summary(
        self,
        user_id: str,
    ) -> dict[str, dict]:
        """获取所有知识点的摘要（掌握度+级别）"""
        ...
