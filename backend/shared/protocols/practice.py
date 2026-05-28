"""
Practice Service Protocol — 练习模块对外契约
其他模块只能通过此接口调用练习功能。
实现类: domain/practice/service_impl.py
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shared.constants import DEFAULT_USER_ID
from app.schemas.practice import (
    Question,
    PracticeSession,
    KnowledgeState,
)


@runtime_checkable
class PracticeService(Protocol):
    """练习模块对外契约"""

    async def generate_questions(
        self,
        subject: str,
        topic: str = "",
        level: str = "medium",
        count: int = 5,
        user_id: str = DEFAULT_USER_ID,
    ) -> list[Question]:
        """生成练习题目"""
        ...

    async def create_session(
        self,
        user_id: str,
        question_ids: list[str],
        mode: str = "adaptive",
    ) -> PracticeSession:
        """创建练习会话"""
        ...

    async def submit_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
        time_spent: float = 0.0,
        hints_used: int = 0,
        explanation_text: str = "",
    ) -> dict:
        """提交答案 — 核心路径，同步返回 dict"""
        ...

    async def get_hint(
        self,
        question_id: str,
        hint_level: int = 1,
    ) -> dict:
        """获取提示"""
        ...

    async def get_knowledge_state(
        self,
        user_id: str,
        skill_id: str,
    ) -> KnowledgeState | None:
        """查询知识点掌握状态"""
        ...


    async def get_errors(
        self,
        user_id: str,
        resolved: bool | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """获取错题列表"""
        ...

    async def get_summary(
        self,
        branch_id: str,
    ) -> dict:
        """获取分支相关的练习摘要（供对话上下文注入用）"""
        ...
