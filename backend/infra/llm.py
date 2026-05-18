"""LiteLLM 客户端基础设施 — 实现 LLM 调用"""
import logging

logger = logging.getLogger("infra.llm")


class DeepSeekLLMClient:
    """DeepSeek LLM 客户端 — 封装 LiteLLM"""

    def __init__(self):
        self._model = "deepseek/deepseek-v4-flash"

    async def generate(self, prompt: str, system: str = "",
                       temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """生成回复"""
        # TODO: 接入 LiteLLM
        return ""
