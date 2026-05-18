"""
LiteLLM 服务封装
统一封装大模型调用，支持流式和非流式输出
使用 LiteLLM 进行模型路由，允许用户自行配置模型端点
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

import litellm
from litellm import acompletion

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    大模型调用服务
    - 支持多种模型（OpenAI、Anthropic、本地模型等）
    - 通过 LiteLLM 统一路由
    - 支持流式/非流式输出
    """

    def __init__(self) -> None:
        self._setup_litellm()

    def _setup_litellm(self) -> None:
        """初始化 LiteLLM 配置"""
        # 设置调试模式
        litellm.set_verbose = settings.debug

        # 如果有自定义API端点，设置全局默认
        if settings.custom_api_base:
            # 通过环境变量让 LiteLLM 使用自定义端点
            import os
            os.environ["OPENAI_API_BASE"] = settings.custom_api_base

        # 设置 API Keys
        if settings.openai_api_key:
            import os
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        if settings.anthropic_api_key:
            import os
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.deepseek_api_key:
            import os
            os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key

        # 加载 LiteLLM 模型列表配置（如果有的话）
        if settings.litellm_model_list:
            litellm.model_list = settings.litellm_model_list

        logger.info("LiteLLM 服务初始化完成，当前默认模型: %s", settings.default_model)

    def select_model(
        self,
        task_type: str = "chat",
        subject: Optional[str] = None,
    ) -> str:
        """
        根据任务类型选择合适的模型

        参数:
            task_type: 任务类型 (chat/reasoning/fast)
            subject: 学科（可用于特定模型路由）

        返回:
            LiteLLM 格式的模型名称
        """
        model_map = {
            "chat": settings.default_model,
            "reasoning": settings.reasoning_model,
            "fast": settings.fast_model,
            "intent": settings.fast_model,       # 意图识别用轻量模型
            "emotion": settings.fast_model,       # 情绪分析用轻量模型
            "explain": settings.reasoning_model,  # 解释复杂概念用推理模型
            "plan": settings.default_model,       # 学习计划用默认模型
        }
        model = model_map.get(task_type, settings.default_model)
        logger.debug("任务类型 [%s] -> 选择模型 [%s]", task_type, model)
        return model

    async def generate(
        self,
        messages: list[dict[str, str]],
        task_type: str = "chat",
        subject: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        非流式生成回复

        参数:
            messages: OpenAI格式的消息列表
            task_type: 任务类型
            subject: 学科
            temperature: 温度
            max_tokens: 最大token数

        返回:
            生成的文本
        """
        model = self.select_model(task_type, subject)
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            content = response.choices[0].message.content or ""
            # Reasoning models (deepseek-v4-flash) may put all tokens into reasoning_content
            if not content:
                reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
                if reasoning:
                    content = reasoning.strip()
            logger.info("模型生成完成 [%s]，token数: %d", model, response.usage.total_tokens if response.usage else 0)
            return content
        except Exception as e:
            logger.error("LLM 生成失败 [%s]: %s", model, str(e))
            raise

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        task_type: str = "chat",
        subject: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回复（异步生成器）

        参数:
            messages: OpenAI格式的消息列表
            task_type: 任务类型
            subject: 学科
            temperature: 温度
            max_tokens: 最大token数

        产出:
            逐个token的文本片段
        """
        model = self.select_model(task_type, subject)
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
            async for chunk in response:
                if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content
                ):
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("LLM 流式生成失败 [%s]: %s", model, str(e))
            raise

    async def classify_intent(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """
        使用轻量模型对用户消息进行意图分类

        返回:
            {"intent": "...", "confidence": 0.0~1.0, "subject": "..."}
        """
        system_prompt = """你是一个意图分类器。分析用户的消息，返回JSON格式的分类结果。

可选的意图类型（intent）：
- question: 提问
- explain: 请求解释概念
- practice: 想要练习
- review: 复习
- encouragement: 寻求鼓励
- frustration: 表达挫败感
- chitchat: 闲聊

可选的情绪类型（emotion）：
- neutral: 中性
- happy: 高兴
- confused: 困惑
- frustrated: 挫败
- excited: 兴奋
- tired: 疲倦
- confident: 自信

同时请识别涉及的学科（subject）。

只返回JSON，不要其他文字。格式：
{"intent": "...", "emotion": "...", "confidence": 0.9, "subject": "..."}
"""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        if context:
            messages.extend(context[-3:])  # 只取最近3条作为上下文
        messages.append({"role": "user", "content": user_message})

        result_text = await self.generate(
            messages=messages,
            task_type="intent",
            temperature=0.1,
            max_tokens=200,
        )

        # 解析JSON结果
        import json
        try:
            # 尝试从可能包含markdown代码块的文本中提取JSON
            clean_text = result_text.strip()
            if clean_text.startswith("```"):
                clean_text = clean_text.split("```")[1]
                if clean_text.startswith("json"):
                    clean_text = clean_text[4:]
            result = json.loads(clean_text.strip())
        except (json.JSONDecodeError, IndexError):
            logger.warning("意图分类结果解析失败，返回默认值")
            result = {
                "intent": "unknown",
                "emotion": "neutral",
                "confidence": 0.0,
                "subject": None,
            }

        return result


# ── 全局服务实例 ──
llm_service = LLMService()
