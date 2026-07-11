"""DiagnosticSignal 生成器 — Phase 3

订阅 PracticeAnswerBehaviorRecorded，基于派生指标生成诊断信号。
不直接修改认知信念（Belief），只作为反馈和秘书编排的输入。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.infrastructure.db.database import get_db
from shared.events import DomainEvent, PracticeAnswerBehaviorRecorded

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str = "ds") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def _parse_json(raw: Any, default: Any = None) -> Any:
    if raw is None or raw == "" or raw == {} or raw == []:
        return default if default is not None else {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def build_diagnostic_signal(event: PracticeAnswerBehaviorRecorded) -> dict:
    """由 PracticeAnswerBehaviorRecorded 生成 DiagnosticSignal。

    信号解释：
    - hesitation_ratio: 犹豫时间占比
    - answer_change_rate: 改选次数（绝对值）
    - hover_focus_ratio: hover 总时长占比（近似投入度）
    - pause_burstiness: 输入停顿突发度（avg_text_pause_ms 相对总时长）
    - hint_used: 是否使用提示
    """
    time_on = max(event.time_on_question_ms, 1)
    hesitation_ms = max(event.hesitation_ms, 0)
    hesitation_ratio = min(hesitation_ms / time_on, 1.0)

    hover_focus_ratio = min(event.total_hover_ms / time_on, 1.0) if time_on > 0 else 0.0
    pause_burstiness = min(event.avg_text_pause_ms / time_on, 1.0) if time_on > 0 else 0.0

    signals = {
        "hesitation_ratio": round(hesitation_ratio, 3),
        "answer_change_count": event.answer_change_count,
        "answer_change_rate": event.answer_change_count,
        "hover_focus_ratio": round(hover_focus_ratio, 3),
        "pause_burstiness": round(pause_burstiness, 3),
        "hint_used": 1.0 if event.hint_count > 0 else 0.0,
        "time_on_question_ms": event.time_on_question_ms,
        "avg_text_pause_ms": event.avg_text_pause_ms,
    }

    # 综合判断建议动作
    suggested_action = "idle"
    interpretation_parts: list[str] = []
    confidence_factors: list[float] = []

    if hesitation_ratio > 0.4 and event.time_on_question_ms > 5000:
        interpretation_parts.append("答题过程中犹豫时间较长，可能存在概念不确定")
        suggested_action = "review"
        confidence_factors.append(0.7)

    if event.answer_change_count >= 2:
        interpretation_parts.append("多次改选答案，说明在选项间存在混淆")
        if suggested_action == "idle":
            suggested_action = "explain"
        confidence_factors.append(0.6)

    if event.hint_count > 0:
        interpretation_parts.append("使用了提示，说明对题目不够自信")
        confidence_factors.append(0.5)

    if event.avg_text_pause_ms > 2000 and event.time_on_question_ms > 8000:
        interpretation_parts.append("输入过程中存在长时间停顿，可能构思困难")
        if suggested_action == "idle":
            suggested_action = "practice"
        confidence_factors.append(0.5)

    if not interpretation_parts:
        interpretation_parts.append("答题过程流畅，未发现明显认知卡点")
        suggested_action = "idle"
        confidence_factors.append(0.3)

    confidence = min(sum(confidence_factors) / max(len(confidence_factors), 1), 1.0)
    interpretation = "；".join(interpretation_parts)

    return {
        "user_id": event.user_id,
        "attempt_id": event.attempt_id,
        "question_id": event.question_id,
        "signals": signals,
        "interpretation": interpretation,
        "suggested_action": suggested_action,
        "confidence": round(confidence, 3),
    }


def save_diagnostic_signal(data: dict) -> dict:
    """写入 diagnostic_signals 表。"""
    db = get_db()
    signal_id = _uid("ds")
    now = _now()
    db.execute(
        """INSERT INTO diagnostic_signals
           (id, user_id, attempt_id, question_id, signals, interpretation, suggested_action, confidence, generated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (signal_id, data["user_id"], data["attempt_id"], data["question_id"],
         _json(data["signals"]), data["interpretation"], data["suggested_action"],
         data["confidence"], now),
    )
    return {"signal_id": signal_id, **data}


class DiagnosticSignalBuilder:
    """认知中心诊断信号构建器。"""

    def __init__(self) -> None:
        self._bus = None
        self._subscribed = False

    def subscribe(self, bus: Any) -> None:
        if self._subscribed:
            return
        self._bus = bus
        from app.infrastructure.event_bus import EventBus
        from app.infrastructure.persistent_event_bus import PersistentEventBus
        if not isinstance(bus, (EventBus, PersistentEventBus)):
            logger.warning("传入对象不是 EventBus 实例 (%s)，跳过订阅", type(bus).__module__)
            return
        bus.subscribe("PracticeAnswerBehaviorRecorded", self._on_behavior_recorded)
        self._subscribed = True
        logger.info("📡 DiagnosticSignalBuilder 已订阅 PracticeAnswerBehaviorRecorded")

    def unsubscribe(self) -> None:
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("PracticeAnswerBehaviorRecorded", self._on_behavior_recorded)
        self._subscribed = False

    async def _on_behavior_recorded(self, event: DomainEvent) -> None:
        if not isinstance(event, PracticeAnswerBehaviorRecorded):
            return
        try:
            signal = build_diagnostic_signal(event)
            save_diagnostic_signal(signal)
            logger.debug("生成 DiagnosticSignal: attempt=%s action=%s",
                         event.attempt_id, signal["suggested_action"])
        except Exception:
            logger.exception("DiagnosticSignal 生成失败: attempt=%s", getattr(event, "attempt_id", ""))


# 全局单例
diagnostic_signal_builder = DiagnosticSignalBuilder()
