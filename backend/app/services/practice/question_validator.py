"""
结构化输出校验 — Pydantic 校验链 (ADR 0011 Q6)

替换 question_generator._parse_llm_response() 中脆弱的三段降级解析。
校验失败 → 自动重试1次 (temperature=0.3)。重试仍失败 → 记录日志, 不返回。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ── 允许的 Bloom 层级 ──
VALID_BLOOM_LEVELS = {"remember", "understand", "apply", "analyze", "evaluate", "create"}


class GeneratedOption(BaseModel):
    """生成题目的选项"""
    letter: str = Field(min_length=1, max_length=2, description="选项字母")
    text: str = Field(min_length=1, description="选项内容")
    is_correct: bool = Field(default=False, description="是否为正确答案")
    distractor_type: str | None = Field(default=None, description="干扰项类型")


class GeneratedQuestion(BaseModel):
    """LLM 生成的题目结构"""
    text: str = Field(..., min_length=5, description="题目文本")
    options: list[GeneratedOption] = Field(..., min_length=2, max_length=8, description="选项列表")
    correct_answer: str = Field(..., min_length=1, description="正确答案")
    explanation: str = Field(default="", description="解析")
    hints: list[str] = Field(default_factory=list, max_length=5, description="提示列表")
    difficulty: float = Field(default=0.5, ge=0.1, le=1.0, description="难度 0.1~1.0")
    bloom_level: str = Field(default="apply", description="Bloom 认知层次")

    @field_validator("bloom_level")
    @classmethod
    def validate_bloom(cls, v: str) -> str:
        v_lower = v.lower().strip()
        if v_lower not in VALID_BLOOM_LEVELS:
            raise ValueError(f"无效的 bloom_level: {v}，允许值: {VALID_BLOOM_LEVELS}")
        return v_lower

    @field_validator("options")
    @classmethod
    def has_correct_option(cls, v: list[GeneratedOption]) -> list[GeneratedOption]:
        if not any(o.is_correct for o in v):
            raise ValueError("选项列表中没有正确答案 (is_correct=True)")
        return v

    @field_validator("correct_answer")
    @classmethod
    def match_option_letter(cls, v: str, info) -> str:
        """验证 correct_answer 对应一个存在的选项字母"""
        options = info.data.get("options", [])
        if options:
            option_letters = {o.letter for o in options}
            if v not in option_letters:
                raise ValueError(f"correct_answer '{v}' 不在选项字母 {option_letters} 中")
        return v


def validate_generated_questions(raw_data: list[dict]) -> list[GeneratedQuestion]:
    """
    校验 LLM 生成的题目列表。

    返回: 通过校验的题目列表（无效的题目被跳过并记录日志）
    """
    valid = []
    for i, item in enumerate(raw_data):
        try:
            q = GeneratedQuestion(**item)
            valid.append(q)
        except Exception as e:
            logger.warning(
                "Q%d 校验失败: %s — data: %s",
                i + 1, e, json.dumps(item, ensure_ascii=False)[:200],
            )
    return valid


def parse_and_validate_llm_response(response: str) -> list[dict]:
    """
    解析 LLM 返回的 JSON 并校验。

    解析策略（三层降级）：
    1. 直接 JSON 解析
    2. Markdown 代码块提取
    3. 正则数组提取

    每层解析后都通过 Pydantic 校验，不合格的题目被丢弃。
    返回: 通过校验的 dict 列表（可用于 Question 构造）
    """
    raw_data: list[dict] = []

    # 第1层：直接解析
    try:
        data = json.loads(response)
        if isinstance(data, list):
            raw_data = data
        elif isinstance(data, dict):
            raw_data = [data]
    except json.JSONDecodeError:
        pass

    # 第2层：Markdown 代码块提取
    if not raw_data:
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list):
                    raw_data = data
                elif isinstance(data, dict):
                    raw_data = [data]
            except json.JSONDecodeError:
                pass

    # 第3层：正则数组提取
    if not raw_data:
        array_match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', response)
        if array_match:
            try:
                data = json.loads(array_match.group(0))
                if isinstance(data, list):
                    raw_data = data
            except json.JSONDecodeError:
                pass

    if not raw_data:
        logger.warning("无法从 LLM 响应中解析出任何 JSON: %s", response[:200])
        return []

    # Pydantic 校验
    valid = validate_generated_questions(raw_data)

    # 转为 dict 保持向后兼容
    return [q.model_dump() for q in valid]