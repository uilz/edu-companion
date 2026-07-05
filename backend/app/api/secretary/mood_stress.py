"""
MoodStress 模块 API 端点（ADR 0005）

路由：
  GET  /api/secretary/mood-stress/dashboard     - 仪表盘数据
  POST /api/secretary/mood-stress/record        - 用户主动记录
  GET  /api/secretary/mood-stress/records       - 情绪记录列表
  DELETE /api/secretary/mood-stress/records/{id} - 删除单条
  POST /api/secretary/mood-stress/intervention  - 记录干预工具使用
  GET  /api/secretary/mood-stress/interventions - 干预日志
  GET  /api/secretary/mood-stress/signals       - 行为信号列表
  POST /api/secretary/mood-stress/signals/mark-read - 标记已读
  POST /api/secretary/mood-stress/signals/emit  - 手动触发行为信号
  GET  /api/secretary/mood-stress/prefs         - 读取偏好
  PUT  /api/secretary/mood-stress/prefs         - 更新偏好
  POST /api/secretary/mood-stress/rules         - 新增规则
  GET  /api/secretary/mood-stress/rules         - 规则列表
  DELETE /api/secretary/mood-stress/rules/{id}  - 删除规则
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secretary/mood-stress", tags=["心情压力"])


# ──────────────────────────────────────────────
# Pydantic 模型
# ──────────────────────────────────────────────

VALID_EMOTION_TAGS = {
    "frustration", "anxiety", "confusion", "boredom",
    "overwhelm", "procrastination",
    "motivated", "achievement", "curious",
    "calm", "neutral",
}

VALID_INTERVENTION_TYPES = {
    "breathing", "knowledge_breathing",
    "cognitive_reappraisal", "environment",
}


class RecordRequest(BaseModel):
    emotion_tags: list[str] = Field(default_factory=list)
    pressure_score: int | None = Field(default=None, ge=1, le=10)
    energy_score: int | None = Field(default=None, ge=1, le=10)
    text_note: str | None = None
    related_event_ids: list[str] = Field(default_factory=list)

    @field_validator("emotion_tags")
    @classmethod
    def _validate_tags(cls, v: list[str]) -> list[str]:
        invalid = [t for t in v if t not in VALID_EMOTION_TAGS]
        if invalid:
            raise ValueError(
                f"非法的情绪标签: {invalid}; 必须是 11 类之一"
            )
        return v


class InterventionRequest(BaseModel):
    intervention_type: str
    duration_seconds: int | None = Field(default=None, ge=0, le=3600)
    trigger_event: str | None = None
    notes: str | None = None

    @field_validator("intervention_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in VALID_INTERVENTION_TYPES:
            raise ValueError(f"非法的干预类型: {v}")
        return v


class PrefsRequest(BaseModel):
    reminder_enabled: bool | None = None
    reminder_frequency: Optional[str] = None
    reminder_time: Optional[str] = None
    data_retention_days: int | None = Field(default=None, ge=1, le=3650)
    auto_collect_task_switch: bool | None = None
    auto_collect_stay_duration: bool | None = None
    auto_collect_error_rate: bool | None = None
    auto_collect_undo: bool | None = None
    auto_collect_session_anomaly: bool | None = None
    auto_collect_flashcard_failure: bool | None = None
    auto_collect_voice_features: bool | None = None
    output_to_planning: bool | None = None
    output_to_conversation: bool | None = None
    output_to_language_room: bool | None = None
    knowledge_breathing_excluded_node_ids: list[str] | None = None
    environment_theme: str | None = None
    environment_sound: str | None = None
    planning_rules: dict | None = None


class RuleRequest(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=64)
    trigger_metric: str  # pressure_score | energy_score | emotion_tag
    trigger_operator: str  # >= | <= | == | != | > | <
    trigger_value: Any
    action: str  # postpone_high_intensity | only_flashcard | suggest_break

    @field_validator("trigger_metric")
    @classmethod
    def _validate_metric(cls, v: str) -> str:
        if v not in {"pressure_score", "energy_score", "emotion_tag"}:
            raise ValueError(f"非法的 trigger_metric: {v}")
        return v

    @field_validator("trigger_operator")
    @classmethod
    def _validate_op(cls, v: str) -> str:
        if v not in {">=", "<=", "==", "!=", ">", "<"}:
            raise ValueError(f"非法的 trigger_operator: {v}")
        return v

    @field_validator("action")
    @classmethod
    def _validate_action(cls, v: str) -> str:
        if v not in {"postpone_high_intensity", "only_flashcard", "suggest_break"}:
            raise ValueError(f"非法的 action: {v}")
        return v


class SignalEmitRequest(BaseModel):
    signal_type: str
    signal_data: dict = Field(default_factory=dict)
    severity: int = Field(default=1, ge=1, le=3)

    @field_validator("signal_type")
    @classmethod
    def _validate_sig(cls, v: str) -> str:
        valid = {
            "task_switch", "stay_duration", "error_rate",
            "undo", "session_anomaly", "flashcard_failure", "voice_features",
        }
        if v not in valid:
            raise ValueError(f"非法的 signal_type: {v}")
        return v


# ──────────────────────────────────────────────
# 端点
# ──────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    user_id: str = Depends(current_user_id),
    days: int = Query(default=7, ge=1, le=90),
) -> dict:
    """情绪仪表盘 — 手动优先 + 自动检测 + 行为信号 + 干预日志"""
    from app.services.secretary.modules.mood_stress import build_dashboard
    return await build_dashboard(user_id, days=days)


@router.post("/record")
async def post_record(
    body: RecordRequest,
    user_id: str = Depends(current_user_id),
) -> dict:
    """用户主动记录心情/压力/能量"""
    from app.services.secretary.modules.mood_stress import record_manual
    row = await record_manual(
        user_id=user_id,
        emotion_tags=body.emotion_tags,
        pressure_score=body.pressure_score,
        energy_score=body.energy_score,
        text_note=body.text_note,
        related_event_ids=body.related_event_ids,
    )
    return {"status": "ok", "record": row}


@router.get("/records")
async def get_records(
    user_id: str = Depends(current_user_id),
    source: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """情绪记录列表"""
    if source and source not in ("manual", "auto"):
        raise HTTPException(422, "source 必须为 manual / auto")
    from app.services.secretary.mood_stress_store import mood_stress_store
    rows = mood_stress_store.list_emotion_records(user_id, source=source, days=days, limit=limit)
    return {
        "status": "ok",
        "records": [r.to_dict() for r in rows],
        "total": len(rows),
    }


@router.delete("/records/{record_id}")
async def delete_record(
    record_id: str,
    user_id: str = Depends(current_user_id),
) -> dict:
    """删除单条情绪记录（遗忘权）"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    ok = mood_stress_store.delete_emotion_record(user_id, record_id)
    if not ok:
        raise HTTPException(404, "记录不存在")
    return {"status": "deleted"}


