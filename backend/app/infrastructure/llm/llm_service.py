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
        """初始化 LiteLLM 配置 — 仅使用 OpenAI 兼容格式"""
        import os

        # 禁用远程模型价格表拉取（避免网络超时警告，使用本地备份）
        os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

        litellm.set_verbose = settings.debug

        # OpenAI 兼容 API 配置（唯一格式）
        if settings.openai_api_base:
            os.environ["OPENAI_API_BASE"] = settings.openai_api_base
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
            # LiteLLM 的 deepseek/ provider 查的是 DEEPSEEK_API_KEY，不是 OPENAI_API_KEY
            os.environ["DEEPSEEK_API_KEY"] = settings.openai_api_key

        logger.info("LiteLLM 初始化完成，文本模型: %s", settings.text_model)

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
            "chat": settings.text_model,
            "reasoning": settings.text_reasoning_model,
            "fast": settings.text_fast_model,
            "intent": settings.text_fast_model,       # 意图识别用轻量模型
            "emotion": settings.text_fast_model,       # 情绪分析用轻量模型
            "explain": settings.text_reasoning_model,  # 解释复杂概念用推理模型
            "plan": settings.text_model,               # 学习计划用默认模型
        }
        model = model_map.get(task_type, settings.text_model)
        logger.debug("任务类型 [%s] -> 选择模型 [%s]", task_type, model)
        return model

    def _get_user_llm_kwargs(self, user_id: Optional[str] = None) -> dict:
        """获取用户的 LLM 自定义配置参数

        如果用户已保存自定义配置（api_key/api_base/model_name），
        返回对应的 LiteLLM acompletion 参数用于覆盖全局配置。

        Returns:
            dict，可解包传入 acompletion：api_key/api_base/model
        """
        if not user_id:
            return {}
        try:
            from app.domain.auth.user_llm_repo import get_user_llm_config_repo
            repo = get_user_llm_config_repo()
            config = repo.get(user_id)
            if config and config.get("model_name"):
                kwargs: dict = {}
                if config.get("api_key"):
                    kwargs["api_key"] = config["api_key"]
                if config.get("api_base"):
                    kwargs["api_base"] = config["api_base"]
                if config.get("model_name"):
                    kwargs["model"] = config["model_name"]
                return kwargs
        except Exception as e:
            logger.warning("获取用户 LLM 配置失败 (user_id=%s): %s", user_id, e)
        return {}

    async def generate(
        self,
        messages: list[dict[str, str]],
        task_type: str = "chat",
        subject: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] | None = None,
        user_id: Optional[str] = None,  # 用户自定义配置
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
            tools: OpenAI function calling 工具定义列表 (Phase 5)
            user_id: 用户ID，传入后将使用用户自定义 LLM 配置

        返回:
            生成的文本；如果 LLM 返回 tool_calls，返回特殊标记 JSON

        异常:
            ValueError: 模型或 API Key 未配置
        """
        # 检查用户自定义配置
        user_kwargs = self._get_user_llm_kwargs(user_id)
        use_custom = bool(user_kwargs.get("model"))

        if use_custom:
            model = user_kwargs.pop("model")
        else:
            model = self.select_model(task_type, subject)

        # 统一配置校验
        if not model:
            raise ValueError("LLM 模型未配置，请在 .env 中设置 TEXT_MODEL")
        if not use_custom:
            if not settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")
        elif not user_kwargs.get("api_key"):
            # 用户自定义模式但没填 API Key — 回退全局 key
            if settings.openai_api_key:
                user_kwargs["api_key"] = settings.openai_api_key
            else:
                raise ValueError("自定义 LLM 未配置 API Key")

        extra = dict(kwargs)
        # 合并用户自定义参数
        extra.update(user_kwargs)
        if tools:
            extra["tools"] = tools
            extra["tool_choice"] = "auto"
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=60,  # 60s LLM 超时 (M3)
                **extra,
            )
            msg = response.choices[0].message
            # 优先处理 tool_calls
            if msg.tool_calls:
                import json
                tool_calls_json = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
                return json.dumps({"__tool_calls__": tool_calls_json}, ensure_ascii=False)

            content = msg.content or ""
            if not content:
                reasoning = getattr(msg, 'reasoning_content', None)
                if reasoning:
                    # 推理模型的 thinking 不是最终输出，不能用
                    logger.warning(
                        "模型返回了 reasoning_content 但 content 为空 "
                        "（thinking 消耗了全部 max_tokens=%d？），raw: %s...",
                        max_tokens, str(reasoning)[:100],
                    )
                    content = f"[模型推理溢出] 请增大 max_tokens 或使用非推理模型。\nmodel={model}, max_tokens={max_tokens}"
                else:
                    # content 为空且无 reasoning → 模型静默返回空
                    logger.warning("模型返回空 content（无 reasoning），model=%s, usage=%s",
                                   model, response.usage)
                    content = f"[模型无输出] 模型 '{model}' 返回了空内容。请检查 API 配额或模型可用性。"
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
        user_id: Optional[str] = None,  # 用户自定义配置
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
            user_id: 用户ID，传入后将使用用户自定义 LLM 配置

        产出:
            逐个token的文本片段
        """
        # 检查用户自定义配置
        user_kwargs = self._get_user_llm_kwargs(user_id)
        use_custom = bool(user_kwargs.get("model"))

        if use_custom:
            model = user_kwargs.pop("model")
        else:
            model = self.select_model(task_type, subject)

        # 统一配置校验
        if not model:
            raise ValueError("LLM 模型未配置，请在 .env 中设置 TEXT_MODEL")
        if not use_custom:
            if not settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")
        elif not user_kwargs.get("api_key"):
            # 用户自定义模式但没填 API Key — 回退全局 key
            if settings.openai_api_key:
                user_kwargs["api_key"] = settings.openai_api_key
            else:
                raise ValueError("自定义 LLM 未配置 API Key")

        extra = dict(kwargs)
        extra.update(user_kwargs)

        yielded_any = False
        last_reasoning = ""
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                timeout=120,  # 流式超时更长 (M3)
                **extra,
            )
            async for chunk in response:
                if not (chunk.choices and chunk.choices[0].delta):
                    continue

                delta = chunk.choices[0].delta
                # 追踪 reasoning_content（推理模型）
                rc = getattr(delta, 'reasoning_content', None)
                if rc:
                    last_reasoning = rc

                if delta.content:
                    yielded_any = True
                    yield delta.content

            # 流结束但未产出任何 content → 推理模型溢出或模型静默
            if not yielded_any:
                if last_reasoning:
                    msg = (
                        f"[模型推理溢出] 推理模型 '{model}' 的 thinking 消耗了全部 {max_tokens} tokens，"
                        f"请增大 max_tokens 或换用非推理模型。\n"
                        f"reasoning 片段: {str(last_reasoning)[:300]}"
                    )
                else:
                    msg = (
                        f"[模型无输出] 模型 '{model}' 未返回任何内容。"
                        "请检查 API 配额、模型可用性或增大 max_tokens。"
                    )
                logger.warning("generate_stream 无输出: model=%s, reasoning=%s",
                               model, "有" if last_reasoning else "无")
                yield msg
        except Exception as e:
            logger.error("LLM 流式生成失败 [%s]: %s", model, str(e))
            raise

    async def generate_stream_with_tools(
        self,
        messages: list[dict[str, str]],
        task_type: str = "chat",
        subject: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] | None = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """流式生成，支持 OpenAI function calling。

        产出事件：
          {"type": "token",      "content": str }   — 文本 token
          {"type": "tool_calls", "tool_calls": [...]} — 模型决定调工具
          {"type": "done",       "full_text": str }  — 文本回复完成
        """
        user_kwargs = self._get_user_llm_kwargs(user_id)
        use_custom = bool(user_kwargs.get("model"))

        if use_custom:
            model = user_kwargs.pop("model")
        else:
            model = self.select_model(task_type, subject)

        if not model:
            raise ValueError("LLM 模型未配置，请在 .env 中设置 TEXT_MODEL")
        if not use_custom:
            if not settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")
        elif not user_kwargs.get("api_key"):
            if settings.openai_api_key:
                user_kwargs["api_key"] = settings.openai_api_key
            else:
                raise ValueError("自定义 LLM 未配置 API Key")

        extra: dict[str, Any] = {}
        extra.update(user_kwargs)
        if tools:
            extra["tools"] = tools
            extra["tool_choice"] = "auto"

        full_content = ""
        yielded_any = False
        last_reasoning = ""
        tool_calls_accum: dict[int, dict] = {}

        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                timeout=120,
                **extra,
            )
            async for chunk in response:
                if not (chunk.choices and chunk.choices[0].delta):
                    continue
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # reasoning content（推理模型）
                rc = getattr(delta, 'reasoning_content', None)
                if rc:
                    last_reasoning = rc
                    yield {"type": "reasoning", "content": rc}

                # text token
                if delta.content:
                    full_content += delta.content
                    yielded_any = True
                    yield {"type": "token", "content": delta.content}

                # tool_calls delta（跨 chunk 累加）
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_accum:
                            tool_calls_accum[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_accum[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_accum[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_accum[idx]["function"]["arguments"] += tc.function.arguments

                # finish_reason 判断
                if finish_reason == "tool_calls":
                    result = [
                        {"id": v["id"], "type": "function", "function": v["function"]}
                        for _, v in sorted(tool_calls_accum.items())
                    ]
                    yield {"type": "tool_calls", "tool_calls": result}
                    return

            # 正常流结束（finish_reason="stop"），无 tool_calls
            if not yielded_any and not full_content:
                if last_reasoning:
                    msg = (
                        f"[模型推理溢出] 推理模型 '{model}' 的 thinking 消耗了全部 {max_tokens} tokens，"
                        f"请增大 max_tokens 或换用非推理模型。\n"
                        f"reasoning 片段: {str(last_reasoning)[:300]}"
                    )
                else:
                    msg = (
                        f"[模型无输出] 模型 '{model}' 未返回任何内容。"
                        "请检查 API 配额、模型可用性或增大 max_tokens。"
                    )
                logger.warning("generate_stream_with_tools 无输出: model=%s", model)
                full_content = msg
                yield {"type": "token", "content": msg}

            yield {"type": "done", "full_text": full_content, "reasoning_content": last_reasoning or None}

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
- negotiate: 协商/调整学习建议（如"改成明天""换个方式""今日太忙"）

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


def _parse_tool_calls_response(result_text: str) -> list[dict] | None:
    """解析 LLM 返回的 tool_calls JSON"""
    import json
    if not result_text.startswith("{"):
        return None
    try:
        data = json.loads(result_text)
        return data.get("__tool_calls__")
    except (json.JSONDecodeError, KeyError):
        return None
