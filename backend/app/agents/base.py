"""
Agent 基类
定义所有智能体的公共接口和基础能力 — Phase 5: 支持 tool calling
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional

from app.services.llm_service import LLMService, _parse_tool_calls_response
from app.schemas.learner import IntentType, EmotionType

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 基类
    所有智能体（Tutor、Coach等）都继承此类

    Phase 5: 支持 LLM native tool calling
    - 子类设置 self._tools 即可启用
    - handle_stream() 自动执行 tool call loop
    """

    # Agent 名称，子类需要覆盖
    agent_name: str = "base"
    # Agent 描述
    agent_description: str = "基础Agent"

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service
        self._message_history: list[dict[str, str]] = []
        self._system_prompt: str = ""
        # Phase 5: 工具定义 + 执行器
        self._tools: list[dict] | None = None
        self._tool_executor: Any = None  # ToolExecutor 实例

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词"""
        self._system_prompt = prompt

    def set_tools(self, tools: list[dict], executor: Any = None) -> None:
        """
        Phase 5: 配置工具列表 + 执行器

        参数:
            tools: OpenAI function calling format 工具定义
            executor: ToolExecutor 实例（可选，有默认值）
        """
        self._tools = tools
        if executor is None:
            from app.services.tool_executor import tool_executor
            executor = tool_executor
        self._tool_executor = executor

    def get_messages(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> list[dict[str, str]]:
        """
        构建发送给LLM的消息列表
        """
        messages: list[dict[str, str]] = []

        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        messages.extend(self._message_history[-10:])

        if context:
            messages.extend(context)

        messages.append({"role": "user", "content": user_message})

        return messages

    def record_exchange(self, user_message: str, assistant_reply: str) -> None:
        """记录对话交换到历史"""
        self._message_history.append({"role": "user", "content": user_message})
        self._message_history.append({"role": "assistant", "content": assistant_reply})
        if len(self._message_history) > 20:
            self._message_history = self._message_history[-20:]

    @abstractmethod
    async def handle(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """处理用户消息并返回回复（非流式）"""
        ...

    @abstractmethod
    async def handle_stream(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """流式处理用户消息"""
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
        """判断该Agent是否应该处理当前请求"""
        return True

    # ── Phase 5: Tool Calling ──

    async def _run_with_tools(
        self,
        messages: list[dict[str, str]],
        task_type: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_rounds: int = 3,
    ) -> str:
        """
        Tool call loop: LLM → 执行工具 → 结果喂回 → 最终回复

        最多 max_rounds 轮 tool call，防止死循环。
        """
        tools = self._tools
        executor = self._tool_executor
        if not tools or not executor:
            return await self.llm.generate(messages=messages, task_type=task_type,
                                           temperature=temperature, max_tokens=max_tokens)

        current_messages = list(messages)
        round_count = 0

        while round_count < max_rounds:
            round_count += 1

            result = await self.llm.generate(
                messages=current_messages,
                task_type=task_type,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )

            # 检查是否 LLM 请求 tool call
            tool_calls = _parse_tool_calls_response(result)
            if not tool_calls:
                # 纯文本回复 → 完成
                return result

            # LLM 发出了 tool_calls → 执行
            logger.info(
                "🔧 Agent [%s] tool call round %d: %s",
                self.agent_name, round_count,
                [tc["function"]["name"] for tc in tool_calls],
            )

            # 添加 assistant 消息（含 tool_calls）
            assistant_msg: dict = {
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            }
            current_messages.append(assistant_msg)

            # 逐个执行工具
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}

                try:
                    handler = executor.TOOL_HANDLERS.get(tool_name)
                    if handler:
                        tool_result = await handler(args)
                        result_str = json.dumps(tool_result, ensure_ascii=False)
                    else:
                        result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})
                except Exception as e:
                    logger.error("Tool %s failed: %s", tool_name, e)
                    result_str = json.dumps({"error": str(e)})

                # 添加 tool result 消息
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

                logger.debug("✅ Tool %s executed, result %d chars", tool_name, len(result_str))

        # 超过最大轮次 → 强制要求总结
        current_messages.append({
            "role": "system",
            "content": "已达到最大工具调用次数，请基于已有结果直接回答用户问题。",
        })
        return await self.llm.generate(
            messages=current_messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _stream_with_tools(
        self,
        messages: list[dict[str, str]],
        task_type: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        带 tool calling 的流式输出。

        流程:
        1. 先非流式检查 LLM 是否需要 tool calls
        2. 如果需要 → 执行工具 → 结果注入 → 流式输出最终回复
        3. 如果不需要 → 直接流式输出
        """
        tools = self._tools
        executor = self._tool_executor
        if not tools or not executor:
            async for chunk in self.llm.generate_stream(
                messages=messages, task_type=task_type,
                temperature=temperature, max_tokens=max_tokens,
            ):
                yield chunk
            return

        # 先用非流式调用探测是否需要工具
        final_text = await self._run_with_tools(
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            max_rounds=3,
        )

        # 将最终结果逐字符 yield（模拟流式）
        chunk_size = 4
        for i in range(0, len(final_text), chunk_size):
            yield final_text[i:i + chunk_size]
