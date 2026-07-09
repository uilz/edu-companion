"""BKT-lite 信念模型操作（隐马尔可夫）"""

from __future__ import annotations

import logging
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

# 全局默认 BKT 参数（键名与 cognitive_node_projections 列名一致）
_BKT_DEFAULTS = {
    "bkt_known": 0.3,   # P(L_0)
    "bkt_learn": 0.3,   # P(T)
    "bkt_forget": 0.05, # P(F)
    "bkt_guess": 0.2,   # P(G)
    "bkt_slip": 0.1,    # P(S)
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _bkt_param(bkt_state: dict, key: str) -> float:
    """读取 BKT 参数，兼容旧键 p_* 与新键 bkt_*。"""
    return float(bkt_state.get(key, bkt_state.get(key.replace("bkt_", "p_"), _BKT_DEFAULTS[key])))


def effective_guess_slip(
    p_guess: float,
    p_slip: float,
    difficulty: float | None,
) -> tuple[float, float]:
    """根据题目难度调整 guess/slip 基线。"""
    if difficulty is None:
        return p_guess, p_slip
    d = _clamp(difficulty, -1.0, 1.0)
    g = _clamp(p_guess + d * 0.1, 0.05, 0.45)
    s = _clamp(p_slip + d * 0.05, 0.05, 0.25)
    return g, s


@_registry.register(
    "bkt_update",
    "基于练习观测更新 BKT 掌握概率 P(K)",
    params_schema={
        "bkt_state": {"type": "object", "required": True},
        "success": {"type": "boolean", "required": True},
        "difficulty": {"type": "number", "required": False},
        "weight": {"type": "number", "required": False, "default": 1.0},
        "now": {"type": "number", "required": False},
    },
)
def bkt_update(
    bkt_state: dict,
    success: bool,
    difficulty: float | None = None,
    weight: float = 1.0,
    now: float | None = None,
) -> dict:
    """BKT 单步更新：先遗忘衰减，再按观测更新。"""
    now = now or time.time()

    p_known = _clamp(_bkt_param(bkt_state, "bkt_known"))
    p_learn = _clamp(_bkt_param(bkt_state, "bkt_learn"))
    p_forget = _clamp(_bkt_param(bkt_state, "bkt_forget"))
    p_guess = _clamp(_bkt_param(bkt_state, "bkt_guess"))
    p_slip = _clamp(_bkt_param(bkt_state, "bkt_slip"))
    peak = float(bkt_state.get("bkt_peak", bkt_state.get("peak", p_known)))

    # 时间遗忘衰减
    last_updated = float(bkt_state.get("bkt_last_updated", bkt_state.get("last_updated", now)))
    # 未初始化时（last_updated <= 0）视为刚更新，避免首次事件被巨大时间差衰减到 0
    if last_updated <= 0:
        last_updated = now
    delta_days = max(0.0, (now - last_updated) / 86400.0)
    if delta_days > 0:
        p_known = p_known * ((1 - p_forget) ** delta_days)
        p_known = _clamp(p_known)

    # 根据难度调整 guess/slip
    p_guess_eff, p_slip_eff = effective_guess_slip(p_guess, p_slip, difficulty)

    obs = 1.0 if success else 0.0
    p_obs_if_known = obs * (1 - p_slip_eff) + (1 - obs) * p_slip_eff
    p_obs_if_unknown = obs * p_guess_eff + (1 - obs) * (1 - p_guess_eff)

    denom = p_obs_if_known * p_known + p_obs_if_unknown * (1 - p_known)
    if denom <= 0:
        p_known_post = p_known
    else:
        p_known_post = (p_obs_if_known * p_known) / denom

    # 学习转移 + 权重影响（weight 越大越接近完整转移）
    p_known_new = p_known_post + (1 - p_known_post) * (p_learn * weight)
    p_known_new = _clamp(p_known_new)

    peak = max(peak, p_known_new)

    bkt_after = {
        "bkt_known": round(p_known_new, 4),
        "bkt_learn": round(p_learn, 4),
        "bkt_forget": round(p_forget, 4),
        "bkt_guess": round(p_guess, 4),
        "bkt_slip": round(p_slip, 4),
        "bkt_proficiency": round(p_known_new, 4),
        "bkt_peak": round(peak, 4),
        "bkt_last_updated": now,
    }

    return {
        "subsystem": "bkt",
        "method": "bkt_update",
        "params": {"success": success, "difficulty": difficulty, "weight": weight},
        "result_summary": (
            f"P(K): {p_known:.3f}→{p_known_new:.3f} "
            f"obs={'correct' if success else 'incorrect'}"
        ),
        "bkt_after": bkt_after,
    }


@_registry.register(
    "bkt_decay",
    "BKT 遗忘衰减：按时间差降低 P(K)",
    params_schema={
        "bkt_state": {"type": "object", "required": True},
        "now": {"type": "number", "required": False},
    },
)
def bkt_decay(bkt_state: dict, now: float | None = None) -> dict:
    """仅执行遗忘衰减，不引入新观测。"""
    now = now or time.time()

    p_known = _clamp(_bkt_param(bkt_state, "bkt_known"))
    p_forget = _clamp(_bkt_param(bkt_state, "bkt_forget"))
    last_updated = float(bkt_state.get("bkt_last_updated", bkt_state.get("last_updated", now)))
    # 未初始化时直接更新时间戳，避免过度衰减
    if last_updated <= 0:
        return {
            "subsystem": "bkt",
            "method": "bkt_decay",
            "params": {"delta_days": 0},
            "result_summary": "no decay (uninitialized)",
            "bkt_after": {**bkt_state, "bkt_last_updated": now},
        }

    delta_days = max(0.0, (now - last_updated) / 86400.0)
    if delta_days <= 0:
        return {
            "subsystem": "bkt",
            "method": "bkt_decay",
            "params": {"delta_days": 0},
            "result_summary": "no decay (no time elapsed)",
            "bkt_after": dict(bkt_state),
        }

    p_known_new = p_known * ((1 - p_forget) ** delta_days)
    p_known_new = _clamp(p_known_new)

    bkt_after = {
        **bkt_state,
        "bkt_known": round(p_known_new, 4),
        "bkt_proficiency": round(p_known_new, 4),
        "bkt_last_updated": now,
    }

    return {
        "subsystem": "bkt",
        "method": "bkt_decay",
        "params": {"delta_days": round(delta_days, 2)},
        "result_summary": f"P(K): {p_known:.3f}→{p_known_new:.3f} (decay)",
        "bkt_after": bkt_after,
    }


@_registry.register(
    "aggregate_proficiency_to_parent",
    "聚合子节点掌握度到父节点",
    params_schema={
        "child_proficiencies": {"type": "array", "required": True},
        "child_weights": {"type": "array", "required": False},
    },
)
def aggregate_proficiency_to_parent(
    child_proficiencies: list[float],
    child_weights: list[float] | None = None,
) -> dict:
    """父节点掌握度 = 子节点 proficiency 加权平均。"""
    if not child_proficiencies:
        return {
            "subsystem": "bkt",
            "method": "aggregate_proficiency_to_parent",
            "result_summary": "no children, default 0.3",
            "mastery": 0.3,
        }

    weights = child_weights or [1.0] * len(child_proficiencies)
    weights = weights[: len(child_proficiencies)]
    if len(weights) < len(child_proficiencies):
        weights.extend([1.0] * (len(child_proficiencies) - len(weights)))

    total_weight = sum(weights)
    if total_weight <= 0:
        mastery = sum(child_proficiencies) / len(child_proficiencies)
    else:
        mastery = sum(p * w for p, w in zip(child_proficiencies, weights)) / total_weight

    return {
        "subsystem": "bkt",
        "method": "aggregate_proficiency_to_parent",
        "result_summary": f"weighted mastery={mastery:.3f}",
        "mastery": round(_clamp(mastery), 4),
    }
