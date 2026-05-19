"""
Persistence Repository Protocols — 仓储接口

定义 core/domain 层对持久化基础设施的抽象依赖。
基础设施层 (infra/) 实现这些接口。
"""

from __future__ import annotations

from typing import Protocol


class KnowledgeStateRepository(Protocol):
    """知识状态持久化仓储接口"""

    async def load(
        self,
        user_id: str,
        skill_id: str,
    ) -> dict | None:
        """加载单个知识点状态"""
        ...

    async def save(
        self,
        user_id: str,
        skill_id: str,
        state: dict,
    ) -> None:
        """保存知识点状态"""
        ...

    async def load_all(
        self,
        user_id: str,
    ) -> dict[str, dict]:
        """加载用户所有知识点状态"""
        ...


class AttemptRepository(Protocol):
    """答题记录仓储接口"""

    async def save_attempt(
        self,
        attempt: dict,
    ) -> None:
        """保存答题记录"""
        ...

    async def get_session_attempts(
        self,
        session_id: str,
    ) -> list[dict]:
        """获取会话所有答题记录"""
        ...

    async def get_user_attempts(
        self,
        user_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """获取用户近期答题记录"""
        ...


class SessionRepository(Protocol):
    """练习会话仓储接口"""

    async def get(
        self,
        session_id: str,
    ) -> dict | None:
        """获取会话"""
        ...

    async def create(
        self,
        session: dict,
    ) -> str:
        """创建会话，返回 session_id"""
        ...

    async def update(
        self,
        session_id: str,
        updates: dict,
    ) -> None:
        """更新会话"""
        ...

    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """获取用户会话列表"""
        ...


class QuestionRepository(Protocol):
    """题目仓储接口"""

    async def get(
        self,
        question_id: str,
    ) -> dict | None:
        """获取题目"""
        ...

    async def search(
        self,
        skill_id: str | None = None,
        difficulty: str | None = None,
        bloom_level: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """搜索题目"""
        ...


class ErrorBookRepository(Protocol):
    """错题本仓储接口"""

    async def add(
        self,
        entry: dict,
    ) -> None:
        """添加错题记录"""
        ...

    async def get_user_errors(
        self,
        user_id: str,
        resolved: bool | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """获取用户错题"""
        ...

    async def mark_resolved(
        self,
        entry_id: str,
    ) -> None:
        """标记错题已解决"""
        ...
