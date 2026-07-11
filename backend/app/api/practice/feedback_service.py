"""Practice Feedback Service — 按 attempt_id 组装答题后信息增益反馈。

数据来源优先级：
1. cognitive_events.event_type='cognitive_reward'（按 practice_event.id 关联）
2. cognitive_node_projections 当前投影（兜底）
3. practice_attempts 基础答题信息（ always 返回）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _safe_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def _belief_proficiency(alpha: float, beta: float) -> float:
    total = alpha + beta
    if total <= 0:
        return 0.0
    return alpha / total


def _uncertainty_from_entropy(entropy: float) -> float:
    """熵是不确定性的一种度量，这里直接返回归一化前的熵值。"""
    return entropy


def get_feedback(user_id: str, attempt_id: str) -> dict:
    """根据 attempt_id 返回信息增益、掌握度变化与元认知建议。"""
    from app.infrastructure.db.database import get_db

    db = get_db()

    # 1. 校验 attempt 归属
    attempt = db.fetchone(
        """SELECT id, session_id, question_id, user_id, is_correct,
                  user_answer, time_spent_seconds, confidence_before, created_at
           FROM practice_attempts
           WHERE id = %s AND user_id = %s""",
        (attempt_id, user_id),
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="attempt not found")

    session_id = attempt["session_id"]
    question_id = attempt["question_id"]

    # 2. 查找 practice_event（最新一条匹配 session_id + question_id 的记录）
    pe = db.fetchone(
        """SELECT id, node_id, timestamp
           FROM practice_events
           WHERE session_id = %s AND question_id = %s AND user_id = %s
           ORDER BY timestamp DESC LIMIT 1""",
        (session_id, question_id, user_id),
    )

    # 3. 查找 cognitive_reward
    reward_payload: dict[str, Any] | None = None
    if pe:
        reward_row = db.fetchone(
            """SELECT payload FROM cognitive_events
               WHERE event_type = 'cognitive_reward'
                 AND source_id = %s
                 AND user_id = %s
               ORDER BY created_at DESC LIMIT 1""",
            (pe["id"], user_id),
        )
        if reward_row:
            reward_payload = _safe_json(reward_row.get("payload"), {})

    # 4. 组装节点反馈
    nodes: list[dict[str, Any]] = []
    information_gain = 0.0
    uncertainty_reduction_percent = 0.0
    proficiency_before = 0.0
    proficiency_after = 0.0
    uncertainty_before = 0.0
    uncertainty_after = 0.0
    is_final = False

    if reward_payload:
        is_final = True
        information_gain = float(reward_payload.get("reward_value", 0.0))
        belief_before = _safe_json(reward_payload.get("belief_before"), {})
        belief_after = _safe_json(reward_payload.get("belief_after"), {})
        alpha_before = float(belief_before.get("alpha", 1.0))
        beta_before = float(belief_before.get("beta", 1.0))
        alpha_after = float(belief_after.get("alpha", 1.0))
        beta_after = float(belief_after.get("beta", 1.0))

        proficiency_before = _belief_proficiency(alpha_before, beta_before)
        proficiency_after = _belief_proficiency(alpha_after, beta_after)
        uncertainty_before = float(reward_payload.get("uncertainty_before", 0.0))
        uncertainty_after = float(reward_payload.get("uncertainty_after", 0.0))
        uncertainty_reduction_percent = float(reward_payload.get("uncertainty_reduction_percent", 0.0))

        node_id = reward_payload.get("node_id") or pe.get("node_id") if pe else None
        node_label = ""
        if node_id:
            node_row = db.fetchone(
                "SELECT label FROM knowledge_nodes WHERE id = %s AND user_id = %s",
                (node_id, user_id),
            )
            if node_row:
                node_label = node_row.get("label", "") or ""

        nodes.append({
            "node_id": node_id,
            "label": node_label,
            "information_gain": round(information_gain, 4),
            "proficiency_before": round(proficiency_before, 4),
            "proficiency_after": round(proficiency_after, 4),
        })
    elif pe:
        # 兜底：读取当前投影
        node_id = pe.get("node_id")
        if node_id:
            proj = db.fetchone(
                """SELECT belief_alpha, belief_beta, total_information_gain, last_information_gain
                   FROM cognitive_node_projections
                   WHERE node_id = %s AND user_id = %s""",
                (node_id, user_id),
            )
            if proj:
                alpha = float(proj.get("belief_alpha", 1.0))
                beta = float(proj.get("belief_beta", 1.0))
                proficiency_after = _belief_proficiency(alpha, beta)
                information_gain = float(proj.get("last_information_gain", 0.0))

                node_row = db.fetchone(
                    "SELECT label FROM knowledge_nodes WHERE id = %s AND user_id = %s",
                    (node_id, user_id),
                )
                node_label = (node_row.get("label", "") if node_row else "") or ""

                nodes.append({
                    "node_id": node_id,
                    "label": node_label,
                    "information_gain": round(information_gain, 4),
                    "proficiency_before": round(proficiency_before, 4),
                    "proficiency_after": round(proficiency_after, 4),
                })

    # 5. 元认知建议（复用现有逻辑）
    confidence_before = attempt.get("confidence_before")
    is_correct = bool(attempt["is_correct"])
    metacognition_advice = _get_metacognition_feedback(confidence_before, is_correct)

    # 6. 学习建议
    suggestions = _build_suggestions(
        is_correct=is_correct,
        proficiency_after=proficiency_after,
        nodes=nodes,
    )

    return {
        "attempt_id": attempt_id,
        "session_id": session_id,
        "question_id": question_id,
        "is_correct": is_correct,
        "submitted_at": attempt.get("created_at"),
        "is_final": is_final,
        "feedback": {
            "information_gain": round(information_gain, 4),
            "uncertainty_reduction_percent": round(uncertainty_reduction_percent, 2),
            "proficiency_before": round(proficiency_before, 4),
            "proficiency_after": round(proficiency_after, 4),
            "uncertainty_before": round(uncertainty_before, 4),
            "uncertainty_after": round(uncertainty_after, 4),
            "nodes": nodes,
        },
        "metacognition": {
            "advice": metacognition_advice,
            "confidence_before": confidence_before,
            "bias": _metacognition_bias(confidence_before, is_correct),
        },
        "suggestions": suggestions,
    }


def _get_metacognition_feedback(confidence_before: Any, is_correct: bool) -> str:
    """根据自信度和正确性返回元认知反馈文案（与 PracticeEngine 对齐）。"""
    if confidence_before is None:
        return ""
    try:
        confidence = int(confidence_before)
    except (TypeError, ValueError):
        return ""
    if confidence >= 3:
        if is_correct:
            return "你确实掌握了，自信是对的"
        return "⚠️ 元认知偏差：你以为掌握了但其实没有。建议重新学习推导过程。"
    if is_correct:
        return "💡 谦逊的正确：你比你以为的更懂。试着给别人讲一遍确认。"
    return "还有提升空间，继续努力"


def _metacognition_bias(confidence_before: Any, is_correct: bool) -> str:
    """返回元认知偏差类型。"""
    if confidence_before is None:
        return "unknown"
    try:
        confidence = int(confidence_before)
    except (TypeError, ValueError):
        return "unknown"
    if confidence >= 3:
        return "accurate" if is_correct else "overconfident"
    return "underconfident" if is_correct else "accurate"


def _build_suggestions(
    *,
    is_correct: bool,
    proficiency_after: float,
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """基于答题结果生成学习建议。"""
    suggestions: list[dict[str, Any]] = []
    if not is_correct:
        suggestions.append({
            "type": "review",
            "title": "回顾错题解析",
            "reason": "本次回答错误，建议重新理解知识点",
        })
    if nodes and proficiency_after < 0.7:
        suggestions.append({
            "type": "practice",
            "title": f"针对「{nodes[0].get('label') or '薄弱知识点'}」继续练习",
            "node_id": nodes[0].get("node_id"),
            "reason": "掌握度仍有提升空间",
        })
    if is_correct and proficiency_after >= 0.8:
        suggestions.append({
            "type": "expand",
            "title": "尝试更高难度或相关知识点",
            "reason": "当前知识点掌握较好，可以横向拓展",
        })
    return suggestions
