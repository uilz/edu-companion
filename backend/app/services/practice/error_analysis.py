"""
LLM 错因分析 — 异步分析答题错误原因 (ADR 0011 A2)

答错时异步调 LLM 分析错因，不阻塞答题流程。
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def llm_error_analysis(
    question: dict,
    user_answer: list[str],
    correct_answer: list[str],
    selected_option: Optional[dict] = None,
) -> dict:
    """
    LLM 分析答题错误原因。

    参数:
        question: 题目信息 (含 stem, options, analysis)
        user_answer: 用户提交的答案
        correct_answer: 正确答案
        selected_option: 用户选择的选项详情（含 distractor_type）

    返回:
        {
            "error_type": "concept_confusion" | "calculation_error" | "carelessness" | "misreading" | "knowledge_gap",
            "misconception": "具体错误概念描述",
            "suggestion": "改进建议",
            "related_knowledge": ["关联知识点"],
            "confidence": 0.0~1.0,
        }
    """
    from app.infrastructure.llm.llm_service import llm_service

    stem = question.get("stem", question.get("text", ""))
    options = question.get("options", [])
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except Exception:
            options = []
    analysis = question.get("analysis", question.get("explanation", ""))

    # 构建选项文本
    option_text = ""
    if options:
        option_lines = []
        for o in options:
            letter = o.get("letter", "")
            text = o.get("text", o.get("content", ""))
            is_correct = o.get("is_correct", False)
            dt = o.get("distractor_type", "")
            marker = " ✓(正确)" if is_correct else ""
            dt_label = f" [{dt}]" if dt else ""
            option_lines.append(f"  {letter}. {text}{marker}{dt_label}")
        option_text = "\n".join(option_lines)

    # 如果有 distractor_type，直接用作错因线索
    distractor_hint = ""
    if selected_option and selected_option.get("distractor_type"):
        distractor_hint = f"\n学生选择的干扰项类型标记: {selected_option['distractor_type']}"

    prompt = f"""分析以下学生答题错误，诊断错误原因。

题目: {stem[:300]}
{option_text if option_text else ''}
正确答案: {', '.join(correct_answer) if isinstance(correct_answer, list) else correct_answer}
学生答案: {', '.join(user_answer) if isinstance(user_answer, list) else user_answer}{distractor_hint}

请分析学生为什么答错，返回 JSON:
{{
    "error_type": "错误类型 (concept_confusion/calculation_error/carelessness/misreading/knowledge_gap)",
    "misconception": "具体错误概念描述（中文，30-100字）",
    "suggestion": "针对性改进建议（中文，30-100字）",
    "related_knowledge": ["关联知识点1", "关联知识点2"],
    "confidence": 0.8
}}
只返回 JSON，不要其他文字。"""

    try:
        result = await llm_service.generate(
            messages=[
                {"role": "system", "content": "你是一个教育诊断专家，擅长分析学生的学习错误原因。"},
                {"role": "user", "content": prompt},
            ],
            task_type="fast",
            temperature=0.1,
            max_tokens=400,
        )

        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]

        analysis_result = json.loads(clean.strip())
        analysis_result.setdefault("error_type", "unknown")
        analysis_result.setdefault("misconception", "")
        analysis_result.setdefault("suggestion", "")
        analysis_result.setdefault("related_knowledge", [])
        analysis_result.setdefault("confidence", 0.5)

        return analysis_result

    except Exception as e:
        logger.warning("LLM 错因分析失败: %s", e)
        return {
            "error_type": "unknown",
            "misconception": "",
            "suggestion": "",
            "related_knowledge": [],
            "confidence": 0.0,
            "error_detail": str(e),
        }


def classify_error_basic(
    question: dict,
    user_answer: list[str],
    correct_answer: list[str],
    selected_option: Optional[dict] = None,
) -> dict:
    """
    基础错因分类（快速，无需 LLM）。

    基于 distractor_type 和答题模式做规则判断。
    当 LLM 不可用时作为 fallback。
    """
    # 1. 检查 distractor_type
    if selected_option and selected_option.get("distractor_type"):
        dt = selected_option["distractor_type"]
        dt_map = {
            "sign_error": "符号错误",
            "concept_confusion": "概念混淆",
            "partial_understanding": "部分理解",
            "common_mistake": "常见错误",
            "calculation_error": "计算失误",
            "unit_error": "单位错误",
            "formula_misuse": "公式误用",
        }
        return {
            "error_type": dt,
            "misconception": dt_map.get(dt, dt),
            "suggestion": "建议回顾相关基础概念",
            "related_knowledge": [],
            "confidence": 0.6,
        }

    # 2. 检查是否完全未作答
    if not user_answer or user_answer == [""]:
        return {
            "error_type": "knowledge_gap",
            "misconception": "未作答，可能完全不了解该知识点",
            "suggestion": "建议从基础概念开始学习",
            "related_knowledge": [],
            "confidence": 0.7,
        }

    return {
        "error_type": "unknown",
        "misconception": "",
        "suggestion": "",
        "related_knowledge": [],
        "confidence": 0.3,
    }