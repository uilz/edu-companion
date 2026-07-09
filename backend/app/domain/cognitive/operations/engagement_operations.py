"""Engagement 子系统操作 — 激励与连续练习"""

from __future__ import annotations

import logging
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_BASE_XP_CORRECT = 10
_BASE_XP_WRONG = 2
_MAX_SPEED_BONUS = 0.5
_OPTIMAL_TIME_SEC = 10.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _date_key(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


@_registry.register(
    "update_engagement",
    "更新激励：XP、连续天数、flow_score",
    params_schema={
        "engagement_state": {"type": "object", "required": True},
        "success": {"type": "boolean", "required": True},
        "difficulty": {"type": "number", "required": False},
        "time_spent": {"type": "number", "required": False, "default": 0.0},
        "now": {"type": "number", "required": False},
    },
)
def update_engagement(
    engagement_state: dict,
    success: bool,
    difficulty: float | None = None,
    time_spent: float = 0.0,
    now: float | None = None,
) -> dict:
    """根据练习结果更新 XP、连续天数与 flow score。"""
    now = now or time.time()

    xp = int(engagement_state.get("eng_xp", 0))
    streak_current = int(engagement_state.get("eng_streak_current", 0))
    streak_longest = int(engagement_state.get("eng_streak_longest", 0))
    last_practice_date = engagement_state.get("eng_last_practice_date", "")

    # 基础 XP
    base_xp = _BASE_XP_CORRECT if success else _BASE_XP_WRONG

    # 难度奖励
    diff_bonus = 0.0
    if difficulty is not None:
        diff_bonus = _clamp(difficulty) * 0.5

    # 速度奖励（越快越多，但不超过上限）
    speed_bonus = 0.0
    if time_spent > 0 and time_spent < _OPTIMAL_TIME_SEC:
        speed_bonus = (_OPTIMAL_TIME_SEC - time_spent) / _OPTIMAL_TIME_SEC * _MAX_SPEED_BONUS
        speed_bonus = _clamp(speed_bonus)

    # 连续奖励
    streak_bonus = min(1.0, streak_current / 30.0)

    xp_gain = int(base_xp * (1.0 + diff_bonus + speed_bonus + streak_bonus))
    xp += xp_gain

    # 连续天数
    today = _date_key(now)
    if today != last_practice_date:
        yesterday = _date_key(now - 86400.0)
        if last_practice_date == yesterday:
            streak_current += 1
        else:
            streak_current = 1
        streak_longest = max(streak_longest, streak_current)

    # flow_score: 理想成功率 0.8
    success_rate = 0.8  # 单次练习用目标值近似
    flow_score = 1.0 - abs((1.0 if success else 0.0) - success_rate) / success_rate
    flow_score = _clamp(flow_score)

    eng_after = {
        "eng_xp": xp,
        "eng_streak_current": streak_current,
        "eng_streak_longest": streak_longest,
        "eng_flow_score": round(flow_score, 4),
        "eng_last_practice_date": today,
    }

    return {
        "subsystem": "engagement",
        "method": "update_engagement",
        "params": {"success": success, "xp_gain": xp_gain},
        "result_summary": (
            f"xp={xp} streak={streak_current}/{streak_longest} "
            f"flow={flow_score:.3f}"
        ),
        "engagement_after": eng_after,
    }
