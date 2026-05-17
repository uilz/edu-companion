"""
Agent 基类
定义所有智能体的公共接口和基础能力
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional

from app.services.llm_service import LLMService
from app.schemas.learner import IntentType, EmotionType

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 基类
    所有智能体（Tutor、Coach等）都继承此类
    """

    # Agent 名称，子类需要覆盖
    agent_name: str = "base"
    # Agent 描述
    agent_description: str = "基础Agent"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service
        # 会话消息历史（每个Agent维护自己的上下文）
        self._message_history: list[dict[str, str]] = []
        # 系统提示词（子类需要设置）
        self._system_prompt: str = ""

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词"""
        self._system_prompt = prompt

    def get_messages(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> list[dict[str, str]]:
        """
        构建发送给LLM的消息列表

        参数:
            user_message: 用户消息
            context: 额外的上下文消息

        返回:
            OpenAI格式的消息列表
        """
        messages: list[dict[str, str]] = []

        # 系统提示词
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        # 历史消息
        messages.extend(self._message_history[-10:])  # 保留最近10条

        # 额外上下文
        if context:
            messages.extend(context)

        # 当前用户消息
        messages.append({"role": "user", "content": user_message})

        return messages

    def record_exchange(self, user_message: str, assistant_reply: str) -> None:
        """记录对话交换到历史"""
        self._message_history.append({"role": "user", "content": user_message})
        self._message_history.append({"role": "assistant", "content": assistant_reply})
        # 限制历史长度
        if len(self._message_history) > 20:
            self._message_history = self._message_history[-20:]

    @abstractmethod
    async def handle(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        处理用户消息并返回回复（非流式）

        参数:
            user_message: 用户消息
            context: 上下文信息
            metadata: 额外元数据（如知识状态等）

        返回:
            Agent的回复文本
        """
        ...

    @abstractmethod
    async def handle_stream(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式处理用户消息

        参数:
            user_message: 用户消息
            context: 上下文信息
            metadata: 额外元数据

        产出:
            逐片段的回复文本
        """
        ...

    def clear_history(self) -> None:
        """清空对话历史"""
        self._message_history.clear()
        logger.info("Agent [%s] 对话历史已清空", self.agent_name)

    def should_handle(
        self,
        intent: IntentType,
        emotion: EmotionType,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        判断该Agent是否应该处理当前请求
        子类可以覆盖此方法来实现自定义路由逻辑

        参数:
            intent: 检测到的意图
            emotion: 检测到的情绪
            metadata: 额外元数据

        返回:
            是否应该处理
        """
        return True  # 默认所有Agent都接受
