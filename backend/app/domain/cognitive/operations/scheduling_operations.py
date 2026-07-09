"""Scheduling 子系统操作 — 基于 Beta 不确定性的统一复习调度。

核心变更：
- 复习间隔由 Beta(α, β) 后验方差决定；
- 秘书系统可通过 adjustment_factor 进行修正；
- 保留 urgency 多因素加权与 next_action_type 选择。
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_TARGET_RETENTION = 0.85
_TARGET_UNCERTAINTY = 0.05
_BASE_INTERVAL_DAYS = 1.0

# urgency 权重
_W_RETENTION = 0.35
_W_MASTERY = 0.25
_W_CORE = 0.15
_W_STAGNATION = 0.15
_W_GOAL = 0.10


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _read_belief(belief_state: dict[str, Any]) -> tuple[float, float]:
    """读取信念参数并返回 (α, β)。"""
    alpha = max(0.1, float(belief_state.get("belief_alpha", 1.0)))
    beta = max(0.1, float(belief_state.get("belief_beta", 1.0)))
    return alpha, beta


@_registry.register(
    "update_scheduling",
    "基于 Beta 不确定性计算复习间隔、urgency 与下一步动作",
    params_schema={
        "scheduling_state": {"type": "object", "required": True},
        "belief_state": {"type": "object", "required": True},
        "last_practiced": {"type": "number", "required": False},
        "successful_reviews": {"type": "number", "required": False, "default": 0},
        "is_core": {"type": "boolean", "required": False, "default": False},
        "goal_distance": {"type": "number", "required": False, "default": -1},
        "stagnation_days": {"type": "number", "required": False, "default": 0.0},
        "adjustment_factor": {"type": "number", "required": False, "default": 1.0},
        "now": {"type": "number", "required": False},
    },
)
def update_scheduling(
    scheduling_state: dict[str, Any],
    belief_state: dict[str, Any],
    last_practiced: float | None = None,
    successful_reviews: float = 0,
    is_core: bool = False,
    goal_distance: float = -1,
    stagnation_days: float = 0.0,
    adjustment_factor: float = 1.0,
    now: float | None = None,
) -> dict[str, Any]:
    """基于 Beta 方差计算复习间隔，并综合多因素计算 urgency。"""
    now = now or time.time()
    last_practiced = last_practiced or now

    alpha, beta = _read_belief(belief_state)
    proficiency = alpha / (alpha + beta)
    total = alpha + beta

    # Beta 方差作为不确定性度量
    variance = alpha * beta / ((total ** 2) * (total + 1.0))
    uncertainty = math.sqrt(variance)

    # 间隔：不确定性高则短，不确定性低则长；秘书修正通过 adjustment_factor
    adjustment_factor = max(0.1, adjustment_factor)
    interval_days = _BASE_INTERVAL_DAYS * (_TARGET_UNCERTAINTY / max(uncertainty, 1e-6))
    interval_days *= adjustment_factor
    interval_days = max(0.1, min(365.0, interval_days))

    # 距上次练习经过的天数与保留率
    delta_days = max(0.0, (now - last_practiced) / 86400.0)
    retention = math.exp(-delta_days / max(interval_days, 0.1))
    retention = _clamp(retention)

    # urgency 多因素加权
    mastery_push = max(0.0, _TARGET_RETENTION - proficiency)
    stagnation_penalty = min(1.0, stagnation_days / 7.0)
    goal_push = 0.0 if goal_distance < 0 else 1.0 / (1.0 + goal_distance)

    urgency = (
        _W_RETENTION * (1.0 - retention)
        + _W_MASTERY * mastery_push
        + _W_CORE * (1.0 if is_core else 0.0)
        - _W_STAGNATION * stagnation_penalty
        + _W_GOAL * goal_push
    )
    urgency = _clamp(urgency)

    next_review = last_practiced + interval_days * 86400.0

    if urgency > 0.7:
        next_action_type = "review"
    elif stagnation_days > 7:
        next_action_type = "deep_processing"
    else:
        next_action_type = "practice"

    sched_after = {
        "sched_urgency": round(urgency, 4),
        "sched_next_review": round(next_review, 4),
        "sched_interval_days": round(interval_days, 4),
        "sched_next_action_type": next_action_type,
    }

    return {
        "subsystem": "scheduling",
        "method": "update_scheduling",
        "params": {
            "proficiency": round(proficiency, 3),
            "uncertainty": round(uncertainty, 4),
            "interval_days": round(interval_days, 2),
            "retention": round(retention, 3),
        },
        "result_summary": (
            f"urgency={urgency:.3f} interval={interval_days:.2f}d "
            f"next_review={next_review:.0f} action={next_action_type}"
        ),
        "scheduling_after": sched_after,
    }
