"""
MoodStress 业务模块 (Task #87)

提供 4 个核心业务函数：
  - build_dashboard()        — 仪表盘数据聚合
  - record_manual()          — 主动记录 (写库 + 发事件)
  - record_intervention()    — 干预工具使用 (写库 + 发事件)
  - emit_behavior_signal()   — 行为信号触发 (写库 + 发事件)

设计原则：
1. **手动优先**：仪表盘顶部永远展示最新手动记录
2. **不污染学习数据**：干预/行为信号不修改 Belief/FSRS/Scheduling
3. **事件透明**：所有写操作都发对应事件
4. **不抛业务异常**：写库失败 → 返回 None，记录日志
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Optional

from app.services.secretary import mood_stress_store as store

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 仪表盘
# ──────────────────────────────────────────────

async def build_dashboard(user_id: str, days: int = 7) -> dict:
    """
    构建情绪仪表盘数据。

    字段：
      - days: 查询周期
      - prefs: 19 项偏好
      - latest_manual: 最新手动记录 (None 表示无)
      - stats: 周期统计 (manual_total/auto_total/avg_pressure/avg_energy/tag_distribution)
      - recent_records: 最近 manual + auto 混合记录
      - recent_interventions: 最近干预记录
      - unread_behavior_signals: 未读行为信号
      - rules: 用户自定义规则
      - principles: 5 条设计原则 (前端展示用)
    """
    prefs = store.get_prefs(user_id=user_id)

    # 周期统计 (manual + auto)
    manual_records = store.list_emotion_records(
        user_id=user_id, source="manual", days=days, limit=200,
    )
    auto_records = store.list_emotion_records(
        user_id=user_id, source="auto", days=days, limit=200,
    )

    all_period = manual_records + auto_records
    pressure_scores = [r.pressure_score for r in all_period if r.pressure_score is not None]
    energy_scores = [r.energy_score for r in all_period if r.energy_score is not None]
    tag_counter: Counter = Counter()
    for r in all_period:
        for t in r.emotion_tags:
            tag_counter[t] += 1

    stats = {
        "days": days,
        "total": len(all_period),
        "manual_total": len(manual_records),
        "auto_total": len(auto_records),
        "avg_pressure": round(sum(pressure_scores) / len(pressure_scores), 2) if pressure_scores else None,
        "avg_energy": round(sum(energy_scores) / len(energy_scores), 2) if energy_scores else None,
        "tag_distribution": dict(tag_counter.most_common()),
    }

    # 最近记录 (混合 manual + auto，limit 50)
    recent_records = store.list_emotion_records(
        user_id=user_id, days=days, limit=50,
    )

    # 最近干预
    recent_interventions = store.list_interventions(
        user_id=user_id, days=days, limit=20,
    )

    # 未读信号
    unread_signals = store.list_unread_signals(user_id=user_id, limit=20)

    # 规则
    rules = store.list_rules(user_id=user_id)

    # 最新手动记录
    latest_manual_dict: Optional[dict] = None
    if manual_records:
        latest = manual_records[0]  # 已按时间倒序
        latest_manual_dict = latest.to_dict()

    return {
        "days": days,
        "prefs": prefs,
        "latest_manual": latest_manual_dict,
        "stats": stats,
        "recent_records": [r.to_dict() for r in recent_records],
        "recent_interventions": [i.to_dict() for i in recent_interventions],
        "unread_behavior_signals": [s.to_dict() for s in unread_signals],
        "rules": rules,
        "principles": {
            "manual_priority": True,
            "intervention_isolated": True,
            "voice_features_default_off": True,
            "reminder_default_off": True,
            "behavior_signal_readonly": True,
        },
    }


# ──────────────────────────────────────────────
# 主动记录
# ──────────────────────────────────────────────

async def record_manual(
    user_id: str,
    emotion_tags: list[str],
    pressure_score: Optional[int],
    energy_score: Optional[int],
    text_note: Optional[str],
    related_event_ids: Optional[list[str]] = None,
) -> Optional[dict]:
    """
    主动记录心情/压力/能量 — 手动优先。

    副作用：
      1. 写库 emotion_records (source=manual)
      2. 发布 MoodStressRecorded 事件
    """
    try:
        rec = store.insert_emotion_record(
            user_id=user_id,
            source="manual",
            emotion_tags=emotion_tags or [],
            pressure_score=pressure_score,
            energy_score=energy_score,
            text_note=text_note,
            related_event_ids=related_event_ids or [],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_manual 写库失败: %s", exc)
        return None

    # 发布事件
    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        from shared.events import MoodStressRecorded
        publish_event_safe(MoodStressRecorded(
            user_id=user_id,
            id=rec.id,
            emotion_tags=rec.emotion_tags,
            pressure_score=rec.pressure_score or 0,
            energy_score=rec.energy_score or 0,
            text_note=rec.text_note or "",
            related_event_ids=rec.related_event_ids,
        ))
    except Exception as exc:  # noqa: BLE001
        logger.debug("MoodStressRecorded 事件发布失败: %s", exc)

    return rec.to_dict()


# ──────────────────────────────────────────────
# 干预工具
# ──────────────────────────────────────────────

async def record_intervention(
    user_id: str,
    intervention_type: str,
    duration_seconds: Optional[int],
    trigger_event: Optional[str],
    notes: Optional[str],
) -> Optional[dict]:
    """
    记录干预工具使用。

    设计：干预不修改学习数据（Belief/FSRS/Scheduling），
         仅本地记录 + 事件流，供前端展示。
    """
    try:
        log = store.insert_intervention(
            user_id=user_id,
            intervention_type=intervention_type,
            duration_seconds=duration_seconds,
            trigger_event=trigger_event,
            notes=notes,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_intervention 写库失败: %s", exc)
        return None

    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        from shared.events import MoodStressInterventionTriggered
        publish_event_safe(MoodStressInterventionTriggered(
            user_id=user_id,
            id=log.id,
            intervention_type=intervention_type,
            duration_seconds=duration_seconds or 0,
            trigger_event=trigger_event or "",
            notes=notes or "",
        ))
    except Exception as exc:  # noqa: BLE001
        logger.debug("MoodStressInterventionTriggered 事件发布失败: %s", exc)

    return log.to_dict()


# ──────────────────────────────────────────────
# 行为信号
# ──────────────────────────────────────────────

async def emit_behavior_signal(
    user_id: str,
    signal_type: str,
    signal_data: dict,
    severity: int = 1,
) -> Optional[dict]:
    """
    触发行为信号。

    设计：信号仅提示，不自动修改学习数据；
         由用户在前端手动 mark-read。
    """
    try:
        sig = store.insert_behavior_signal(
            user_id=user_id,
            signal_type=signal_type,
            signal_data=signal_data or {},
            severity=severity,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("emit_behavior_signal 写库失败: %s", exc)
        return None

    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        from shared.events import MoodStressBehaviorSignalDetected
        publish_event_safe(MoodStressBehaviorSignalDetected(
            user_id=user_id,
            id=sig.id,
            signal_type=signal_type,
            signal_data=signal_data or {},
            severity=severity,
        ))
    except Exception as exc:  # noqa: BLE001
        logger.debug("MoodStressBehaviorSignalDetected 事件发布失败: %s", exc)

    return sig.to_dict()
