"""
Trend 子系统操作 — 掌握度趋势与波动分析。

注册操作:
- update_trend: 基于新掌握度更新趋势向量 (velocity/direction/volatility)
"""

from __future__ import annotations

import logging
import statistics
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()


@_registry.register(
    "update_trend",
    "更新趋势: 基于新 proficiency_mean 更新 velocity/stagnation/volatility/direction",
    params_schema={
        "trend": {"type": "object", "required": True},
        "new_mean": {"type": "number", "required": True},
        "now": {"type": "number", "required": False},
        "last_updated": {"type": "number", "required": False},
    },
)
def update_trend(
    trend: dict,
    new_mean: float,
    now: float | None = None,
    last_updated: float | None = None,
) -> dict:
    """EWMA 速度 + 停滞检测 + 波动率 + 方向判定。"""
    now = now or time.time()
    last_updated = last_updated or now

    recent = list(trend.get("recent_proficiencies", []))
    recent.append(new_mean)
    # 保留最近 20 个采样点
    if len(recent) > 20:
        recent = recent[-20:]

    # velocity: EWMA of differences
    diffs = []
    for i in range(1, len(recent)):
        diffs.append(recent[i] - recent[i - 1])
    ewma = trend.get("velocity_ewma", 0.0)
    alpha = 0.3
    for d in diffs:
        ewma = alpha * d + (1 - alpha) * ewma

    # stagnation: hours since last meaningful change
    stagnation_days = trend.get("stagnation_days", 0.0)
    elapsed_days = (now - last_updated) / 86400.0
    if abs(ewma) < 0.01:
        stagnation_days += elapsed_days
    else:
        stagnation_days = 0.0

    # volatility: std of recent
    volatility = statistics.stdev(recent) if len(recent) >= 2 else 0.0

    # direction
    if volatility > 0.15:
        direction = "volatile"
    elif ewma > 0.02:
        direction = "ascending"
    elif ewma < -0.02:
        direction = "descending"
    else:
        direction = "plateau"

    trend_after = {
        "recent_proficiencies": recent,
        "velocity_ewma": round(ewma, 4),
        "stagnation_days": round(stagnation_days, 2),
        "volatility_std": round(volatility, 4),
        "direction": direction,
    }

    return {
        "subsystem": "trend",
        "method": "update_trend",
        "params": {"new_mean": new_mean, "samples": len(recent)},
        "result_summary": (
            f"velocity={ewma:.3f} direction={direction} "
            f"volatility={volatility:.3f}"
        ),
        "trend_after": trend_after,
    }
