"""
Belief 子系统操作 — Beta 分布掌握度信念。

注册操作:
- update_belief_from_evidence: 贝叶斯证据融合 (Beta(α', β'))
- decay_belief: 遗忘衰减 (时间加权)
"""

from __future__ import annotations

import logging
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()


@_registry.register(
    "update_belief_from_evidence",
    "贝叶斯证据融合: 基于答题正误更新 Beta(α,β) 信念分布",
    params_schema={
        "node_id": {"type": "string", "required": True},
        "user_id": {"type": "string", "required": True},
        "belief": {"type": "object", "required": True, "description": "当前 Belief 字典"},
        "success": {"type": "boolean", "required": True},
        "weight": {"type": "number", "required": False, "default": 1.0},
        "now": {"type": "number", "required": False},
    },
)
def update_belief_from_evidence(
    node_id: str,
    user_id: str,
    belief: dict,
    success: bool = True,
    weight: float = 1.0,
    now: float | None = None,
) -> dict:
    """贝叶斯更新: 成功→α+=weight, 失败→β+=weight, 重算派生指标。"""
    now = now or time.time()

    alpha = float(belief.get("alpha", 2.0))
    beta = float(belief.get("beta", 2.0))

    # 融合新证据
    if success:
        alpha += weight
    else:
        beta += weight

    total = alpha + beta
    mean = alpha / total if total > 0 else 0.5
    precision = total

    peak = max(belief.get("peak_proficiency", 0.5), mean)

    belief_after = {
        "alpha": round(alpha, 4),
        "beta": round(beta, 4),
        "proficiency_mean": round(mean, 4),
        "proficiency_precision": round(precision, 4),
        "peak_proficiency": round(peak, 4),
        "last_updated": now,
    }

    return {
        "subsystem": "belief",
        "method": "update_belief_from_evidence",
        "params": {"success": success, "weight": weight},
        "result_summary": (
            f"alpha={alpha:.1f} beta={beta:.1f} "
            f"proficiency_mean: {belief.get('proficiency_mean', 0.5):.2f}→{mean:.2f}"
        ),
        "belief_after": belief_after,
    }


@_registry.register(
    "decay_belief",
    "遗忘衰减: 基于时间差降低信念精度 (precision)",
    params_schema={
        "belief": {"type": "object", "required": True},
        "now": {"type": "number", "required": False},
    },
)
def decay_belief(belief: dict, now: float | None = None) -> dict:
    """时间衰减: 精度指数衰减, mean 向 0.5 回归。"""
    now = now or time.time()

    alpha = float(belief.get("alpha", 2.0))
    beta = float(belief.get("beta", 2.0))
    last_updated = float(belief.get("last_updated", now))

    elapsed_hours = (now - last_updated) / 3600.0
    if elapsed_hours <= 0:
        return {
            "subsystem": "belief",
            "method": "decay_belief",
            "params": {},
            "result_summary": "no decay (no time elapsed)",
            "belief_after": belief,
        }

    # 指数衰减: 每 24h precision 减少 5%
    decay_rate = 0.05 ** (elapsed_hours / 24.0)
    total = (alpha + beta - 4) * decay_rate + 4  # 保底 precision=4
    total = max(total, 4.0)

    mean = alpha / (alpha + beta) if (alpha + beta) > 0 else 0.5
    # mean 向 0.5 漂移 (先验)
    drift_strength = min(1.0, elapsed_hours / 168.0)  # 7 天趋于先验
    mean = mean * (1 - drift_strength) + 0.5 * drift_strength

    new_alpha = mean * total
    new_beta = total - new_alpha

    belief_after = {
        "alpha": round(new_alpha, 4),
        "beta": round(new_beta, 4),
        "proficiency_mean": round(mean, 4),
        "proficiency_precision": round(total, 4),
        "peak_proficiency": belief.get("peak_proficiency", 0.5),
        "last_updated": now,
    }

    return {
        "subsystem": "belief",
        "method": "decay_belief",
        "params": {"elapsed_hours": round(elapsed_hours, 2)},
        "result_summary": (
            f"precision: {alpha+beta:.1f}→{total:.1f} "
            f"mean: {belief.get('proficiency_mean', 0.5):.2f}→{mean:.2f}"
        ),
        "belief_after": belief_after,
    }
