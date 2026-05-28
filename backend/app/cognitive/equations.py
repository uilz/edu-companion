"""核心数学方程 — 激活/信念/遗忘/趋势/疲劳/聚合

实现 CognitiveNode 文档 v2.10 第 4 节全部方程。
纯函数，无副作用，无 I/O。
"""

from __future__ import annotations

import math

from . import constants as C
from .models import (
    Activation, Belief, CognitiveLoad, CognitiveNode, Engagement,
    PracticeEvent, PracticeSummary, Scheduling, Trend, UserCognitiveState,
)


# ════════════════════════════════════════════
# 4.1 激活更新（层级 ACT‑R）
# ════════════════════════════════════════════

def calc_base_level(
    events: list[PracticeEvent],
    now: float,
    decay_factor: float,
) -> float:
    """
    B_i = ln( Σ (t_now - t_e)^{-d} + ε )
    ε = 1e-6
    """
    d = decay_factor
    total = 0.0
    for e in events:
        age = max(now - e.timestamp, 1e-10)
        total += age ** (-d)
    return math.log(max(total + 1e-6, 1e-10))


def calc_retrieval_prob(base_level: float, sigma: float) -> float:
    """P_recall = 1 / (1 + e^{-B_i / σ})"""
    return 1.0 / (1.0 + math.exp(-base_level / max(sigma, 1e-10)))


def calc_latency_ms(base_level: float) -> float:
    """RT = 5000 · e^{-B_i}"""
    return 5000.0 * math.exp(-base_level)


def calc_spread(associates: list, retrieval_probs: dict[str, float]) -> float:
    """Σ w_ij · R_j, 缺失时 R_j=0.5"""
    total = 0.0
    for a in associates:
        r = retrieval_probs.get(a.id, 0.5)
        total += a.strength * r
    return total


def update_activation(
    node: CognitiveNode,
    now: float,
    retrieval_probs: dict[str, float] | None = None,
    params: dict | None = None,
) -> Activation:
    """完整 ACT‑R 激活更新"""
    d = (params or {}).get("student.decay_factor", C.DEFAULT_PARAMS["student.decay_factor"])
    sigma = (params or {}).get("student.retrieval_sigma", C.DEFAULT_PARAMS["student.retrieval_sigma"])

    base = calc_base_level(node.practice_events, now, d)

    # 父节点贡献
    # parent_mu 由外部传入（跨节点读取），这里设为 0
    parent_contrib = 0.0

    # 扩散激活
    spread = calc_spread(node.associates, retrieval_probs or {})

    base_effective = base + 0.1 * parent_contrib + spread
    retrieval_prob = calc_retrieval_prob(base_effective, sigma)
    latency = calc_latency_ms(base_effective)

    return Activation(
        base_level=base_effective,
        retrieval_prob=retrieval_prob,
        latency_ms=latency,
        spread_from_network=spread,
    )


# ════════════════════════════════════════════
# 4.2 信念更新（稳健贝叶斯）
# ════════════════════════════════════════════

def decay_belief(
    belief: Belief,
    now: float,
    decay_factor: float,
    min_pseudo_count: float = C.INITIAL_BELIEF_ALPHA,
) -> Belief:
    """
    遗忘衰减：α, β 同比例时间衰减，强制下限
    α_decay = max(α_last · e^{-d·Δt}, α_min)
    β_decay = max(β_last · e^{-d·Δt}, β_min)
    """
    dt = max(now - belief.last_updated, 0.0) / 86400.0  # 秒→天
    decay = math.exp(-decay_factor * dt)

    new_alpha = max(belief.alpha * decay, min_pseudo_count)
    new_beta = max(belief.beta * decay, min_pseudo_count)

    return Belief(
        alpha=new_alpha,
        beta=new_beta,
        proficiency_mean=new_alpha / (new_alpha + new_beta),
        proficiency_precision=new_alpha + new_beta,
        peak_proficiency=belief.peak_proficiency,
        last_updated=now,
    )


