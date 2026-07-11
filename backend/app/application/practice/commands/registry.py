"""练习命令总线注册。

在应用启动时调用 register_practice_handlers() 把所有命令处理器挂载到总线。
"""

from __future__ import annotations

from app.application.practice.commands.base import CommandBus
from app.application.practice.commands.handlers import (
    CompleteSessionCommandHandler,
    SkipQuestionCommandHandler,
    StartSessionCommandHandler,
    SubmitAnswerCommandHandler,
)


def register_practice_handlers(bus: CommandBus) -> CommandBus:
    """向命令总线注册所有练习命令处理器。"""
    bus.register(StartSessionCommandHandler())
    bus.register(SubmitAnswerCommandHandler())
    bus.register(SkipQuestionCommandHandler())
    bus.register(CompleteSessionCommandHandler())
    return bus
