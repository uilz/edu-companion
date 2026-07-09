"""Activation 子系统操作 — ACT-R base-level + 网络传播"""

from __future__ import annotations

import logging
import math
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_DEFAULT_DECAY = 0.5
_DEFAULT_LATENCY_FACTOR = 500.0
_DEFAULT_RETRIEVAL_THRESHOLD = 0.0
_DEFAULT_RETRIEVAL_SLOPE = 1.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "activation_update",
    "基于练习事件更新 ACT-R base-level 激活与检索概率",
    params_schema={
        "activation_state": {"type": "object", "required": True},
        "event_timestamp": {"type": "number", "required": True},
        "neighbor_activations": {"type": "array", "required": False},
        "neighbor_strengths": {"type": "array", "required": False},
        "now": {"type": "number", "required": False},
    },
)
def activation_update(
    activation_state: dict,
    event_timestamp: float,
    neighbor_activations: list[float] | None = None,
    neighbor_strengths: list[float] | None = None,
    now: float | None = None,
) -> dict:
    """增量更新 base-level activation，结合网络传播。"""
    now = now or time.time()

    base_level = float(activation_state.get("act_base_level", 0.0))
    spread = float(activation_state.get("act_spread", 0.0))
    last_updated = float(activation_state.get("act_last_updated", now))
    decay = float(activation_state.get("decay", _DEFAULT_DECAY))

    # 新练习事件：在 base_level 上叠加一个脉冲
    # B_i = ln( Σ_j (t_j)^(-decay) )
    # 近似增量更新：A_new = log(exp(A_old) + (now - event_ts)^(-decay))
    # 为简化，直接加一个基于时间距离的脉冲
    age_seconds = max(1.0, now - event_timestamp)
    pulse = age_seconds ** (-decay)

    exp_base = math.exp(max(-20, min(20, base_level)))
    new_base = math.log(exp_base + pulse)

    # 网络传播
    neighbors = neighbor_activations or []
    strengths = neighbor_strengths or []
    if len(strengths) < len(neighbors):
        strengths.extend([0.5] * (len(neighbors) - len(strengths)))

    if neighbors and strengths:
        spread = sum(a * s for a, s in zip(neighbors, strengths)) / sum(strengths)
    else:
        spread = 0.0

    activation = new_base + spread
    retrieval_prob = 1.0 / (1.0 + math.exp(-(activation - _DEFAULT_RETRIEVAL_THRESHOLD) / _DEFAULT_RETRIEVAL_SLOPE))
    latency_ms = _DEFAULT_LATENCY_FACTOR * math.exp(-activation)

    act_after = {
        "act_base_level": round(new_base, 4),
        "act_retrieval_prob": round(_clamp(retrieval_prob), 4),
        "act_latency_ms": max(0.0, round(latency_ms, 2)),
        "act_spread": round(spread, 4),
        "act_last_updated": now,
    }

    return {
        "subsystem": "activation",
        "method": "activation_update",
        "params": {"event_timestamp": event_timestamp},
        "result_summary": (
            f"base={new_base:.3f} spread={spread:.3f} "
            f"retrieval={retrieval_prob:.3f}"
        ),
        "activation_after": act_after,
    }


@_registry.register(
    "activation_decay",
    "Activation 惰性衰减",
    params_schema={
        "activation_state": {"type": "object", "required": True},
        "now": {"type": "number", "required": False},
    },
)
def activation_decay(activation_state: dict, now: float | None = None) -> dict:
    """读取时若超过阈值未更新则惰性衰减。"""
    now = now or time.time()

    base_level = float(activation_state.get("act_base_level", 0.0))
    spread = float(activation_state.get("act_spread", 0.0))
    last_updated = float(activation_state.get("act_last_updated", now))
    decay = float(activation_state.get("decay", _DEFAULT_DECAY))

    elapsed_seconds = max(0.0, now - last_updated)
    if elapsed_seconds <= 0:
        return {
            "subsystem": "activation",
            "method": "activation_decay",
            "result_summary": "no decay",
            "activation_after": dict(activation_state),
        }

    # 激活按时间幂衰减
    new_base = base_level * math.exp(-decay * elapsed_seconds / 86400.0)
    activation = new_base + spread
    retrieval_prob = 1.0 / (1.0 + math.exp(-(activation - _DEFAULT_RETRIEVAL_THRESHOLD) / _DEFAULT_RETRIEVAL_SLOPE))
    latency_ms = _DEFAULT_LATENCY_FACTOR * math.exp(-activation)

    act_after = {
        **activation_state,
        "act_base_level": round(new_base, 4),
        "act_retrieval_prob": round(_clamp(retrieval_prob), 4),
        "act_latency_ms": max(0.0, round(latency_ms, 2)),
        "act_last_updated": now,
    }

    return {
        "subsystem": "activation",
        "method": "activation_decay",
        "params": {"elapsed_seconds": round(elapsed_seconds, 2)},
        "result_summary": f"base={base_level:.3f}→{new_base:.3f} (decay)",
        "activation_after": act_after,
    }
