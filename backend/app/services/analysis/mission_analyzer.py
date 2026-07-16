"""LI-01 Mission Intelligence — Mission 理解分析服务。

职责:
  把用户要学的东西，转换成苹果果可以理解的学习对象。

不做:
  - 不生成学习内容
  - 不推荐练习
  - 不决定学习顺序
  - 不更新 Learner Model

原则:
  P2 — 理解先于干预（理解 Mission 才能做后续决策）
  P4 — 隔离能力（只写 mission.analysis，不碰其他命名空间）
  P7 — 不确定是一等公民（confidence < 0.5 时下游降级）
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.domain.session.runtime_context import MissionAnalysis
from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)


# ── System Prompt ────────────────────────────────────────

MISSION_ANALYZER_PROMPT = """你是一个学习分析引擎。给定一个学习目标，分析它并输出结构化理解。

输出必须是严格的 JSON，不要包含其他文本。JSON Schema:

{
  "concepts": [
    {
      "name": "概念名称",
      "importance": "high" | "medium" | "low",
      "description": "简短的说明"
    }
  ],
  "dependencies": [
    {
      "concept": "前置知识名称",
      "importance": "required" | "recommended"
    }
  ],
  "learning_objectives": [
    "用户角度的学习目标1，以'能够...'开头",
    "用户角度的学习目标2"
  ],
  "difficulty_spots": [
    {
      "point": "具体难点",
      "common_misconception": "常见误区",
      "difficulty_level": 3
    }
  ],
  "practice_strategy": {
    "type": "explanation" | "comparison" | "correction",
    "focus": "练习重点"
  },
  "reflection_focus": [
    "反思引导问题1",
    "反思引导问题2"
  ],
  "growth_signals": {
    "expected_gains": ["预期收获1"],
    "observation_points": [
      "判断用户是否真正理解的观察角度"
    ]
  }
}

规则:
- difficulty_level: 1-5，1 最简单，5 最难
- learning_objectives 从用户视角写，不是系统视角
- reflection_focus 必须是开放问题，不能是"是/否"问题
- growth_signals.expected_gains 是用户能获得的能力
- growth_signals.observation_points 是判断用户是否理解的观察角度"""


def _build_prompt(mission_title: str, learner_context: str = "", previous_growth_context: str = "") -> list[dict]:
    """构造 LLM 消息列表。

    Args:
        mission_title: 用户输入的学习目标标题
        learner_context: 学习者上下文摘要（可选，用于个性化）
        previous_growth_context: 上次学习记录摘要（可选，用于连续性）

    Returns:
        OpenAI 格式的 messages list
    """
    user_content = f"学习目标：{mission_title}\n"
    if learner_context:
        user_content += f"\n学习者背景：\n{learner_context}"
    if previous_growth_context:
        user_content += f"\n上次学习情况：\n{previous_growth_context}"
    user_content += "\n\n请分析这个学习目标，输出 JSON。"

    return [
        {"role": "system", "content": MISSION_ANALYZER_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_response(raw: str) -> Optional[MissionAnalysis]:
    """解析 LLM 返回的 JSON 字符串为 MissionAnalysis。

    Args:
        raw: LLM 返回的原始字符串（应为 JSON）

    Returns:
        MissionAnalysis 实例，解析失败时返回 None
    """
    # 清理可能的 markdown 代码块包裹
    text = raw.strip()
    if text.startswith("```"):
        # 移除 ```json ... ``` 包裹
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("MissionAnalyzer: failed to parse LLM response as JSON: %s", e)
        return None

    # 验证必需字段
    required = ["concepts", "learning_objectives", "difficulty_spots",
                 "reflection_focus", "growth_signals"]
    for field in required:
        if field not in data:
            logger.warning("MissionAnalyzer: missing required field '%s' in LLM response", field)
            return None

    try:
        return MissionAnalysis(**data)
    except Exception as e:
        logger.warning("MissionAnalyzer: MissionAnalysis validation failed: %s", e)
        return None


def _summarize_learner_context(learner_context) -> str:
    """将 LearnerContext 简化为一段文本，用于 LLM 个性化分析。

    Args:
        learner_context: RuntimeContext 中的 learner 字段

    Returns:
        简短的文本描述
    """
    if not learner_context:
        return ""

    parts = []
    profile = getattr(learner_context, "profile", None)
    if profile:
        subjects = getattr(profile, "subjects", [])
        if subjects:
            parts.append(f"学习科目：{', '.join(subjects)}")
        grade = getattr(profile, "grade_level", None)
        if grade:
            parts.append(f"学习阶段：{grade}")

    knowledge = getattr(learner_context, "knowledge", {})
    if knowledge:
        known = [
            sid for sid, state in knowledge.items()
            if state.proficiency >= 0.5
        ]
        if known:
            parts.append(f"已掌握的概念：{', '.join(known[:5])}")

    return "\n".join(parts)


# ── Main Service ─────────────────────────────────────────


class MissionAnalyzer:
    """Mission 理解分析器。

    LI-01 核心服务。分析 Mission 标题，输出结构化 MissionAnalysis。
    """

    async def analyze(
        self,
        mission_title: str,
        learner_context=None,
        previous_growth_context: str = "",
    ) -> Optional[MissionAnalysis]:
        """分析 Mission。

        Args:
            mission_title: 用户输入的学习目标标题
            learner_context: 可选，LearnerContext 对象，用于个性化
            previous_growth_context: 上次学习记录文本（用于连续性）

        Returns:
            MissionAnalysis | None — 分析成功返回实例，失败返回 None
        """
        context_text = _summarize_learner_context(learner_context)
        messages = _build_prompt(mission_title, context_text, previous_growth_context)

        try:
            raw = await llm_service.generate(
                messages=messages,
                task_type="fast",          # Mission 分析使用轻量模型
                temperature=0.3,           # 低温度保证输出稳定性
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("MissionAnalyzer: LLM call failed for '%s': %s",
                         mission_title, e)
            return None

        result = _parse_response(raw)
        if result is None:
            logger.warning("MissionAnalyzer: failed to produce valid MissionAnalysis for '%s'",
                           mission_title)

        return result


# ── Module-level convenience ─────────────────────────────

_analyzer: Optional[MissionAnalyzer] = None


def get_mission_analyzer() -> MissionAnalyzer:
    """获取全局 MissionAnalyzer 单例。"""
    global _analyzer
    if _analyzer is None:
        _analyzer = MissionAnalyzer()
    return _analyzer
