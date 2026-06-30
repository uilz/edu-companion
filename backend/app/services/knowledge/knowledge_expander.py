"""智能创造扩展引擎

LLM 驱动的知识点发散：拓展阅读、变式题、知识关联发现。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)

# ── Prompt 模板 ──

EXPAND_KNOWLEDGE_PROMPT = """你是一个教育 AI，负责将知识点做智能拓展。

## 知识点
{skill_name}: {explanation}

## 输出 JSON 格式
{{
  "deeper_explanation": "用生活化比喻+一句话深化，50字以内",
  "prerequisite_chain": ["前置知识1", "前置知识2"],
  "next_steps": ["同层知识A", "进阶知识B"],
  "real_world_example": "一个真实生活或工业中的应用案例，30字以内",
  "common_misconception": "这个知识点最常见的误解，20字以内",
  "fun_fact": "一个有趣的冷知识或历史故事，25字以内"
}}

只输出 JSON。"""

VARIANT_QUESTION_PROMPT = """你是一个出题老师。根据一道题目的知识点，出一道变式题。

## 原题
{question_text}

## 正确答案
{correct_answer}

## 新题要求
- 考查同一个知识点
- 但换一个角度或情境
- 难度相同
- 格式：四选一单选题

## 输出 JSON
{{
  "question": "变式题目",
  "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],
  "correct": 0,
  "explanation": "为什么选这个，100字以内"
}}

只输出 JSON。"""

DISCOVER_RELATIONS_PROMPT = """你是一个教育 AI，帮助学生发现知识之间的内在联系。

## 最近学习的知识点
{recent_skills}

## 输出 JSON
{{
  "discoveries": [
    {{
      "relation_type": "延伸 | 类比 | 应用 | 串联",
      "from_skill": "源知识点",
      "to_skill": "目标知识点",
      "insight": "一句话说明关联，30字以内"
    }}
  ]
}}

最多输出 3 条关联。只输出 JSON。"""


class KnowledgeExpander:
    """知识拓展引擎"""

    async def expand_knowledge(
        self, skill_name: str, explanation: str = ""
    ) -> dict[str, Any]:
        """拓展知识点：深入解释 + 前置 + 进阶 + 案例 + 误区 + 趣味"""
        try:
            prompt = EXPAND_KNOWLEDGE_PROMPT.format(
                skill_name=skill_name, explanation=explanation or skill_name
            )
            raw = llm_service.chat(
                system_prompt="你是一个教育 AI，只输出 JSON。",
                user_prompt=prompt,
            )
            data = json.loads(self._extract_json(raw))
            return {
                "skill_name": skill_name,
                **data,
            }
        except Exception as e:
            logger.warning(f"知识拓展 LLM 失败: {e}")
            return self._fallback(skill_name)

    async def generate_variant(
        self, question_text: str, correct_answer: str
    ) -> dict[str, Any]:
        """生成变式题"""
        try:
            prompt = VARIANT_QUESTION_PROMPT.format(
                question_text=question_text,
                correct_answer=correct_answer,
            )
            raw = llm_service.chat(
                system_prompt="你是一个出题老师，只输出 JSON。",
                user_prompt=prompt,
            )
            data = json.loads(self._extract_json(raw))
            return data
        except Exception as e:
            logger.warning(f"变式题生成 LLM 失败: {e}")
            return {
                "question": f"关于「{question_text[:20]}」的变式练习",
                "options": [
                    "A. 暂无生成（LLM 不可用）",
                    "B. 请稍后再试",
                    "C. 联系管理员",
                    "D. 以上都不对",
                ],
                "correct": 0,
                "explanation": "LLM 服务暂时不可用，已跳过变式题生成。",
            }

    async def discover_relations(
        self, recent_skills: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """发现最近知识点之间的关联"""
        if len(recent_skills) < 2:
            return []

        skill_text = "\n".join(
            f"- {s.get('name', s.get('id', '?'))}: {s.get('explanation', '')}"
            for s in recent_skills[:5]
        )
        try:
            prompt = DISCOVER_RELATIONS_PROMPT.format(recent_skills=skill_text)
            raw = llm_service.chat(
                system_prompt="你是一个教育 AI，只输出 JSON。",
                user_prompt=prompt,
            )
            data = json.loads(self._extract_json(raw))
            return data.get("discoveries", [])
        except Exception as e:
            logger.warning(f"知识关联发现 LLM 失败: {e}")
            return []

    def _extract_json(self, text: str) -> str:
        """从 LLM 回复中提取 JSON"""
        match = re.search(r"\{[\s\S]*\}", text)
        return match.group(0) if match else "{}"

    def _fallback(self, skill_name: str) -> dict[str, Any]:
        """LLM 不可用时的兜底"""
        return {
            "skill_name": skill_name,
            "deeper_explanation": f"暂时无法生成拓展内容，已记住你想了解「{skill_name}」，稍后可重试。",
            "prerequisite_chain": [],
            "next_steps": [],
            "real_world_example": "",
            "common_misconception": "",
            "fun_fact": "",
        }


# 全局实例
knowledge_expander = KnowledgeExpander()
