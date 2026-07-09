"""Metacognition 子系统操作 — 元认知校准"""

from __future__ import annotations

import logging
import statistics
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_RECENT_WINDOW = 20
_BIAS_OVERCONFIDENT = 0.1
_BIAS_UNDERCONFIDENT = -0.1


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "update_metacognition",
    "更新元认知：基于 confidence_before 与实际正确性计算校准误差",
    params_schema={
        "metacognition_state": {"type": "object", "required": True},
        "confidence_before": {"type": "number", "required": True},
        "success": {"type": "boolean", "required": True},
        "now": {"type": "number", "required": False},
    },
)
def update_metacognition(
    metacognition_state: dict,
    confidence_before: float,
    success: bool,
    now: float | None = None,
) -> dict:
    """gap = confidence_before - correctness；计算 calibration_error 与方向。"""
    now = now or time.time()

    confidence = _clamp(confidence_before)
    correctness = 1.0 if success else 0.0
    gap = confidence - correctness

    recent_gaps = list(metacognition_state.get("_recent_gaps", []))
    recent_gaps.append(gap)
    if len(recent_gaps) > _RECENT_WINDOW:
        recent_gaps = recent_gaps[-_RECENT_WINDOW:]

    calibration_error = sum(abs(g) for g in recent_gaps) / len(recent_gaps) if recent_gaps else 0.0
    signed_bias = statistics.mean(recent_gaps) if recent_gaps else 0.0

    if signed_bias > _BIAS_OVERCONFIDENT:
        direction = "overconfident"
    elif signed_bias < _BIAS_UNDERCONFIDENT:
        direction = "underconfident"
    else:
        direction = "accurate"

    meta_after = {
        "meta_self_assessment": round(confidence, 4),
        "meta_calibration_error": round(calibration_error, 4),
        "meta_direction": direction,
        "_recent_gaps": recent_gaps,
    }

    return {
        "subsystem": "metacognition",
        "method": "update_metacognition",
        "params": {"confidence_before": confidence, "success": success},
        "result_summary": (
            f"calibration_error={calibration_error:.3f} direction={direction}"
        ),
        "metacognition_after": meta_after,
    }
