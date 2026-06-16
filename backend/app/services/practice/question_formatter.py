"""
QuestionFormatter — 题目标准化、校验、质量评分

纯函数，无 I/O 依赖，可独立单元测试。
"""

from __future__ import annotations

from typing import Optional

from app.schemas.practice import BloomLevel


# ── Bloom 层级中英文映射 ──
BLOOM_ZH_MAP = {
    "记忆": BloomLevel.REMEMBER,
    "remember": BloomLevel.REMEMBER,
    "理解": BloomLevel.UNDERSTAND,
    "understand": BloomLevel.UNDERSTAND,
    "应用": BloomLevel.APPLY,
    "apply": BloomLevel.APPLY,
    "分析": BloomLevel.ANALYZE,
    "analyze": BloomLevel.ANALYZE,
    "评价": BloomLevel.EVALUATE,
    "evaluate": BloomLevel.EVALUATE,
    "创造": BloomLevel.CREATE,
    "create": BloomLevel.CREATE,
}

# ── 题型映射 ──
CONTENT_TYPE_MAP = {
    "单选": "choice",
    "choice": "choice",
    "选择": "choice",
    "多选": "multiple",
    "multiple": "multiple",
    "填空": "fill",
    "fill": "fill",
    "解答": "free_form",
    "free_form": "free_form",
    "计算": "calculation",
    "calculation": "calculation",
}

# ── AI 质量校验 ──


def validate_question(question_data: dict) -> list[str]:
    """校验 AI 输出完整性，返回缺失字段列表"""
    errors = []
    if not question_data.get("stem"):
        errors.append("题干为空")
    if not question_data.get("answer"):
        errors.append("答案为空")
    qtype = question_data.get("question_type", "choice")
    if qtype in ("choice", "single", "multiple"):
        opts = question_data.get("options", [])
        if len(opts) < 2:
            errors.append("选择题选项不足")
        else:
            correct_count = sum(1 for o in opts if o.get("is_correct"))
            if correct_count == 0:
                errors.append("无正确答案标记")
    return errors


def score_quality(question: dict) -> float:
    """对题目质量评分 0~1"""
    score = 0.5
    if question.get("analysis") or question.get("explanation"):
        score += 0.15
    hints = question.get("hints", [])
    if len(hints) >= 2:
        score += 0.1
    tags = question.get("tags", [])
    if len(tags) >= 2:
        score += 0.05
    cognitive_ids = question.get("cognitive_node_ids", [])
    if cognitive_ids and len(cognitive_ids) > 0:
        score += 0.1
    return min(1.0, max(0.1, score))


def extract_answer(question_data) -> list:
    """从 AI 输出或 Question 对象提取答案列表"""
    q = question_data
    if hasattr(q, "answer"):
        ans = q.answer
        if ans is None:
            return []
        if isinstance(ans, list):
            return ans
        return [ans]
    if isinstance(q, dict):
        ans = q.get("answer") or []
        if isinstance(ans, list):
            return ans
        return [ans]
    return []


def extract_options(question_data) -> list[dict]:
    """从 AI 输出或 Question 对象提取选项"""
    q = question_data
    if hasattr(q, "options") and q.options:
        return [
            {"letter": opt.letter, "text": opt.text, "is_correct": opt.is_correct,
             "distractor_type": getattr(opt, "distractor_type", "")}
            for i, opt in enumerate(q.options)
        ]
    if isinstance(q, dict):
        return q.get("options", [])
    return []


def map_difficulty(d: float) -> int:
    """将 0~1 浮点难度映射为 1~5 整数"""
    if d < 0.2:
        return 1
    if d < 0.4:
        return 2
    if d < 0.6:
        return 3
    if d < 0.8:
        return 4
    return 5


def parse_bloom_level(level: str | BloomLevel) -> BloomLevel:
    """解析 Bloom 级别"""
    if isinstance(level, BloomLevel):
        return level
    return BLOOM_ZH_MAP.get(level.lower(), BloomLevel.APPLY)


def parse_content_type(ct: str) -> str:
    """解析题型"""
    return CONTENT_TYPE_MAP.get(ct, ct)
