"""Trend 子系统操作 — 掌握度趋势与波动分析"""

from __future__ import annotations

import logging
import statistics
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_VELOCITY_ALPHA = 0.3
_RECENT_WINDOW = 20
_DIRECTION_THRESHOLD = 0.02
_VOLATILITY_THRESHOLD = 0.15


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "update_trend",
    "更新趋势：基于新 proficiency 更新 velocity/stability/volatility/direction",
    params_schema={
        "trend_state": {"type": "object", "required": True},
        "new_proficiency": {"type": "number", "required": True},
        "now": {"type": "number", "required": False},
        "last_practiced": {"type": "number", "required": False},
    },
)
def update_trend(
    trend_state: dict,
    new_proficiency: float,
    now: float | None = None,
    last_practiced: float | None = None,
) -> dict:
    """EWMA 速度 + 停滞检测 + 波动率 + 方向判定。"""
    now = now or time.time()

    velocity = float(trend_state.get("trend_velocity", 0.0))
    stagnation_days = float(trend_state.get("trend_stagnation_days", 0.0))
    direction = trend_state.get("trend_direction", "plateau")

    recent = list(trend_state.get("_recent_proficiencies", []))
    recent.append(_clamp(new_proficiency))
    if len(recent) > _RECENT_WINDOW:
        recent = recent[-_RECENT_WINDOW:]

    # velocity: EWMA of differences
    if len(recent) >= 2:
        delta = recent[-1] - recent[-2]
        velocity = _VELOCITY_ALPHA * delta + (1 - _VELOCITY_ALPHA) * velocity

    # volatility: std of recent
    volatility = statistics.stdev(recent) if len(recent) >= 2 else 0.0
    stability = 1.0 - _clamp(volatility / 0.3)

    # stagnation: days since last meaningful increase
    if last_practiced:
        elapsed_days = max(0.0, (now - last_practiced) / 86400.0)
        if new_proficiency <= max(recent[:-1] + [0.0]):
            stagnation_days += elapsed_days
        else:
            stagnation_days = 0.0
    else:
        if abs(velocity) < _DIRECTION_THRESHOLD:
            stagnation_days += 1.0 / 24.0  # 默认按小时累积
        else:
            stagnation_days = 0.0

    # direction
    if volatility > _VOLATILITY_THRESHOLD:
        direction = "volatile"
    elif velocity > _DIRECTION_THRESHOLD:
        direction = "ascending"
    elif velocity < -_DIRECTION_THRESHOLD:
        direction = "descending"
    else:
        direction = "plateau"

    trend_after = {
        "trend_velocity": round(velocity, 4),
        "trend_stability": round(stability, 4),
        "trend_volatility": round(volatility, 4),
        "trend_direction": direction,
        "trend_stagnation_days": round(stagnation_days, 2),
        "_recent_proficiencies": recent,
    }

    return {
        "subsystem": "trend",
        "method": "update_trend",
        "params": {"new_proficiency": new_proficiency, "samples": len(recent)},
        "result_summary": (
            f"velocity={velocity:.3f} direction={direction} "
            f"volatility={volatility:.3f} stagnation={stagnation_days:.1f}d"
        ),
        "trend_after": trend_after,
    }
