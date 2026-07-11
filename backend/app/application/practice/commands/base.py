"""练习模块命令总线基础类型。

提供 Command 基类、CommandHandler 协议和 CommandBus 实现。
命令总线负责把命令分发给对应的处理器，是练习模块重构后应用层的核心入口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar


@dataclass(frozen=True)
class Command:
    """命令基类。

    所有练习相关命令都应该是 dataclass，且继承自 Command。
    命令必须包含 command_id 用于幂等，以及 user_id 用于权限校验。
    """

    command_id: str
    user_id: str


C = TypeVar("C", bound=Command)
R = TypeVar("R")


class CommandHandler(ABC):
    """命令处理器协议。"""

    command_type: type[Command]

    @abstractmethod
    async def handle(self, command: Command, context: dict | None = None) -> R:
        """处理命令并返回结果。

        context 可选，由 dispatch 传入，通常包含 uow / event_bus 等依赖。
        """
        raise NotImplementedError


class CommandBus:
    """内存命令总线。

    处理器在初始化时注册到总线。dispatch 根据命令类型查找对应处理器。
    命令总线本身不负责持久化，只负责路由；依赖通过 context 透传。
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Command], CommandHandler] = {}

    def register(self, handler: CommandHandler) -> None:
        """注册命令处理器。"""
        self._handlers[handler.command_type] = handler

    async def dispatch(self, command: Command, context: dict | None = None) -> Any:
        """分发命令到对应处理器。"""
        handler = self._handlers.get(type(command))
        if handler is None:
            raise ValueError(f"No handler registered for command {type(command).__name__}")
        return await handler.handle(command, context=context)