@router.post("/intervention")
async def post_intervention(
    body: InterventionRequest,
    user_id: str = Depends(current_user_id),
) -> dict:
    """记录干预工具使用（4 种）"""
    from app.services.secretary.modules.mood_stress import record_intervention
    row = await record_intervention(
        user_id=user_id,
        intervention_type=body.intervention_type,
        duration_seconds=body.duration_seconds,
        trigger_event=body.trigger_event,
        notes=body.notes,
    )
    return {"status": "ok", "intervention": row}


@router.get("/interventions")
async def get_interventions(
    user_id: str = Depends(current_user_id),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """干预日志列表"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    rows = mood_stress_store.list_interventions(user_id, days=days, limit=limit)
    return {
        "status": "ok",
        "interventions": [r.to_dict() for r in rows],
        "total": len(rows),
    }


@router.get("/signals")
async def get_signals(
    user_id: str = Depends(current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """未读行为信号"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    rows = mood_stress_store.list_unread_signals(user_id, limit=limit)
    return {
        "status": "ok",
        "signals": [r.to_dict() for r in rows],
        "total": len(rows),
    }


@router.post("/signals/mark-read")
async def mark_signals_read(
    ids: list[str],
    user_id: str = Depends(current_user_id),
) -> dict:
    """批量标记行为信号已读"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    count = mood_stress_store.mark_signals_read(user_id, ids)
    return {"status": "ok", "marked": count}


@router.post("/signals/emit")
async def emit_signal(
    body: SignalEmitRequest,
    user_id: str = Depends(current_user_id),
) -> dict:
    """手动触发行为信号（一般由事件消费自动调用）"""
    from app.services.secretary.modules.mood_stress import emit_behavior_signal
    result = await emit_behavior_signal(
        user_id=user_id,
        signal_type=body.signal_type,
        signal_data=body.signal_data,
        severity=body.severity,
    )
    return {"status": "ok", "signal": result}


@router.get("/prefs")
async def get_prefs(
    user_id: str = Depends(current_user_id),
) -> dict:
    """读取用户偏好"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    prefs = mood_stress_store.get_prefs(user_id)
    return {"status": "ok", "prefs": prefs}


@router.put("/prefs")
async def put_prefs(
    body: PrefsRequest,
    user_id: str = Depends(current_user_id),
) -> dict:
    """更新用户偏好（增量覆盖）"""
    from app.services.secretary.mood_stress_store import mood_stress_store

    delta = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not delta:
        return {"status": "ok", "prefs": mood_stress_store.get_prefs(user_id)}

    prefs = mood_stress_store.upsert_prefs(user_id, delta)

    # 发布偏好更新事件 (Task 架构 P0-1: 委托 publish_event_safe, 统一 sync/async 上下文)
    from app.infrastructure.event_bus_utils import publish_event_safe
    from shared.events import MoodStressPrefsUpdated
    publish_event_safe(MoodStressPrefsUpdated(
        user_id=user_id,
        changed_fields=list(delta.keys()),
    ))

    return {"status": "ok", "prefs": prefs}


@router.post("/rules")
async def add_rule(
    body: RuleRequest,
    user_id: str = Depends(current_user_id),
) -> dict:
    """新增心情压力规则"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    rule_id = mood_stress_store.add_rule(
        user_id=user_id,
        rule_name=body.rule_name,
        trigger_metric=body.trigger_metric,
        trigger_operator=body.trigger_operator,
        trigger_value=body.trigger_value,
        action=body.action,
    )
    return {"status": "ok", "rule_id": rule_id}


@router.get("/rules")
async def get_rules(
    user_id: str = Depends(current_user_id),
) -> dict:
    """规则列表"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    rules = mood_stress_store.list_rules(user_id)
    return {"status": "ok", "rules": rules, "total": len(rules)}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    user_id: str = Depends(current_user_id),
) -> dict:
    """删除规则"""
    from app.services.secretary.mood_stress_store import mood_stress_store
    ok = mood_stress_store.delete_rule(user_id, rule_id)
    if not ok:
        raise HTTPException(404, "规则不存在")
    return {"status": "deleted"}


