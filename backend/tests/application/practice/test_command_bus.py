"""练习命令总线单元测试"""

from __future__ import annotations

import pytest

from app.application.practice.commands import (
    Command,
    CommandBus,
    CommandHandler,
    CompleteSessionCommand,
    SkipQuestionCommand,
    StartSessionCommand,
    SubmitAnswerCommand,
    register_practice_handlers,
)
from dataclasses import dataclass

from app.application.practice.commands.base import Command as BaseCommand


@dataclass(frozen=True)
class PingCommand(BaseCommand):
    """测试命令"""
    message: str = "ping"


class PingCommandHandler(CommandHandler):
    command_type = PingCommand

    async def handle(self, command: Command, context: dict | None = None) -> str:
        return f"pong:{command.message}"


@pytest.fixture
def bus() -> CommandBus:
    return CommandBus()


class TestCommandBus:
    @pytest.mark.asyncio
    async def test_register_and_dispatch(self, bus: CommandBus) -> None:
        bus.register(PingCommandHandler())
        result = await bus.dispatch(PingCommand(command_id="cmd_1", user_id="u1", message="hello"))
        assert result == "pong:hello"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_command_raises(self, bus: CommandBus) -> None:
        with pytest.raises(ValueError, match="No handler registered"):
            await bus.dispatch(PingCommand(command_id="cmd_1", user_id="u1"))

    @pytest.mark.asyncio
    async def test_context_passed_to_handler(self, bus: CommandBus) -> None:
        class CaptureHandler(CommandHandler):
            command_type = PingCommand

            async def handle(self, command: Command, context: dict | None = None) -> dict:
                return {"command": command.message, "context": context}

        bus.register(CaptureHandler())
        ctx = {"extra": 42}
        result = await bus.dispatch(PingCommand(command_id="cmd_1", user_id="u1"), context=ctx)
        assert result["context"] == ctx


class TestRegistry:
    def test_register_practice_handlers(self, bus: CommandBus) -> None:
        register_practice_handlers(bus)
        assert len(bus._handlers) == 4
        assert StartSessionCommand in bus._handlers
        assert SubmitAnswerCommand in bus._handlers
        assert SkipQuestionCommand in bus._handlers
        assert CompleteSessionCommand in bus._handlers
