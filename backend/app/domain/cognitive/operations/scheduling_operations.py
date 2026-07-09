"""Scheduling 子系统操作 — 复习调度与 urgency 计算"""

from __future__ import annotations

import logging
import math
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_DEFAULT_BASE_STRENGTH = 1.0
_DEFAULT_HALFLIFE_FACTOR = 2.0
_TARGET_RETENTION = 0.85

# urgency 权重
_W_RETENTION = 0.35
_W_MASTERY = 0.25
_W_CORE = 0.15
_W_STAGNATION = 0.15
_W_GOAL = 0.10


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "update_scheduling",
    "更新调度：基于掌握度、稳定性、目标距离计算 urgency 与下次复习时间",
    params_schema={
        "scheduling_state": {"type": "object", "required": True},
        "proficiency": {"type": "number", "required": True},
        "stability": {"type": "number", "required": False, "default": 0.5},
        "stagnation_days": {"type": "number", "required": False, "default": 0.0},
        "is_core": {"type": "boolean", "required": False, "default": False},
        "goal_distance": {"type": "number", "required": False, "default": -1},
        "last_practiced": {"type": "number", "required": False},
        "successful_reviews": {"type": "number", "required": False, "default": 0},
        "now": {"type": "number", "required": False},
    },
)
def update_scheduling(
    scheduling_state: dict,
    proficiency: float,
    stability: float = 0.5,
    stagnation_days: float = 0.0,
    is_core: bool = False,
    goal_distance: float = -1,
    last_practiced: float | None = None,
    successful_reviews: float = 0,
    now: float | None = None,
) -> dict:
    """计算 retention、urgency 和 next_review。"""
    now = now or time.time()
    last_practiced = last_practiced or now

    proficiency = _clamp(proficiency)
    stability = _clamp(stability, 0.01, 1.0)

    # 记忆强度随成功复习增长
    strength = _DEFAULT_BASE_STRENGTH * (2 ** (successful_reviews / _DEFAULT_HALFLIFE_FACTOR))

    # 距上次练习的天数
    delta_days = max(0.0, (now - last_practiced) / 86400.0)
    retention = math.exp(-delta_days / strength) if strength > 0 else 0.0
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

    # 下次复习时间：为达到目标保留率所需的间隔
    if proficiency <= 0 or strength <= 0:
        next_review = now + 86400.0
    else:
        target_interval_days = -math.log(_TARGET_RETENTION) / math.log(2) * strength
        next_review = last_practiced + target_interval_days * 86400.0

    # 根据 urgency 选择下一步动作
    if urgency > 0.7:
        next_action_type = "review"
    elif stagnation_days > 7:
        next_action_type = "deep_processing"
    else:
        next_action_type = "practice"

    sched_after = {
        "sched_urgency": round(urgency, 4),
        "sched_next_review": round(next_review, 4),
        "sched_next_action_type": next_action_type,
    }

    return {
        "subsystem": "scheduling",
        "method": "update_scheduling",
        "params": {
            "proficiency": proficiency,
            "retention": round(retention, 3),
            "stagnation_days": stagnation_days,
        },
        "result_summary": (
            f"urgency={urgency:.3f} next_review={next_review:.0f} "
            f"action={next_action_type}"
        ),
        "scheduling_after": sched_after,
    }
