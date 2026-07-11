"""练习模块命令定义。

每个命令对应用户或系统对练习聚合根的一次意图。
命令只包含事实数据，不包含业务逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.practice.commands.base import Command


@dataclass(frozen=True)
class StartSessionCommand(Command):
    """开始练习会话。"""

    session_id: str
    bank_id: str
    session_type: str = "practice"
    mode: str = "adaptive"
    question_count: int = 10
    config: dict[str, Any] = field(default_factory=dict)
    cognitive_node_ids: list[str] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SubmitAnswerCommand(Command):
    """提交答题答案。"""

    session_id: str
    attempt_id: str
    question_id: str
    user_answer: Any
    response_time_ms: int = 0
    confidence_before: int | None = None
    hints_used: int = 0


@dataclass(frozen=True)
class SkipQuestionCommand(Command):
    """跳过当前题目。"""

    session_id: str
    question_id: str


@dataclass(frozen=True)
class CompleteSessionCommand(Command):
    """完成练习会话。"""

    session_id: str
    duration_seconds: int = 0
