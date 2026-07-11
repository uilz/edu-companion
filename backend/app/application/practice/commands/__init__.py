"""练习模块命令总线公开接口。"""

from __future__ import annotations

from app.application.practice.commands.base import Command, CommandBus, CommandHandler
from app.application.practice.commands.commands import (
    CompleteSessionCommand,
    SkipQuestionCommand,
    StartSessionCommand,
    SubmitAnswerCommand,
)
from app.application.practice.commands.handlers import (
    CompleteSessionCommandHandler,
    SkipQuestionCommandHandler,
    StartSessionCommandHandler,
    SubmitAnswerCommandHandler,
)
from app.application.practice.commands.registry import register_practice_handlers

__all__ = [
    "Command",
    "CommandBus",
    "CommandHandler",
    "StartSessionCommand",
    "SubmitAnswerCommand",
    "SkipQuestionCommand",
    "CompleteSessionCommand",
    "StartSessionCommandHandler",
    "SubmitAnswerCommandHandler",
    "SkipQuestionCommandHandler",
    "CompleteSessionCommandHandler",
    "register_practice_handlers",
]
