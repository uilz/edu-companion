"""
错题智能归因服务 v1.0

对答错的题目，调用 LLM 进行深度错因分析。
从 11 种错因标签中选出最匹配的 1-2 个，并生成分析文字和改进建议。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)

# 错因分类体系
ERROR_CATEGORIES = {
    "concept_gap": "前置知识缺失 — 缺少理解当前概念所需的基础知识",
    "concept_fuzzy": "概念理解模糊 — 知道大概但不精确，边界不清",
    "concept_forgotten": "知识遗忘 — 学过但忘了，需要复习",
    "calc_sign": "符号/正负号错误 — 符号拿反或正负号搞错",
    "calc_skip": "步骤遗漏 — 解题过程中跳步或忽略中间步骤",
    "calc_careless": "粗心 — 计算过程正确但最终结果抄错或笔误",
    "read_ignore": "忽略关键条件 — 题目中的关键约束或条件未被使用",
    "read_misunderstand": "理解偏差 — 对题目要求的理解与题意不符",
    "method_wrong_formula": "用错公式 — 选用了错误的公式或定理",
    "method_no_approach": "不会入手 — 完全不知道从哪里开始解题",
    "method_fixation": "思维定势 — 套用熟悉的解法但在此题不适用",
}

CATEGORY_LABELS_CN = {
    "concept_gap": "前置知识缺失",
    "concept_fuzzy": "概念理解模糊",
    "concept_forgotten": "知识遗忘",
    "calc_sign": "符号错误",
    "calc_skip": "步骤遗漏",
    "calc_careless": "粗心",
    "read_ignore": "忽略关键条件",
    "read_misunderstand": "理解偏差",
    "method_wrong_formula": "用错公式",
    "method_no_approach": "不会入手",
    "method_fixation": "思维定势",
}

CATEGORY_GROUP = {
    "concept_gap": "概念",
    "concept_fuzzy": "概念",
    "concept_forgotten": "概念",
    "calc_sign": "计算",
    "calc_skip": "计算",
    "calc_careless": "计算",
    "read_ignore": "审题",
    "read_misunderstand": "审题",
    "method_wrong_formula": "方法",
    "method_no_approach": "方法",
    "method_fixation": "方法",
}


async def analyze_error(
    question_text: str,
    user_answer: str,
    correct_answer: str,
    error_type: str = "",
    skill_id: str = "",
) -> dict[str, Any]:
    """
    调用 LLM 分析错题深层原因。

    Returns:
        {
            "primary": "concept_fuzzy",
            "secondary": "calc_careless",
            "primary_label": "概念理解模糊",
            "group": "概念",
            "analysis": "这段题目考察的是...",
            "recommendation": "建议先复习...再练习...",
        }
    """
    categories_desc = "\n".join(
        f"  - {k}: {v}" for k, v in ERROR_CATEGORIES.items()
    )

    prompt = f"""分析以下错题的深层原因。

题目: {question_text[:500]}
学生答案: {user_answer[:200]}
正确答案: {correct_answer[:200]}
知识点: {skill_id}

请从以下 11 种错因中选择最匹配的 1-2 个：

{categories_desc}

要求：
1. primary: 最可能的错因标签（必须是上面列表中的 key）
2. secondary: 次可能的错因标签（选填，可为 null）
3. analysis: 2-3 句话分析为什么学生会犯这个错误（中文，口语化，像老师在说话）
4. recommendation: 1-2 条具体可行的改进建议（中文）

只返回 JSON，不要其他文字：
{{"primary": "...", "secondary": "...", "analysis": "...", "recommendation": "..."}}"""

    try:
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400,
        )
        content = response.get("content", "") if isinstance(response, dict) else str(response)

        # 提取 JSON
        json_match = content.strip()
        if "```" in json_match:
            json_match = json_match.split("```")[1]
            if json_match.startswith("json"):
                json_match = json_match[4:]
            json_match = json_match.strip()

        result = json.loads(json_match)

        # 补充 label 和 group
        primary = result.get("primary", "")
        if primary in CATEGORY_LABELS_CN:
            result["primary_label"] = CATEGORY_LABELS_CN[primary]
            result["group"] = CATEGORY_GROUP.get(primary, "其他")
        else:
            result["primary_label"] = primary
            result["group"] = "其他"

        return result

    except Exception as e:
        logger.warning(f"Error attribution failed: {e}")
        return {
            "primary": "concept_fuzzy",
            "secondary": None,
            "primary_label": "概念理解模糊",
            "group": "概念",
            "analysis": "暂无法自动分析该错题，请手动查看。",
            "recommendation": "建议对照正确答案重新理解解题步骤。",
        }


def get_error_stats(entries: list[dict]) -> dict[str, Any]:
    """
    从错题列表中统计错因分布。

    返回:
        {
            "total": 总数,
            "by_group": {"概念": 5, "计算": 3, ...},
            "by_category": {"concept_fuzzy": 3, ...},
            "top_weak_skills": ["calculus_limit", ...]
        }
    """
    by_group: dict[str, int] = {}
    by_category: dict[str, int] = {}
    skill_counts: dict[str, int] = {}

    for entry in entries:
        attribution = entry.get("attribution") or {}
        group = attribution.get("group", "未分类")
        primary = attribution.get("primary", "unknown")
        skill = entry.get("skill_id", "unknown")

        by_group[group] = by_group.get(group, 0) + 1
        by_category[primary] = by_category.get(primary, 0) + 1
        skill_counts[skill] = skill_counts.get(skill, 0) + 1

    top_skills = sorted(skill_counts.items(), key=lambda x: -x[1])[:5]

    return {
        "total": len(entries),
        "by_group": by_group,
        "by_category": by_category,
        "top_weak_skills": [s[0] for s in top_skills],
    }
