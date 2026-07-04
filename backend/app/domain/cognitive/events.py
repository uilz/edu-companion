"""事件处理器 — 认知事件全生命周期

保留 practice_response / dialogue_context_update / conversation_assessment 处理器,
改用 CognitiveOperationRegistry + CognitiveEventsAdapter 统一持久化路径.

修复 (2026-07-04)：
- `_get_repo()` 之前回退到 `container.event_bus` (PersistentEventBus)，
  但 EventBus 没有 `insert` / `mark_status` 方法 → submit_practice 静默失败
- 现统一走 `CognitiveEventsAdapter`（单例，包装 EventsRepository）
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.domain.cognitive.events_repository import get_cognitive_events_adapter
from app.domain.cognitive.models import (
    Activation,
    Belief,
    CognitiveLoad,
    CognitiveNode,
    DialogueContext,
    Metacognition,
    PracticeEvent,
    PracticeSummary,
    Trend,
    UserCognitiveState,
)
from app.domain.cognitive.operation_registry import get_registry
from app.domain.cognitive import get_repo
from . import constants as C

logger = logging.getLogger(__name__)

_registry = get_registry()

# ── 领域层事件记录类型（取代 infrastructure Event） ──


class CognitiveEventRecord:
    """领域层事件记录，仅包含事件处理所需字段"""
    def __init__(self, id: str = "", event_type: str = "", user_id: str = "",
                 source_type: str = "", source_id: str = "", status: str = "done",
                 payload: dict | None = None):
        self.id = id
        self.event_type = event_type
        self.user_id = user_id
        self.source_type = source_type
        self.source_id = source_id
        self.status = status
        self.payload = payload or {}


# 可注入的事件仓储协议 — 默认使用 CognitiveEventsAdapter 单例
_events_repo = None


def set_events_repo(repo: Any) -> None:
    """注入事件仓储实现（由 DI 容器或测试覆写）"""
    global _events_repo
    _events_repo = repo


def _get_repo():
    """获取事件仓储 — 优先使用注入的，否则用单例 adapter

    修复 (2026-07-04)：
    之前 fallback 是 `container.event_bus`，但 EventBus 没有
    `insert` / `mark_status` 方法。
    """
    global _events_repo
    if _events_repo is None:
        _events_repo = get_cognitive_events_adapter()
    return _events_repo

# ── 认知事件（统一走 _get_repo()，不再回退到 EventBus） ──

def append_event(event: CognitiveEventRecord):
    """追加事件记录（委托到注入的仓储）"""
    _get_repo().insert(event)


def get_unprocessed_events(limit: int = 100) -> list:
    return _get_repo().get_unprocessed_events(limit)


def mark_event_processed(event_id: str) -> None:
    _get_repo().mark_event_processed(event_id)


def query_events(node_id: str | None = None, event_type: str | None = None, limit: int = 50) -> list:
    return _get_repo().query_events(node_id, event_type, limit)

# Currently active student state (per-session, ephemeral)
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


def process_event(event: CognitiveEventRecord) -> dict[str, Any]:
    """Process a single cognitive event via registry operations.

    Returns a dict of effects for logging/debugging.
    """
    handler = get_handler(event.event_type)
    if handler is None:
        logger.warning(f"No handler for event type: {event.event_type}")
        _get_repo().mark_status(event.id, "done", "no_handler")
        return {"status": "ignored", "event_type": event.event_type}
    try:
        result = handler(event)
        _get_repo().mark_status(event.id, "done")
        return result
    except Exception as e:
        logger.error(f"Error processing {event.event_type}: {e}", exc_info=True)
        _get_repo().mark_status(event.id, "failed", str(e))
        return {"status": "error", "error": str(e)}


# ════════════════════════════════════════════
# 5.1 practice_response — 18 步全链路
# ════════════════════════════════════════════

@register_handler("practice_response")
def handle_practice_response(event: CognitiveEventRecord) -> dict[str, Any]:
    """Complete 18-step pipeline for practice response.

    Uses CognitiveOperationRegistry for belief/trend updates.
    """
    now = time.time()
    node_id = event.payload.get("node_id", "")
    user_id = event.user_id
    payload = event.payload or {}
    success = payload.get("success", True)
    latency_ms = payload.get("latency_ms", 5000.0)
    consecutive = payload.get("consecutive", False)

    # Load node or create stub
    node = get_repo().get_node(node_id, user_id) or CognitiveNode(id=node_id, label=node_id, level="atom")

    # ─── 1–3. 遗忘衰减 → 快速重学 → 证据融合 (via Registry) ───
    belief_result = _registry.execute(
        "update_belief_from_evidence",
        node_id=node_id,
        user_id=user_id,
        belief=node.belief.model_dump() if node.belief else Belief().model_dump(),
        success=success,
        weight=1.0,
        now=now,
    )
    new_belief = Belief(**belief_result["belief_after"])

    # ─── 5. 压缩递推 ───
    decayed = _registry.execute(
        "decay_belief",
        belief=node.belief.model_dump() if node.belief else Belief().model_dump(),
        now=now,
    )
    # 只取 decayed_event_count — 旧逻辑从 practice_summary 读
    # (已废弃旧 decayed_event_count 计算, 由 Beta 分布精度自动反映)

    # ─── 6. 练习摘要 ───
    total = node.practice_summary.total_attempts + 1
    correct_in_history = sum(1 for e in node.practice_events if e.success) + (1 if success else 0)
    success_rate = correct_in_history / max(total, 1)
    mean_lat = node.practice_summary.mean_latency_7d
    if total > 1:
        mean_lat = (mean_lat * (total - 1) + latency_ms) / total
    else:
        mean_lat = latency_ms

    correct_attempts = node.practice_summary.correct_attempts + (1 if success else 0)
    total_time_spent = node.practice_summary.total_time_spent + latency_ms / 1000.0

    new_summary = PracticeSummary(
        total_attempts=total,
        correct_attempts=correct_attempts,
        total_time_spent=total_time_spent,
        recent_success_rate_7d=success_rate,
        mean_latency_7d=mean_lat,
        decayed_event_count=node.practice_summary.decayed_event_count,
        rapid_relearn_cooldown_until=node.practice_summary.rapid_relearn_cooldown_until,
        last_practiced=now,
    )

    # ─── 7. 趋势 (via Registry) ───
    last_updated = node.belief.last_updated if node.belief else now
    trend_result = _registry.execute(
        "update_trend",
        trend=node.trend.model_dump() if node.trend else Trend().model_dump(),
        new_mean=new_belief.proficiency_mean,
        now=now,
        last_updated=last_updated,
    )
    new_trend = Trend(**trend_result["trend_after"])

    # ─── 8. 激活 ───
    events = list(node.practice_events)
    events.append(PracticeEvent(timestamp=now, success=success, latency_ms=latency_ms))
    if len(events) > C.PRACTICE_EVENT_MAX:
        events = events[-C.PRACTICE_EVENT_MAX:]

    # 简易激活计算 (原地, 非 Registry)
    base_level = _calc_base_level(events, now)
    retrieval_prob = _calc_retrieval_prob(base_level, C.DEFAULT_PARAMS.get("student.retrieval_sigma", 0.25))
    latency = _calc_latency_ms(base_level)
    new_activation = Activation(
        base_level=base_level,
        retrieval_prob=retrieval_prob,
        latency_ms=latency,
        spread_from_network=node.activation.spread_from_network if node.activation else 0.0,
    )

    # ─── 9. 认知负荷 ───
    intrinsic = node.cognitive_load.intrinsic if node.cognitive_load else 1.0
    new_load = CognitiveLoad(
        intrinsic=intrinsic,
        dynamic=intrinsic * (1.0 - new_belief.proficiency_mean),
    )

    # ─── 10. 疲劳 ───
    state = get_state(user_id)
    state.practice_count_this_session += 1
    state.fatigue_level = min(1.0, state.fatigue_level + 0.05)
    state.last_activity_time = now

    # ─── 11. 元认知校准 ───
    confidence_before = payload.get("confidence_before")
    # 兼容两种格式:
    #   int 1-4  (旧 API: 1=very unsure, 4=very sure)
    #   float 0-1 (新 API: 0.0-1.0)
    cb_norm: int | None = None
    if confidence_before is not None:
        if isinstance(confidence_before, int) and not isinstance(confidence_before, bool):
            cb_norm = max(1, min(4, confidence_before))
        elif isinstance(confidence_before, float) and 0.0 <= confidence_before <= 1.0:
            cb_norm = max(1, min(4, round(confidence_before * 4) or 1))
    if cb_norm is not None:
        metacog = node.metacognition or Metacognition()
        # 计算偏差：confidence_before (1-4) vs correctness_score (4 if correct, 0 if not)
        correctness_score = 4 if success else 0
        gap = cb_norm - correctness_score
        # 更新方向
        if abs(gap) <= 1:
            direction = "accurate"
        elif gap > 0:
            direction = "overconfident"
        else:
            direction = "underconfident"
        # 更新历史（保留最近20条）
        history = list(metacog.recent_history or []) + [gap]
        if len(history) > 20:
            history = history[-20:]
        # 计算校准误差（历史均值绝对值）
        calibration_error = sum(abs(h) for h in history) / len(history) if history else 0.0
        node.metacognition = Metacognition(
            self_assessment=cb_norm / 4.0,
            calibration_error=round(calibration_error, 3),
            direction=direction,
            recent_history=history,
        )

    # ─── 13. 激励 (简易, 非 Registry) ───
    new_engagement = node.engagement
    if new_engagement:
        new_engagement.xp += 10 if success else 2
        new_engagement.streak_current = (new_engagement.streak_current + 1) if success else 0
        new_engagement.streak_longest = max(new_engagement.streak_longest, new_engagement.streak_current)

    # ─── 14. 写回节点 ───
    proficiency_before = node.belief.proficiency_mean if node.belief else 0.0
    node.belief = new_belief
    node.practice_events = events
    node.practice_summary = new_summary
    node.trend = new_trend
    node.activation = new_activation
    node.cognitive_load = new_load
    node.engagement = new_engagement or node.engagement
    get_repo().upsert_node(node, user_id)

    # ─── 16. 快速下降检测 ───
    decline_signal = _check_decline(node, new_belief)

    # ─── 17. 深度思考触发 ───
    deep_trigger = _check_deep_trigger(node, new_belief)

    # ─── 18. 父节点聚合 ───
    _aggregate_to_parent(node, user_id)

    # 记录 CognitiveUpdateEvent
    operations_result = [belief_result, trend_result]
    _get_repo().insert(CognitiveEventRecord(
        event_type="cognitive_update",
        user_id=user_id,
        source_type="practice",
        source_id=event.id,
        payload={
            "reason": f"practice_response on node {node_id}",
            "target_ids": [node_id],
            "operations": [
                {"subsystem": o["subsystem"], "method": o["method"],
                 "params": o["params"], "result_summary": o["result_summary"]}
                for o in operations_result
            ],
        },
    ))

    return {
        "status": "ok",
        "event_type": "practice_response",
        "node_id": node_id,
        "proficiency_before": proficiency_before,
        "proficiency_after": new_belief.proficiency_mean,
        "success": success,
        "activation": round(base_level, 3),
        "fatigue": round(state.fatigue_level, 3),
        "xp": new_engagement.xp if new_engagement else 0,
        "streak": new_engagement.streak_current if new_engagement else 0,
        "decline_signal": decline_signal,
        "deep_trigger": deep_trigger,
        "metacognition": node.metacognition.model_dump() if node.metacognition else None,
    }


def _calc_base_level(events: list[PracticeEvent], now: float) -> float:
    """简易 base_level 计算: 加权正确率"""
    if not events:
        return 0.0
    recent = [e for e in events if now - e.timestamp < 86400 * 7]
    if not recent:
        recent = events[-10:]
    successes = sum(1 for e in recent if e.success)
    return successes / max(len(recent), 1)


def _calc_retrieval_prob(base_level: float, sigma: float) -> float:
    """提取概率: 简化为 base_level 经 sigmoid"""
    import math
    return 1.0 / (1.0 + math.exp(-sigma * (base_level - 0.5) * 10))


def _calc_latency_ms(base_level: float) -> float:
    """反应时: 随掌握度指数下降"""
    return 5000.0 * (1.0 - base_level * 0.6)


def _check_decline(node: CognitiveNode, new_belief: Belief) -> bool:
    """检测快速下降 → 推荐复习"""
    if not node.belief:
        return False
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
    """聚合到父节点（仅更新调度）"""
    if not node.parent:
        return
    parent = get_repo().get_node(node.parent, user_id)
    if not parent:
        return
    if parent.scheduling and node.scheduling:
        parent.scheduling.urgency = max(parent.scheduling.urgency, node.scheduling.urgency)
        get_repo().upsert_node(parent, user_id)


# ════════════════════════════════════════════
# 5.n dialogue_context_update
# ════════════════════════════════════════════

@register_handler("dialogue_context_update")
def handle_dialogue_context_update(event: Event) -> dict[str, Any]:
    """更新 CognitiveNode 的对话上下文。"""
    now = time.time()
    node_id = event.payload.get("node_id", "")
    user_id = event.user_id
    payload = event.payload or {}

    node = get_repo().get_node(node_id, user_id) or CognitiveNode(id=node_id, label=node_id, level="atom")

    ctx = DialogueContext(
        session_id=payload.get("session_id", ""),
        branch_id=payload.get("branch_id", ""),
        version=str(payload.get("version", "")),
        context_type=payload.get("context_type", "lower"),
        relevance_score=payload.get("relevance_score", 0.5),
        summary_text=payload.get("summary_text", ""),
        last_discussed=now,
    )

    contexts = list(node.dialogue_contexts)
    contexts.append(ctx)
    if len(contexts) > C.CONTEXT_HISTORY_MAX:
        contexts = contexts[-C.CONTEXT_HISTORY_MAX:]
    node.dialogue_contexts = contexts

    get_repo().upsert_node(node, user_id)

    # 记录事件
    _get_repo().insert(CognitiveEventRecord(
        event_type="cognitive_update",
        user_id=user_id,
        source_type="conversation",
        source_id=payload.get("source_id", event.id),
        payload={
            "reason": f"dialogue_context_update on node {node_id}",
            "target_ids": [node_id],
            "operations": [
                {"subsystem": "dialogue", "method": "append_context",
                 "params": {"context_type": ctx.context_type},
                 "result_summary": f"context appended, total {len(contexts)}"}
            ],
        },
    ))

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
def handle_conversation_assessment(event: CognitiveEventRecord) -> dict[str, Any]:
    """轻量信念更新：基于对话评估。"""
    now = time.time()
    node_id = event.payload.get("node_id", "")
    user_id = event.user_id
    payload = event.payload or {}
    success = payload.get("assessment", 0.5) > 0.5

    node = get_repo().get_node(node_id, user_id) or CognitiveNode(id=node_id, label=node_id, level="atom")

    # 使用 Registry: 遗忘衰减 + 低权重证据
    belief_input = node.belief.model_dump() if node.belief else Belief().model_dump()
    belief_result = _registry.execute(
        "update_belief_from_evidence",
        node_id=node_id,
        user_id=user_id,
        belief=belief_input,
        success=success,
        weight=0.3,
        now=now,
    )
    new_belief = Belief(**belief_result["belief_after"])

    last_updated = node.belief.last_updated if node.belief else now
    trend_input = node.trend.model_dump() if node.trend else Trend().model_dump()
    trend_result = _registry.execute(
        "update_trend",
        trend=trend_input,
        new_mean=new_belief.proficiency_mean,
        now=now,
        last_updated=last_updated,
    )
    new_trend = Trend(**trend_result["trend_after"])

    node.belief = new_belief
    node.trend = new_trend
    get_repo().upsert_node(node, user_id)

    # 记录事件
    _get_repo().insert(CognitiveEventRecord(
        event_type="cognitive_update",
        user_id=user_id,
        source_type="conversation",
        source_id=payload.get("source_id", event.id),
        payload={
            "reason": f"conversation_assessment on node {node_id}",
            "target_ids": [node_id],
            "operations": [
                {"subsystem": b["subsystem"], "method": b["method"],
                 "params": b["params"], "result_summary": b["result_summary"]}
                for b in [belief_result, trend_result]
            ],
        },
    ))

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
    confidence_before: int | None = None,
) -> dict[str, Any]:
    """便捷方法：创建一个 practice_response 事件并处理。"""
    evt = CognitiveEventRecord(
        event_type="practice_response",
        user_id=user_id,
        source_type="practice",
        source_id="",
        payload={
            "node_id": node_id,
            "success": success,
            "latency_ms": latency_ms,
            "consecutive": consecutive,
            "confidence": confidence,
            "confidence_before": confidence_before,
        },
    )
    _get_repo().insert(evt)
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
    evt = CognitiveEventRecord(
        event_type="dialogue_context_update",
        user_id=user_id,
        source_type="conversation",
        source_id=session_id,
        payload={
            "node_id": node_id,
            "session_id": session_id,
            "branch_id": branch_id,
            "version": version,
            "context_type": context_type,
            "relevance_score": relevance_score,
            "summary_text": summary_text,
        },
    )
    _get_repo().insert(evt)
    return process_event(evt)


def submit_conversation_assessment(
    user_id: str,
    node_id: str,
    assessment: float = 0.5,
) -> dict[str, Any]:
    """便捷方法：创建对话评估事件并处理。"""
    evt = CognitiveEventRecord(
        event_type="conversation_assessment",
        user_id=user_id,
        source_type="conversation",
        source_id="",
        payload={
            "node_id": node_id,
            "assessment": assessment,
        },
    )
    _get_repo().insert(evt)
    return process_event(evt)