def check_rapid_relearn(
    belief: Belief,
    practice_summary: PracticeSummary,
    event: PracticeEvent,
    now: float,
) -> float:
    """
    快速重学检测
    条件:
    1. peak_proficiency >= 0.95
    2. current proficiency_mean < 0.8
    3. success=True 且 latency < max(3000, expected * 1.5)
    4. cooldown_until <= now
    满足时: 有效权重 × 2.0, 冷却设为 now + 365天
    """
    if belief.peak_proficiency < C.RAPID_RELEARN_PEAK_THRESHOLD:
        return 1.0
    if belief.proficiency_mean >= C.RAPID_RELEARN_CURRENT_THRESHOLD:
        return 1.0
    if not event.success:
        return 1.0

    expected_latency = calc_latency_ms(calc_base_level([], now, 0.5))
    latency_limit = max(C.RAPID_RELEARN_LATENCY_MAX, expected_latency * C.RAPID_RELEARN_LATENCY_FACTOR)
    if event.latency_ms >= latency_limit:
        return 1.0

    if now < practice_summary.rapid_relearn_cooldown_until:
        return 1.0

    return C.RAPID_RELEARN_WEIGHT_MULTIPLIER


def update_belief(
    belief: Belief,
    event: PracticeEvent,
    now: float,
    params: dict | None = None,
    practice_summary: PracticeSummary | None = None,
) -> Belief:
    """
    完整信念更新流程:
    1. 遗忘衰减
    2. 快速重学检测（可选）
    3. 证据融合
    4. 更新 peak_proficiency
    """
    d = (params or {}).get("student.decay_factor", C.DEFAULT_PARAMS["student.decay_factor"])
    min_pc = (params or {}).get("student.min_pseudo_count", C.DEFAULT_PARAMS["student.min_pseudo_count"])

    # 1. 衰减
    decayed = decay_belief(belief, now, d, min_pc)

    # 2. 快速重学
    weight = 1.0
    if practice_summary is not None:
        weight = check_rapid_relearn(decayed, practice_summary, event, now)

    # 3. 证据融合
    x = 1.0 if event.success else 0.0
    alpha_post = decayed.alpha + weight * x
    beta_post = decayed.beta + weight * (1.0 - x)

    # 4. peak
    new_mu = alpha_post / (alpha_post + beta_post)
    peak = max(belief.peak_proficiency, new_mu)

    return Belief(
        alpha=alpha_post,
        beta=beta_post,
        proficiency_mean=new_mu,
        proficiency_precision=alpha_post + beta_post,
        peak_proficiency=peak,
        last_updated=now,
    )


# ════════════════════════════════════════════
# 4.3 聚合（可视化）
# ════════════════════════════════════════════

def aggregate_children(children: list[CognitiveNode], k: float = C.AGGREGATION_K) -> dict:
    """
    μ_parent = ( (1/N) Σ μ_c^{-k} )^{-1/k}
    τ_parent = 1 / ( (1/N) Σ τ_c^{-1} + 0.01 )
    """
    if not children:
        return {"proficiency_mean": 0.0, "precision": 0.0}

    n = len(children)
    mu_sum = sum((c.proficiency ** (-k) if c.proficiency > 0 else float("inf")) for c in children)
    tau_sum = sum(1.0 / max(c.precision, 0.001) for c in children)

    parent_mu = (n / max(mu_sum, 1e-10)) ** (1.0 / k) if mu_sum != float("inf") else 0.0
    parent_tau = 1.0 / (tau_sum / n + 0.01)

    return {"proficiency_mean": min(parent_mu, 1.0), "precision": parent_tau}


# ════════════════════════════════════════════
# 4.4 压缩递推
# ════════════════════════════════════════════

def update_decayed_count(
    old_count: float,
    now: float,
    last_updated: float,
    decay_factor: float,
) -> float:
    """
    decayed_count_new = decayed_count_old · e^{-d·Δt} + 1
    """
    dt = max(now - last_updated, 0.0) / 86400.0
    return old_count * math.exp(-decay_factor * dt) + 1.0


