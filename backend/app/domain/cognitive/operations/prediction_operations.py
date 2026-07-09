"""Prediction 子系统操作 — 预测编码与误差检测"""

from __future__ import annotations

import logging

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_ERROR_THRESHOLD = 0.25


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "update_prediction",
    "更新预测：基于前序节点 proficiency 加权平均与观测值计算预测误差",
    params_schema={
        "prediction_state": {"type": "object", "required": True},
        "observed_proficiency": {"type": "number", "required": True},
        "predecessor_proficiencies": {"type": "array", "required": False},
        "predecessor_strengths": {"type": "array", "required": False},
    },
)
def update_prediction(
    prediction_state: dict,
    observed_proficiency: float,
    predecessor_proficiencies: list[float] | None = None,
    predecessor_strengths: list[float] | None = None,
) -> dict:
    """top_down_mean = 前序节点 proficiency 的加权平均。"""
    predecessors = predecessor_proficiencies or []
    strengths = predecessor_strengths or []
    if len(strengths) < len(predecessors):
        strengths.extend([0.5] * (len(predecessors) - len(strengths)))

    if predecessors and strengths:
        total_strength = sum(strengths)
        if total_strength > 0:
            top_down_mean = sum(p * s for p, s in zip(predecessors, strengths)) / total_strength
        else:
            top_down_mean = sum(predecessors) / len(predecessors)
        top_down_mean = _clamp(top_down_mean)
        observed = _clamp(observed_proficiency)
        prediction_error = observed - top_down_mean
        error_flag = abs(prediction_error) > _ERROR_THRESHOLD
    else:
        # 无前序节点时：保留现有预测，不生成无意义误差标志
        top_down_mean = _clamp(
            float(prediction_state.get("pred_top_down_mean", 0.0)) or 0.5
        )
        observed = _clamp(observed_proficiency)
        prediction_error = 0.0
        error_flag = False

    pred_after = {
        "pred_top_down_mean": round(top_down_mean, 4),
        "pred_prediction_error": round(prediction_error, 4),
        "pred_error_flag": error_flag,
    }

    return {
        "subsystem": "prediction",
        "method": "update_prediction",
        "params": {"observed": observed, "predicted": top_down_mean},
        "result_summary": (
            f"predicted={top_down_mean:.3f} observed={observed:.3f} "
            f"error={prediction_error:.3f} flag={error_flag}"
        ),
        "prediction_after": pred_after,
    }
