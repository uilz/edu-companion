"""OpenAI 兼容 LLM 客户端 — 统一的文本模型调用入口"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("infra.llm")

# 模型名从环境变量读取（OpenAI 兼容格式）
_TEXT_MODEL = os.getenv("TEXT_MODEL", "openai/gpt-4o-mini")


class LLMClient:
    """LLM 客户端 — 只使用 OpenAI 兼容 API 格式"""

    def __init__(self, model: str | None = None):
        self._model = model or _TEXT_MODEL

    async def generate(self, prompt: str, system: str = "",
                       temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """生成回复"""
        # 由 LiteLLM 网关统一路由，此方法为 Phase 4 DI 占位
        # 实际调用走 app/services/llm_service.py
        return ""
