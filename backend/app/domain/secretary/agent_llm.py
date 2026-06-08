"""Agent LLM 服务 — 意图分析与工具调用"""

from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator

from app.services.llm.llm_service import LLMService
from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

# ── System Prompt ──
AGENT_SYSTEM_PROMPT = """你是一个学习助手 AI 秘书，帮助用户导航学习系统。

你的能力：
1. 理解用户的学习需求
2. 推荐合适的页面和功能
3. 调用工具帮助用户完成操作

回复格式：
- 先用自然语言简短回复用户（1-3句话）
- 如果需要调用工具，在回复末尾用以下格式标注：
  ```json
  {"tool_call": {"name": "工具名", "arguments": {...}}}
  ```

注意：
- 回复要简洁友好
- 只在确实需要跳转或执行操作时才调用工具
- 如果用户只是闲聊或提问，只回复文字即可
"""

TOOL_CALL_RE = re.compile(r'```json\s*\n?(\{.*?"tool_call".*?\})\s*\n?```', re.DOTALL)


def parse_tool_call(text: str) -> dict | None:
    """从 LLM 回复中解析 tool_call"""
    match = TOOL_CALL_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return data.get("tool_call")
    except (json.JSONDecodeError, KeyError):
        return None


def strip_tool_call_json(text: str) -> str:
    """从回复中移除 tool_call JSON 块"""
    return TOOL_CALL_RE.sub("", text).strip()


async def agent_generate_stream(
    user_message: str,
    current_page: str,
    tool_schemas: list[dict],
    user_id: str = DEFAULT_USER_ID,
) -> AsyncGenerator[dict, None]:
    """Agent 流式生成回复

    Yields:
        {"type": "token", "delta": str} — 文本增量
        {"type": "tool_call", "tool_call": dict} — 工具调用
        {"type": "done", "full_text": str} — 完成
    """
    llm = LLMService()

    # 构建工具描述
    tools_desc = ""
    if tool_schemas:
        tools_desc = "\n可用工具：\n"
        for t in tool_schemas:
            params_desc = ", ".join(
                f"{k}({v.get('type', 'string')})" for k, v in t.get("parameters", {}).items()
            )
            tools_desc += f"- {t['name']}: {t['description']} [参数: {params_desc or '无'}]\n"

    system_prompt = AGENT_SYSTEM_PROMPT + tools_desc

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"当前页面: {current_page}\n用户: {user_message}",
        },
    ]

    full_text = ""
    try:
        async for token in llm.generate_stream(
            messages=messages,
            task_type="agent_chat",
            temperature=0.7,
            max_tokens=512,
        ):
            full_text += token
            yield {"type": "token", "delta": token}
    except Exception as e:
        logger.error("Agent LLM 流式生成失败: %s", e)
        full_text = f"抱歉，AI 服务暂时不可用：{e}"
        yield {"type": "token", "delta": full_text}

    # 解析 tool_call
    tool_call = parse_tool_call(full_text)
    if tool_call:
        yield {"type": "tool_call", "tool_call": tool_call}

    yield {"type": "done", "full_text": strip_tool_call_json(full_text)}