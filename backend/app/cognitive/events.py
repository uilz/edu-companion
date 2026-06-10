"""事件处理器 — 认知事件全生命周期

实现 CognitiveNode 文档 v2.10 第 5 节全部处理器。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import constants as C
from .equations import (
    calc_base_level,
    calc_latency_ms,
    calc_retrieval_prob,
    decay_belief,
    update_belief,
    update_decayed_count,
    update_engagement,
    update_fatigue,
    update_trend,
)
from .models import (
    Activation,
    Belief,
    CognitiveEvent,
    CognitiveLoad,
    CognitiveNode,
    DialogueContext,
    PracticeEvent,
    PracticeSummary,
    UserCognitiveState,
)
from .storage import (
    append_event,
    get_node,
    mark_event_processed,
    upsert_node,
)

logger = logging.getLogger(__name__)

# Currently active student state (per-session, ephemeral)
# Keyed by user_id
_global_states: dict[str, UserCognitiveState] = {}


def get_state(user_id: str) -> UserCognitiveState:
    """Get or create per-session cognitive state."""
    if user_id not in _global_states:
        _global_states[user_id] = UserCognitiveState(user_id=user_id)
    return _global_states[user_id]


# ════════════════════════════════════════════
# Dispatcher
# ════════════════════════════════════════════

_HANDLERS: dict[str, callable] = {}


def register_handler(event_type: str):
    """Decorator to register an event handler."""
    def wrapper(fn):
        _HANDLERS[event_type] = fn
        return fn
    return wrapper


def get_handler(event_type: str):
    """Get handler for event type, or None."""
    return _HANDLERS.get(event_type)


def process_event(event: CognitiveEvent) -> dict[str, Any]:
    """Process a single cognitive event.

    Returns a dict of effects for logging/debugging.
    """
    handler = get_handler(event.event_type)
    if handler is None:
        logger.warning(f"No handler for event type: {event.event_type}")
        return {"status": "ignored", "event_type": event.event_type}
    try:
        result = handler(event)
        mark_event_processed(event.event_id)
        return result
    except Exception as e:
        logger.error(f"Error processing {event.event_type}: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def process_unprocessed(user_id: str) -> list[dict]:
    """Process all unprocessed events for a user."""
    from .storage import get_unprocessed_events

    events = get_unprocessed_events(user_id)
    results = []
    for event in events:
        result = process_event(event)
        results.append(result)
    return results


# ════════════════════════════════════════════
# 5.1 practice_response — 18 步全链路
# ════════════════════════════════════════════

@register_handler("practice_response")
def handle_practice_response(event: CognitiveEvent) -> dict[str, Any]:
    """Complete 18-step pipeline for practice response.

    Steps:
      1. Decay belief
      2. Quick learn detection
      3. Fuse evidence → update belief
      4. Update peak proficiency
      5. Update decayed event count
      6. Update practice summary
      7. Update trend
      8. Update activation
      9. Update cognitive load
     10. Update fatigue
     11. Sync UserCognitiveState
     12. Calculate scheduling urgency
     13. Update engagement
     14. Save node + state
     15. Mark event as processed
     16. Check rapid decline → review recommendation signal
     17. Check deep processing opportunity
     18. Aggregate to parent nodes
    """
    now = time.time()
    node_id = event.node_id
    user_id = event.user_id
    payload = event.payload or {}
    success = payload.get("success", True)
    latency_ms = payload.get("latency_ms", 5000.0)

    consecutive = payload.get("consecutive", False)

    # Load node or create stub
    node = get_node(node_id, user_id) or CognitiveNode(id=node_id, label=node_id, level="atom")

    # ─── 1–3. 遗忘衰减 → 快速重学 → 证据融合 ───
    new_belief = update_belief(
        node.belief,
        PracticeEvent(timestamp=now, success=success, latency_ms=latency_ms),
        now,
        practice_summary=node.practice_summary,
    )

    # ─── 4. Update peak ───
    # (already done inside update_belief)

    # ─── 5. 压缩递推 ───
    decayed_count = update_decayed_count(
        node.practice_summary.decayed_event_count,
        now,
        node.belief.last_updated,
        C.DEFAULT_PARAMS["student.decay_factor"],
    )

    # ─── 6. 练习摘要 ───
    total = node.practice_summary.total_attempts + 1
    # 从 practice_events 计算正确率
    correct_in_history = sum(1 for e in node.practice_events if e.success) + (1 if success else 0)
    success_rate = correct_in_history / max(total, 1)
    mean_lat = node.practice_summary.mean_latency_7d
    if total > 1:
        mean_lat = (mean_lat * (total - 1) + latency_ms) / total
    else:
        mean_lat = latency_ms

    correct_attempts = node.practice_summary.correct_attempts + (1 if success else 0)
    total_time_spent = node.practice_summary.total_time_spent + latency_ms / 1000.0
    last_practiced = now

    new_summary = PracticeSummary(
        total_attempts=total,
        correct_attempts=correct_attempts,
        total_time_spent=total_time_spent,
        recent_success_rate_7d=success_rate,
        mean_latency_7d=mean_lat,
        decayed_event_count=decayed_count,
        rapid_relearn_cooldown_until=node.practice_summary.rapid_relearn_cooldown_until,
        last_practiced=last_practiced,
    )

    # ─── 7. 趋势 ───
    last_updated = node.belief.last_updated or now  # 首次创建时用 now
    new_trend = update_trend(
        node.trend,
        new_belief.proficiency_mean,
        now,
        last_updated,
    )

    # ─── 8. 激活（追加练习事件到列表后重算） ───
    events = list(node.practice_events)
    events.append(PracticeEvent(timestamp=now, success=success, latency_ms=latency_ms))
    if len(events) > C.PRACTICE_EVENT_MAX:
        events = events[-C.PRACTICE_EVENT_MAX:]

    base_level = calc_base_level(events, now, C.DEFAULT_PARAMS["student.decay_factor"])
    retrieval_prob = calc_retrieval_prob(base_level, C.DEFAULT_PARAMS["student.retrieval_sigma"])
    latency = calc_latency_ms(base_level)
    new_activation = Activation(
        base_level=base_level,
        retrieval_prob=retrieval_prob,
        latency_ms=latency,
        spread_from_network=node.activation.spread_from_network,
    )

    # ─── 9. 认知负荷（简化为基于 proficiency 的逆向估算） ───
    # 前置技能 mastery 未知时，用 intrinsic 反推
    new_load = CognitiveLoad(
        intrinsic=node.cognitive_load.intrinsic,
        dynamic=node.cognitive_load.intrinsic * (1.0 - new_belief.proficiency_mean),
    )

    # ─── 10. 疲劳 ───
    state = get_state(user_id)
    state.practice_count_this_session += 1
    state = update_fatigue(state, now)

    # ─── 11. Sync state ───
    state.last_activity_time = now

    # ─── 12. 调度 ───
    # 临时构建 node 用于调度计算
    temp_node = CognitiveNode(
        id=node.id,
        label=node.label,
        level=node.level,
        activation=new_activation,
        belief=new_belief,
        trend=new_trend,
        scheduling=node.scheduling,
        dialogue_contexts=node.dialogue_contexts,
        is_core=node.is_core,
    )
    # scheduling 已由 Phase 10 SM-2 独立管理，cognitive pipeline 不覆写

    # ─── 13. 激励 ───
    new_engagement = update_engagement(node.engagement, success, consecutive)

    # ─── 14. 写回节点 ───
    proficiency_before = node.belief.proficiency_mean
    node.belief = new_belief
    node.practice_events = events
    node.practice_summary = new_summary
    node.trend = new_trend
    node.activation = new_activation
    node.cognitive_load = new_load
    # scheduling 由 Phase 10 SM-2 独立管理
    node.engagement = new_engagement
    upsert_node(node, user_id)

    # ─── 15. Event already marked processed by caller ───

    # ─── 16. 快速下降检测 ───
    decline_signal = _check_decline(node, new_belief)

    # ─── 17. 深度思考触发 ───
    deep_trigger = _check_deep_trigger(node, new_belief)

    # ─── 18. 父节点聚合（简化：仅更新父节点调度） ───
    # 父节点的精确聚合需要加载子树，留到分区摘要时批量做
    _aggregate_to_parent(node, user_id)

    return {
        "status": "ok",
        "event_type": "practice_response",
        "node_id": node_id,
        "proficiency_before": proficiency_before,
        "proficiency_after": new_belief.proficiency_mean,
        "success": success,
        "activation": round(base_level, 3),
        "urgency": round(node.scheduling.urgency, 3) if node.scheduling else 0.0,
        "fatigue": round(state.fatigue_level, 3),
        "xp": new_engagement.xp,
        "streak": new_engagement.streak_current,
        "decline_signal": decline_signal,
        "deep_trigger": deep_trigger,
    }


def _check_decline(node: CognitiveNode, new_belief: Belief) -> bool:
    """检测快速下降 → 推荐复习"""
    decline = (
        node.belief.proficiency_mean - new_belief.proficiency_mean > C.DECLINE_THRESHOLD
        and new_belief.proficiency_mean < C.DECLINE_DANGER_THRESHOLD
    )
    return decline


def _check_deep_trigger(node: CognitiveNode, new_belief: Belief) -> bool:
    """检查深度思考触发条件"""
    if not node.dialogue_contexts:
        return False
    has_recent = any(
        ctx.last_discussed > time.time() - 86400
        for ctx in node.dialogue_contexts
    )
    in_range = 0.7 <= new_belief.proficiency_mean <= 0.95
    return has_recent and in_range


def _aggregate_to_parent(node: CognitiveNode, user_id: str) -> None:
    """聚合到父节点（仅更新调度 — 完整聚合由扫描器做）"""
    if not node.parent:
        return
    parent = get_node(node.parent, user_id)
    if not parent:
        return
    parent.scheduling.urgency = max(parent.scheduling.urgency, node.scheduling.urgency)
    upsert_node(parent, user_id)


# ════════════════════════════════════════════
# 5.n dialogue_context_update
# ════════════════════════════════════════════

@register_handler("dialogue_context_update")
def handle_dialogue_context_update(event: CognitiveEvent) -> dict[str, Any]:
    """更新 CognitiveNode 的对话上下文。

    payload:
      session_id, branch_id, version, context_type: "upper"|"lower",
      relevance_score, summary_text
    """
    now = time.time()
    node_id = event.node_id
    user_id = event.user_id
    payload = event.payload or {}

    node = get_node(node_id, user_id) or CognitiveNode(id=node_id, label=node_id, level="atom")

    ctx = DialogueContext(
        session_id=payload.get("session_id", ""),
        branch_id=payload.get("branch_id", ""),
        version=payload.get("version", ""),
        context_type=payload.get("context_type", "lower"),
        relevance_score=payload.get("relevance_score", 0.5),
        summary_text=payload.get("summary_text", ""),
        last_discussed=now,
    )

    # Append; keep max N recent
    contexts = list(node.dialogue_contexts)
    contexts.append(ctx)
    if len(contexts) > C.CONTEXT_HISTORY_MAX:
        contexts = contexts[-C.CONTEXT_HISTORY_MAX:]
    node.dialogue_contexts = contexts

    upsert_node(node, user_id)

    return {
        "status": "ok",
        "event_type": "dialogue_context_update",
        "node_id": node_id,
        "context_type": ctx.context_type,
        "relevance_score": ctx.relevance_score,
    }


# ════════════════════════════════════════════
# 5.n conversation_assessment
# ════════════════════════════════════════════

@register_handler("conversation_assessment")
def handle_conversation_assessment(event: CognitiveEvent) -> dict[str, Any]:
    """轻量信念更新：基于对话评估。

    不同于 practice_response 的全链路，对话评估只做:
    1. 遗忘衰减（强制做）
    2. 低权重证据融合（weight = 0.3）
    3. 更新趋势
    4. 不更新练习摘要/激活/疲劳
    """
    now = time.time()
    node_id = event.node_id
    user_id = event.user_id
    payload = event.payload or {}
    success = payload.get("assessment", 0.5) > 0.5  # 强→成功

    node = get_node(node_id, user_id) or CognitiveNode(id=node_id, label=node_id, level="atom")

    # 遗忘衰减 + 低权重证据
    decayed = decay_belief(node.belief, now)
    alpha_post = decayed.alpha + (0.3 if success else 0.0)
    beta_post = decayed.beta + (0.0 if success else 0.3)
    peak = max(node.belief.peak_proficiency, alpha_post / (alpha_post + beta_post))

    new_belief = Belief(
        alpha=alpha_post,
        beta=beta_post,
        proficiency_mean=alpha_post / (alpha_post + beta_post),
        proficiency_precision=alpha_post + beta_post,
        peak_proficiency=peak,
        last_updated=now,
    )

    new_trend = update_trend(node.trend, new_belief.proficiency_mean, now, node.belief.last_updated)

    node.belief = new_belief
    node.trend = new_trend
    upsert_node(node, user_id)

    return {
        "status": "ok",
        "event_type": "conversation_assessment",
        "node_id": node_id,
        "proficiency_before": node.belief.proficiency_mean,
        "proficiency_after": new_belief.proficiency_mean,
        "assessment": payload.get("assessment", 0.5),
    }


# ════════════════════════════════════════════
# 便捷 API：外部调用入口
# ════════════════════════════════════════════

def submit_practice(
    user_id: str,
    node_id: str,
    success: bool,
    latency_ms: float = 5000.0,
    consecutive: bool = False,
    confidence: float = 0.5,
) -> dict[str, Any]:
    """便捷方法：创建一个 practice_response 事件并处理。"""
    evt = CognitiveEvent(
        event_type="practice_response",
        user_id=user_id,
        node_id=node_id,
        payload={
            "success": success,
            "latency_ms": latency_ms,
            "consecutive": consecutive,
            "confidence": confidence,
        },
    )
    append_event(evt)
    return process_event(evt)


def submit_dialogue_context(
    user_id: str,
    node_id: str,
    session_id: str,
    context_type: str = "lower",
    branch_id: str = "",
    version: int = 0,
    relevance_score: float = 0.5,
    summary_text: str = "",
) -> dict[str, Any]:
    """便捷方法：创建对话上下文更新事件并处理。"""
    evt = CognitiveEvent(
        event_type="dialogue_context_update",
        user_id=user_id,
        node_id=node_id,
        payload={
            "session_id": session_id,
            "branch_id": branch_id,
            "version": version,
            "context_type": context_type,
            "relevance_score": relevance_score,
            "summary_text": summary_text,
        },
    )
    append_event(evt)
    return process_event(evt)


def submit_conversation_assessment(
    user_id: str,
    node_id: str,
    assessment: float = 0.5,
) -> dict[str, Any]:
    """便捷方法：创建对话评估事件并处理。"""
    evt = CognitiveEvent(
        event_type="conversation_assessment",
        user_id=user_id,
        node_id=node_id,
        payload={"assessment": assessment},
    )
    append_event(evt)
    return process_event(evt)
