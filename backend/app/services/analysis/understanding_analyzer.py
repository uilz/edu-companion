"""LI-02 Understanding Intelligence — 理解分析服务。

职责:
  观察用户现在是怎么理解的。不是评价，不是打分，不是教育。只是观察。

不做:
  - 不评价对错
  - 不打分
  - 不教育
  - 不推荐下一步（LI-04 负责）

原则:
  P1 — 观察先于评价（使用 O-E-H 三元组，不是标签）
  P4 — 隔离能力（只写 understanding 命名空间）
  P7 — 不确定是一等公民（所有 hypothesis 标注 confidence）
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.domain.session.runtime_context import UnderstandingAnalysis
from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)


# ── System Prompt ────────────────────────────────────────

UNDERSTANDING_ANALYZER_PROMPT = """你是一个学习观察引擎。给定用户写的理解文本和参考材料，观察用户目前是怎么理解的。

输出必须是严格的 JSON，不要包含其他文本。JSON Schema:

{
  "concept_observations": [
    {
      "concept": "概念名称",
      "observation": "用户表达了什么 / 没表达什么",
      "evidence": "原文引用（用户的原话）",
      "hypothesis": "苹果果的假设——用户处于什么状态",
      "confidence": 0.85
    }
  ],
  "reasoning_evidence": {
    "uses_own_words": true,
    "makes_connections": ["用户建立的关联1"],
    "asks_questions": ["用户提出的问题1"]
  },
  "gaps": [
    {
      "concept": "概念名称",
      "observation": "观察到什么差距",
      "evidence": "原文证据",
      "hypothesis": "对差距原因的假设",
      "severity": 2,
      "confidence": 0.70
    }
  ],
  "metacognitive_signals": {
    "aware_of_gap": false,
    "overconfident_on": ["用户过度自信的概念"]
  },
  "learner_delta": {
    "knowledge_updates": [
      {
        "skill_id": "概念ID",
        "confidence_shift": 0.3,
        "evidence": "判断依据"
      }
    ],
    "reasoning_insights": ["对用户推理模式的观察"],
    "growth_insights": ["对用户学习成长的观察"]
  },
  "guidance_question": "如果存在差距且置信度>=0.5，生成开放式引导问题；否则为null"
}

规则:
- 使用 Observation / Evidence / Hypothesis 三元组——不是标签
  - observation：客观描述了用户表达了什么或没表达什么
  - evidence：用户原文引用
  - hypothesis：苹果果的假设，不是事实判定
- confidence: 0.0 ~ 1.0。低于 0.5 时不触发引导
- severity: 1-3（1=轻微，2=中等，3=重大）
- 不计算分数。不评价"对"或"错"
- learner_delta 只包含观察方向，不是修正指令
- guidance_question 必须开放。低于 0.5 置信度时设为 null
- learner_delta.knowledge_updates.confidence_shift 范围 -1 到 +1
"""


def _build_prompt(
    mission_title: str,
    mission_analysis: str,
    user_text: str,
    reference_text: str,
) -> list[dict]:
    """构造 LLM 消息列表。"""
    user_content = f"""学习目标：{mission_title}

任务分析（MissionAnalysis）：
{mission_analysis}

用户写的理解：
{user_text}

参考材料：
{reference_text}

请观察用户的理解情况，输出 JSON。"""

    return [
        {"role": "system", "content": UNDERSTANDING_ANALYZER_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_response(raw: str) -> Optional[UnderstandingAnalysis]:
    """解析 LLM 返回的 JSON 字符串为 UnderstandingAnalysis。"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("UnderstandingAnalyzer: failed to parse JSON: %s", e)
        return None

    required = ["concept_observations", "reasoning_evidence",
                 "gaps", "metacognitive_signals", "learner_delta"]
    for field in required:
        if field not in data:
            logger.warning("UnderstandingAnalyzer: missing required field '%s'", field)
            return None

    try:
        return UnderstandingAnalysis(**data)
    except Exception as e:
        logger.warning("UnderstandingAnalyzer: UnderstandingAnalysis validation failed: %s", e)
        return None


def _extract_guidance(analysis: UnderstandingAnalysis) -> Optional[str]:
    """从 UnderstandingAnalysis 中提取引导问题。

    规则:
    - gaps 为空 → None
    - 所有 gap.confidence < 0.5 → None（P7）
    - 有 confidence >= 0.5 的 gap → 返回 guidance_question
    """
    if not analysis.gaps:
        return None

    # 检查是否有高置信度的 gap
    has_high_conf_gap = any(g.confidence >= 0.5 for g in analysis.gaps)
    if not has_high_conf_gap:
        return None

    # guidance_question 由 LLM 在 JSON 中提供
    # 这里我们保持与已有 response 的兼容性
    return None  # LLM 已经返回了 guidance_question


# ── Main Service ─────────────────────────────────────────


class UnderstandingAnalyzer:
    """理解分析器。

    LI-02 核心服务。分析用户写的理解，输出 UnderstandingAnalysis。
    """

    async def analyze(
        self,
        mission_title: str,
        mission_analysis_str: str,
        user_text: str,
        reference_text: str,
    ) -> Optional[UnderstandingAnalysis]:
        """分析用户的理解。

        Args:
            mission_title: 学习目标标题
            mission_analysis_str: MissionAnalysis 的字符串表示
            user_text: 用户写的理解文本
            reference_text: 参考材料文本

        Returns:
            UnderstandingAnalysis | None
        """
        messages = _build_prompt(
            mission_title=mission_title,
            mission_analysis=mission_analysis_str,
            user_text=user_text,
            reference_text=reference_text,
        )

        try:
            raw = await llm_service.generate(
                messages=messages,
                task_type="fast",
                temperature=0.3,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("UnderstandingAnalyzer: LLM call failed: %s", e)
            return None

        result = _parse_response(raw)
        if result is None:
            logger.warning("UnderstandingAnalyzer: failed to produce valid analysis")
            return None

        return result


# ── Module-level convenience ─────────────────────────────

_analyzer: Optional[UnderstandingAnalyzer] = None


def get_understanding_analyzer() -> UnderstandingAnalyzer:
    """获取全局 UnderstandingAnalyzer 单例。"""
    global _analyzer
    if _analyzer is None:
        _analyzer = UnderstandingAnalyzer()
    return _analyzer