# ════════════════════════════════════════════
# 4.5 学习趋势
# ════════════════════════════════════════════

def update_trend(
    trend: Trend,
    new_proficiency: float,
    now: float,
    last_belief_updated: float,
    params: dict | None = None,
) -> Trend:
    """
    完整趋势更新（文档 4.5 节全部步骤）

    1. 速度衰减
    2. 停滞天数时间累积（若 Δt>0）
    3. 历史序列清理（若 Δt>1）
    4. 推入新值
    5. 计算实际速度
    6. 波动率
    7. direction 判定
    """
    lambda_vel = (params or {}).get(
        "velocity_decay_lambda", C.DEFAULT_PARAMS["student.velocity_decay_lambda"],
    )
    dt = max(now - last_belief_updated, 0.0) / 86400.0

    # 1. 速度衰减
    velocity = trend.velocity_ewma * math.exp(-lambda_vel * dt)

    # 2. 停滞天数累积
    stagnation = trend.stagnation_days + dt

    # 3. 长时间不活动→清空历史
    recent = list(trend.recent_proficiencies)
    if dt > 1.0:
        recent = []

    # 4. 推入
    recent.append(new_proficiency)
    if len(recent) > C.TREND_HISTORY_MAX:
        recent = recent[-C.TREND_HISTORY_MAX:]

    # 5. 计算实际速度
    if len(recent) >= 2:
        actual_velocity = 0.9 * velocity + 0.1 * (recent[-1] - recent[-2])
    else:
        actual_velocity = 0.0

    # 6. 波动率
    if len(recent) >= 2:
        mean = sum(recent) / len(recent)
        variance = sum((v - mean) ** 2 for v in recent) / len(recent)
        volatility = math.sqrt(variance)
    else:
        volatility = 0.0

    # 7. direction
    if volatility > C.TREND_VOLATILITY_THRESHOLD:
        direction = "volatile"
        stagnation = 0.0
    elif abs(actual_velocity) < C.TREND_STAGNATION_THRESHOLD:
        direction = "plateau"
        # stagnation 保持（不减）
    elif actual_velocity >= C.TREND_STAGNATION_THRESHOLD:
        direction = "ascending"
        stagnation = 0.0
    else:
        direction = "descending"
        stagnation = 0.0

    return Trend(
        recent_proficiencies=recent,
        velocity_ewma=actual_velocity,
        stagnation_days=stagnation,
        volatility_std=volatility,
        direction=direction,
    )


# ════════════════════════════════════════════
# 4.6 疲劳模型
# ════════════════════════════════════════════

def update_fatigue(
    state: UserCognitiveState,
    now: float,
    params: dict | None = None,
) -> UserCognitiveState:
    """
    1. 会话定义：最近 1 小时内有操作视为同一会话
    2. L_session = min(1.0, practice_count / 30)
    3. fatigue_new = fatigue_old · e^{-λ·Δt} + η · L_session
    """
    lambda_decay = (params or {}).get(
        "fatigue_decay_lambda", C.DEFAULT_PARAMS["student.fatigue_decay_lambda"],
    )
    eta = (params or {}).get(
        "fatigue_increment_eta", C.DEFAULT_PARAMS["student.fatigue_increment_eta"],
    )

    dt = max(now - state.last_activity_time, 0.0) / 3600.0

    # 会话超时 → 新会话
    if dt > C.SESSION_TIMEOUT_HOURS:
        state.current_session_id = f"sess_{int(now)}"
        state.session_start_time = now
        state.practice_count_this_session = 0

    session_load = min(1.0, state.practice_count_this_session / C.FATIGUE_SESSION_DIVISOR)
    new_fatigue = state.fatigue_level * math.exp(-lambda_decay * dt) + eta * session_load

    state.fatigue_level = min(new_fatigue, 1.0)
    state.last_activity_time = now
    return state


# ════════════════════════════════════════════
# 统一调度
# ════════════════════════════════════════════

