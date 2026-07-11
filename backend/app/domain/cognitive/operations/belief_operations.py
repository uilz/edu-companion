"""Beta 信念操作 — 将认知核心从 BKT-lite 升级为 Beta(α, β) 概率分布。

提供：
- belief_update：基于练习/评估信号更新 Beta 后验
- belief_information_gain：计算两次信念状态之间的信息增益
- shrinkage_prior_apply：子节点向父节点收缩先验
- belief_decay：基于时间衰减 Beta 精度
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from scipy.special import betaln, digamma

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_MIN_PSEUDO_COUNT = 0.1
_DEFAULT_ALPHA = 1.0
_DEFAULT_BETA = 1.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _beta_entropy(alpha: float, beta: float) -> float:
    """Beta(α, β) 微分熵（nats）。"""
    alpha = max(_MIN_PSEUDO_COUNT, alpha)
    beta = max(_MIN_PSEUDO_COUNT, beta)
    return (
        betaln(alpha, beta)
        - (alpha - 1.0) * digamma(alpha)
        - (beta - 1.0) * digamma(beta)
        + (alpha + beta - 2.0) * digamma(alpha + beta)
    )


def _map_difficulty_factor(difficulty: float | None) -> float:
    """将题目 difficulty 映射到 [0, 1]，难题使更新更谨慎。"""
    if difficulty is None:
        return 0.5
    d = _clamp(difficulty, -1.0, 1.0)
    return (d + 1.0) / 2.0


def _read_belief(belief_state: dict[str, Any]) -> dict[str, float]:
    """读取信念状态，补全默认值并 clamp。"""
    return {
        "alpha": max(_MIN_PSEUDO_COUNT, float(belief_state.get("belief_alpha", _DEFAULT_ALPHA))),
        "beta": max(_MIN_PSEUDO_COUNT, float(belief_state.get("belief_beta", _DEFAULT_BETA))),
        "evidence_count": int(belief_state.get("belief_evidence_count", 0)),
        "last_updated": float(belief_state.get("belief_last_updated", 0.0)),
        "total_information_gain": float(belief_state.get("total_information_gain", 0.0)),
        "stability_factor": _clamp(float(belief_state.get("stability_factor", 0.5)), 0.01, 0.99),
        "forgetting_rate": _clamp(float(belief_state.get("forgetting_rate", 0.1)), 1e-6, 1.0),
        "independent_evidence_weight": _clamp(
            float(belief_state.get("independent_evidence_weight", 1.0)), 0.0, 1.0
        ),
    }


@_registry.register(
    "belief_update",
    "基于观测信号更新 Beta(α, β) 后验，并计算信息增益",
    params_schema={
        "belief_state": {"type": "object", "required": True},
        "success": {"type": "boolean", "required": True},
        "difficulty": {"type": "number", "required": False},
        "weight": {"type": "number", "required": False, "default": 1.0},
        "now": {"type": "number", "required": False},
    },
)
def belief_update(
    belief_state: dict[str, Any],
    success: bool,
    difficulty: float | None = None,
    weight: float = 1.0,
    now: float | None = None,
) -> dict[str, Any]:
    """Beta-二项简化更新：成功增加 α，失败增加 β，并记录信息增益。"""
    now = now or time.time()
    state = _read_belief(belief_state)
    alpha, beta = state["alpha"], state["beta"]
    evidence_count = state["evidence_count"]

    p = alpha / (alpha + beta)
    difficulty_factor = _map_difficulty_factor(difficulty)
    weight = max(0.0, weight)

    entropy_before = _beta_entropy(alpha, beta)

    if success:
        alpha += weight
        beta += weight * (1.0 - p) * difficulty_factor
    else:
        alpha += weight * p * (1.0 - difficulty_factor)
        beta += weight

    evidence_count += 1
    entropy_after = _beta_entropy(alpha, beta)
    information_gain = max(0.0, entropy_before - entropy_after)

    # 稳定性随证据累积缓慢提升，遗忘率相应下降
    stability_factor = min(0.95, 0.5 + 0.02 * evidence_count)
    forgetting_rate = 0.1 * (1.0 - stability_factor)

    total_information_gain = state["total_information_gain"] + information_gain

    belief_after = {
        "belief_alpha": round(alpha, 4),
        "belief_beta": round(beta, 4),
        "belief_evidence_count": evidence_count,
        "belief_last_updated": round(now, 4),
        "stability_factor": round(stability_factor, 4),
        "forgetting_rate": round(forgetting_rate, 4),
        "last_information_gain": round(information_gain, 6),
        "total_information_gain": round(total_information_gain, 6),
    }

    return {
        "subsystem": "belief",
        "method": "belief_update",
        "params": {
            "success": success,
            "difficulty": difficulty,
            "weight": weight,
        },
        "result_summary": (
            f"α={belief_state.get('belief_alpha', _DEFAULT_ALPHA):.3f}→{alpha:.3f} "
            f"β={belief_state.get('belief_beta', _DEFAULT_BETA):.3f}→{beta:.3f} "
            f"ig={information_gain:.4f}"
        ),
        "belief_after": belief_after,
        "entropy_before": round(entropy_before, 6),
        "entropy_after": round(entropy_after, 6),
        "information_gain": round(information_gain, 6),
    }


@_registry.register(
    "belief_information_gain",
    "计算两个 Beta 信念状态之间的信息增益（熵减）",
    params_schema={
        "belief_state_before": {"type": "object", "required": True},
        "belief_state_after": {"type": "object", "required": True},
    },
)
def belief_information_gain(
    belief_state_before: dict[str, Any],
    belief_state_after: dict[str, Any],
) -> dict[str, Any]:
    """计算响应前后 Beta 分布熵变。"""
    before = _read_belief(belief_state_before)
    after = _read_belief(belief_state_after)
    h_before = _beta_entropy(before["alpha"], before["beta"])
    h_after = _beta_entropy(after["alpha"], after["beta"])
    ig = max(0.0, h_before - h_after)
    return {
        "subsystem": "belief",
        "method": "belief_information_gain",
        "information_gain": round(ig, 6),
    }


@_registry.register(
    "shrinkage_prior_apply",
    "子节点信念向父节点收缩，数据稀疏时借用父节点估计",
    params_schema={
        "child_belief_state": {"type": "object", "required": True},
        "parent_belief_state": {"type": "object", "required": True},
        "shrinkage_strength": {"type": "number", "required": False, "default": 5.0},
    },
)
def shrinkage_prior_apply(
    child_belief_state: dict[str, Any],
    parent_belief_state: dict[str, Any],
    shrinkage_strength: float = 5.0,
) -> dict[str, Any]:
    """返回 shrinkage 后的有效信念参数，不修改原始观测参数。"""
    child = _read_belief(child_belief_state)
    parent = _read_belief(parent_belief_state)

    evidence_count = child["evidence_count"]
    shrinkage_strength = max(0.0, shrinkage_strength)
    lam = shrinkage_strength / (shrinkage_strength + evidence_count)

    effective_alpha = lam * parent["alpha"] + (1.0 - lam) * child["alpha"]
    effective_beta = lam * parent["beta"] + (1.0 - lam) * child["beta"]
    proficiency = effective_alpha / (effective_alpha + effective_beta)

    return {
        "subsystem": "belief",
        "method": "shrinkage_prior_apply",
        "params": {"shrinkage_lambda": round(lam, 4)},
        "result_summary": (
            f"effective α={effective_alpha:.3f} β={effective_beta:.3f} "
            f"proficiency={proficiency:.3f}"
        ),
        "effective_belief": {
            "belief_alpha": round(effective_alpha, 4),
            "belief_beta": round(effective_beta, 4),
            "proficiency": round(proficiency, 4),
        },
    }


@_registry.register(
    "belief_decay",
    "基于时间衰减 Beta(α, β) 精度，保持均值不变",
    params_schema={
        "belief_state": {"type": "object", "required": True},
        "now": {"type": "number", "required": False},
    },
)
def belief_decay(
    belief_state: dict[str, Any],
    now: float | None = None,
) -> dict[str, Any]:
    """按经过时间降低 α+β 精度，模拟遗忘。"""
    now = now or time.time()
    state = _read_belief(belief_state)
    alpha, beta = state["alpha"], state["beta"]
    last_updated = state["last_updated"]

    if last_updated <= 0:
        last_updated = now

    delta_days = max(0.0, (now - last_updated) / 86400.0)
    if delta_days <= 0:
        return {
            "subsystem": "belief",
            "method": "belief_decay",
            "params": {"delta_days": 0},
            "result_summary": "no decay (no time elapsed)",
            "belief_after": {
                "belief_alpha": round(alpha, 4),
                "belief_beta": round(beta, 4),
                "belief_last_updated": round(now, 4),
            },
        }

    total = alpha + beta
    p = alpha / total if total > 0 else 0.5

    effective_rate = max(1e-6, state["forgetting_rate"] * (1.0 - state["stability_factor"]))
    total_decayed = total * math.exp(-effective_rate * delta_days)

    alpha_new = max(_MIN_PSEUDO_COUNT, total_decayed * p)
    beta_new = max(_MIN_PSEUDO_COUNT, total_decayed * (1.0 - p))

    return {
        "subsystem": "belief",
        "method": "belief_decay",
        "params": {"delta_days": round(delta_days, 2)},
        "result_summary": (
            f"α={alpha:.3f}→{alpha_new:.3f} β={beta:.3f}→{beta_new:.3f} "
            f"(rate={effective_rate:.4f})"
        ),
        "belief_after": {
            "belief_alpha": round(alpha_new, 4),
            "belief_beta": round(beta_new, 4),
            "belief_last_updated": round(now, 4),
        },
    }