# ──────────────────────────────────────────────
# 元数据：常量暴露给前端
# ──────────────────────────────────────────────

@router.get("/constants")
async def get_constants() -> dict:
    """暴露给前端：合法情绪标签 + 干预类型 + 行为信号类型 + 默认偏好"""
    return {
        "emotion_tags": [
            {"value": "frustration", "label": "挫败", "emoji": "😤", "severity": "negative"},
            {"value": "anxiety", "label": "焦虑", "emoji": "😰", "severity": "negative"},
            {"value": "confusion", "label": "困惑", "emoji": "🤔", "severity": "neutral"},
            {"value": "boredom", "label": "无聊", "emoji": "😴", "severity": "negative"},
            {"value": "overwhelm", "label": "压力大", "emoji": "😵", "severity": "negative"},
            {"value": "procrastination", "label": "拖延", "emoji": "🥱", "severity": "negative"},
            {"value": "motivated", "label": "有动力", "emoji": "💪", "severity": "positive"},
            {"value": "achievement", "label": "成就感", "emoji": "🎉", "severity": "positive"},
            {"value": "curious", "label": "好奇", "emoji": "🔍", "severity": "positive"},
            {"value": "calm", "label": "平静", "emoji": "😌", "severity": "positive"},
            {"value": "neutral", "label": "中性", "emoji": "📝", "severity": "neutral"},
        ],
        "intervention_types": [
            {"value": "breathing", "label": "5 分钟呼吸引导", "emoji": "🫁", "side": "client"},
            {"value": "knowledge_breathing", "label": "知识呼吸（复习）", "emoji": "🌬️", "side": "client+read_cards"},
            {"value": "cognitive_reappraisal", "label": "认知重评", "emoji": "🧭", "side": "client"},
            {"value": "environment", "label": "环境切换", "emoji": "🎨", "side": "client"},
        ],
        "behavior_signal_types": [
            "task_switch", "stay_duration", "error_rate", "undo",
            "session_anomaly", "flashcard_failure", "voice_features",
        ],
        "rule_metrics": ["pressure_score", "energy_score", "emotion_tag"],
        "rule_operators": [">=", "<=", "==", "!=", ">", "<"],
        "rule_actions": [
            {"value": "postpone_high_intensity", "label": "推迟高强度任务"},
            {"value": "only_flashcard", "label": "仅安排卡片复习"},
            {"value": "suggest_break", "label": "建议休息"},
        ],
        "principles": {
            "manual_priority": "手动记录在仪表盘顶部展示，自动检测作为参考",
            "intervention_isolated": "干预工具不修改学习数据（Belief/FSRS）",
            "voice_features_default_off": "语音特征默认关闭",
            "reminder_default_off": "提醒默认关闭",
            "behavior_signal_readonly": "行为信号仅提示，不自动修改",
        },
    }