def calc_scheduling(
    node: CognitiveNode,
    fatigue: float,
    now: float,
    params: dict | None = None,
) -> Scheduling:
    """
    调度优先级评分:
    score = w_ret * urgency
          + w_mast * (1-μ)
          + w_inter * interleaving_benefit
          + w_core * is_core
          + w_stag * (stagnation_days > 3)
          - fatigue
    """
    p = params or {}
    w_ret = p.get("sched_retention_weight", C.DEFAULT_PARAMS["student.sched_retention_weight"])
    w_mast = p.get("sched_mastery_push_weight", C.DEFAULT_PARAMS["student.sched_mastery_push_weight"])
    p.get("sched_interleaving_weight", C.DEFAULT_PARAMS["student.sched_interleaving_weight"])
    w_core = p.get("sched_core_boost", C.DEFAULT_PARAMS["student.sched_core_boost"])
    w_stag = p.get("sched_stagnation_penalty", C.DEFAULT_PARAMS["student.sched_stagnation_penalty"])

    # 遗忘紧迫：review_urgency 由召回概率反向估算
    retrieval_prob = node.activation.retrieval_prob
    urgency = max(0.0, 1.0 - retrieval_prob) * w_ret

    # 掌握推进
    mastery_push = (1.0 - node.proficiency) * w_mast

    # 交错收益（简化为 0，后续可以按 interleaving_group 计算）
    interleave = 0.0

    # 核心技能加成
    core_boost = w_core if node.is_core else 0.0

    # 停滞惩罚
    stagnation = w_stag if node.trend.stagnation_days > 3 else 0.0

    score = urgency + mastery_push + interleave + core_boost + stagnation - fatigue
    score = max(0.0, min(score, 1.0))

    # next_action_type：有对话上下文且 proficiency 在 0.7-0.95 → deep_processing
    has_recent_dialogue = any(
        ctx.last_discussed > now - 86400  # 1 天内
        for ctx in node.dialogue_contexts
    )
    if has_recent_dialogue and 0.7 <= node.proficiency <= 0.95:
        next_action = "deep_processing"
    elif score > 0.3:
        next_action = "review"
    else:
        next_action = "none"

    return Scheduling(
        urgency=score,
        next_review=now + C.SCHED_NEXT_REVIEW_DEFAULT_DAYS * 86400,
        interleaving_group=node.scheduling.interleaving_group,
        last_interleaved_with=node.scheduling.last_interleaved_with,
        next_action_type=next_action,
    )


# ════════════════════════════════════════════
# 认知负荷
# ════════════════════════════════════════════

def calc_dynamic_load(
    prerequisites: list,
    child_proficiencies: dict[str, float],
    intrinsic: float = 0.5,
) -> CognitiveLoad:
    """
    dynamic = intrinsic * (1 - mean(mastery_of_prerequisites))
    缺失默认取 0.5
    """
    if not prerequisites:
        dynamic = 0.0
    else:
        proficiencies = [child_proficiencies.get(p.id, 0.5) for p in prerequisites]
        mean_mastery = sum(proficiencies) / len(proficiencies)
        dynamic = intrinsic * (1.0 - mean_mastery)

    return CognitiveLoad(intrinsic=intrinsic, dynamic=min(dynamic, 1.0))


# ════════════════════════════════════════════
# 激励更新
# ════════════════════════════════════════════

def update_engagement(
    engagement: Engagement,
    success: bool,
    consecutive: bool = False,
) -> Engagement:
    """成功 +10xp，连续正确额外 +5；错误无加分、streak 归零"""
    if success:
        xp_gain = 10.0 + (5.0 if consecutive else 0.0)
        new_streak = engagement.streak_current + 1
        return Engagement(
            xp=engagement.xp + xp_gain,
            streak_current=new_streak,
            effort_estimate=engagement.effort_estimate,
        )
    else:
        return Engagement(
            xp=engagement.xp,
            streak_current=0,
            effort_estimate=engagement.effort_estimate,
        )
