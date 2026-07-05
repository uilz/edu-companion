"""
MoodStress 扩展模块 (ADR 0005)

实现为 `SecretaryModule` 的扩展，复用秘书系统的事件消费/Proposal 机制。

职责边界：
  - 复用：EmotionAnalyzer（自动检测）、fatigue_manager（疲劳）、daily_brief（简报）
  - 新建：用户主动记录（心情/压力/能量）、干预工具（呼吸引导/知识呼吸/认知重评/环境切换）、
         隐私控制、行为信号详细面板

实际化复用 (Task #36 Part B):
  - run_check() 在生成 mood_stress rule proposals 后，会通过 module_registry
    主动调用 FatigueManagerModule + DailyBriefModule 的 run_check()，
    把它们的 Proposal 作为上下文附加到 mood_stress rule 上（payload.context）。
  - build_dashboard() 把疲劳数据（predict_fatigue_risk）和今日学习简报
    数据（DailyBriefModule._collect_today_events）等纳入仪表盘，呈现给用户。

核心原则：
  - 手动优先：用户主动记录显示在顶部，自动检测不覆盖用户判断
  - 不自动修改：干预工具不进入知识图谱（不修改 Belief/FSRS/Scheduling）
  - 隐私保守：语音特征默认关闭、提醒默认关闭
  - 行为信号：仅提示用户，不自动触发任何学习数据修改
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.domain.secretary.models import Proposal
from app.domain.secretary.engines.context_engine import SessionContext
from app.domain.secretary.engines.module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 11 类情绪标签（与 EmotionAnalyzer 完全对齐）
# ──────────────────────────────────────────────

VALID_EMOTION_TAGS: set[str] = {
    "frustration", "anxiety", "confusion", "boredom",
    "overwhelm", "procrastination",
    "motivated", "achievement", "curious",
    "calm", "neutral",
}

VALID_INTERVENTION_TYPES: set[str] = {
    "breathing", "knowledge_breathing",
    "cognitive_reappraisal", "environment",
}


class MoodStressModule(SecretaryModule):
    """心情压力感知模块（秘书扩展模块）

    设计：
      - run_check() 不主动生成 Proposal（避免打扰）
      - 真正的写入由用户主动调用 record_manual / record_intervention 完成
      - 这里仅负责根据用户最新记录评估是否需要触发 `MoodStressRuleTriggered`
        （让规划模块在用户开启 output_to_planning 时按规则调整）

    隔离原则 (ADR 0005):
      - **不自动修改** Belief/FSRS/Scheduling
      - 心情压力数据**不进入知识图谱** (Belief 只能由主动学习行为改变)
      - 干预工具只入本地日志 + 事件流，**不**触发认知节点更新
    """

    def __init__(self) -> None:
        super().__init__()
        self._last_rule_check_at: dict[str, float] = {}

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="mood_stress",
            display_name="心情压力感知",
            emoji="🌊",
            description="用户主动记录心情/压力/能量，配合 4 种干预工具，行为信号只读提示",
            default_enabled=True,
            run_interval_seconds=300,  # 5 分钟
            version="1.0.0",
            author="MoodStress Team",
        )

    # ── 模块主入口 ──

    async def run_check(
        self,
        user_id: str,
        ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """每 5 分钟跑一次：评估规则，触发 MoodStressRuleTriggered 事件

        返回：秘书 Proposal 列表（仅作为信息提示，不主动推送）

        原则：
          - 用户未开启 output_to_planning → 不评估
          - 用户未手动记录最近 → 不评估（避免系统擅自推算）
          - 规则触发后由规划模块标记，**不**自动修改

        实际化复用 (Task #36 Part B):
          - 主动调用 fatigue_manager / daily_brief 模块，将它们的 Proposal
            作为 context 附加到 mood_stress rule proposal 上
        """
        # 节流：4 分钟最多一次
        last = self._last_rule_check_at.get(user_id, 0)
        if time.time() - last < 240:
            return []
        self._last_rule_check_at[user_id] = time.time()

        try:
            from app.services.secretary.mood_stress_store import mood_stress_store
            from shared.events import MoodStressRuleTriggered

            prefs = mood_stress_store.get_prefs(user_id)
            if not prefs.get("output_to_planning", True):
                return []

            # 仅基于用户最新一次**手动**记录（手动优先）评估
            latest = mood_stress_store.latest_manual_record(user_id)
            if not latest:
                return []

            rules = mood_stress_store.list_rules(user_id, enabled_only=True)
            if not rules:
                return []

            # ── 实际化复用：调用 fatigue_manager / daily_brief ──
            fatigue_proposals: list[Proposal] = []
            brief_proposals: list[Proposal] = []
            try:
                from app.domain.secretary.engines.module_registry import module_registry
                # 只有在情绪/压力/能量数据存在时，疲劳和简报才有相关性
                if (
                    latest.pressure_score is not None
                    or latest.energy_score is not None
                    or (latest.emotion_tags and any(
                        t in (latest.emotion_tags or []) for t in
                        ("frustration", "anxiety", "overwhelm", "fatigue")
                    ))
                ):
                    fatigue_proposals = await module_registry.run_module(
                        "fatigue_manager", user_id, ctx,
                    ) or []
                # 简报：仅在用户最近记录涉及疲惫/压力时纳入上下文
                if latest.pressure_score is not None and latest.pressure_score >= 6:
                    brief_proposals = await module_registry.run_module(
                        "daily_brief", user_id, ctx,
                    ) or []
            except Exception as e:  # noqa: BLE001
                logger.debug("fatigue_manager / daily_brief 复用失败: %s", e)

            proposals: list[Proposal] = []
            for rule in rules:
                if not self._rule_matches(rule, latest):
                    continue

                # 触发事件（供规划/对话模块订阅）
                # Task 架构 P0-1: 委托 publish_event_safe, 统一 sync/async 上下文
                from app.infrastructure.event_bus_utils import publish_event_safe
                metric = rule["trigger_metric"]
                tv = rule["trigger_value"]
                trigger_value = tv
                publish_event_safe(MoodStressRuleTriggered(
                    user_id=user_id,
                    rule_id=rule["id"],
                    trigger_metric=metric,
                    trigger_value=trigger_value,
                    action=rule["action"],
                ))

                # 构造 context 载荷（不复制原 Proposal，避免循环）
                context_payload = _build_context_payload(
                    fatigue_proposals=fatigue_proposals,
                    brief_proposals=brief_proposals,
                    latest=latest,
                )

                proposals.append(Proposal(
                    emoji="🌊",
                    title=f"心情压力规则触发: {rule['rule_name']}",
                    description=(
                        f"根据最新手动记录评估，规则「{rule['rule_name']}」被触发。"
                        f"动作建议：{rule['action']}。系统**不**自动修改规划，仅标记。"
                    ),
                    action_type="mood_stress_rule",
                    priority=4,  # 较低优先级，避免干扰
                    payload={
                        "rule_id": rule["id"],
                        "action": rule["action"],
                        "trigger_metric": rule["trigger_metric"],
                        "context": context_payload,
                    },
                    insight_source="mood_stress.rule_check",
                    generated_by=self.meta.name,
                    overrideable=True,
                ))
            return proposals
        except Exception as e:
            logger.warning("mood_stress run_check 失败: %s", e)
            return []

    # ── 规则匹配 ──

    @staticmethod
    def _rule_matches(rule: dict, latest: Any) -> bool:
        """检查规则是否匹配用户最新手动记录

        支持的 trigger_metric:
          - pressure_score: 数值 (1-10)
          - energy_score:   数值 (1-10)
          - emotion_tag:    字符串（单选或包含）
        """
        metric = rule["trigger_metric"]
        op = rule["trigger_operator"]
        target = rule["trigger_value"]

        if metric == "pressure_score" and latest.pressure_score is not None:
            return _compare(latest.pressure_score, op, _to_number(target))
        if metric == "energy_score" and latest.energy_score is not None:
            return _compare(latest.energy_score, op, _to_number(target))
        if metric == "emotion_tag":
            if isinstance(target, list):
                return any(t in (latest.emotion_tags or []) for t in target)
            return target in (latest.emotion_tags or [])
        return False

    # ── on_activate / on_deactivate ──

    async def on_activate(self) -> None:
        logger.info("🌊 MoodStress 模块激活")

    async def on_deactivate(self) -> None:
        logger.info("🌊 MoodStress 模块停用")

    async def health_check(self) -> str:
        try:
            from app.services.secretary.mood_stress_store import mood_stress_store
            # 简单健康检查：能查到默认偏好即视为 OK
            mood_stress_store.get_prefs("__health_probe__")
            return "ok"
        except Exception as e:
            return f"degraded: {e}"


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare(actual: float, op: str, target: float | None) -> bool:
    if target is None:
        return False
    if op == ">=":
        return actual >= target
    if op == "<=":
        return actual <= target
    if op == "==":
        return actual == target
    if op == "!=":
        return actual != target
    if op == ">":
        return actual > target
    if op == "<":
        return actual < target
    return False


def _build_context_payload(
    fatigue_proposals: list[Proposal],
    brief_proposals: list[Proposal],
    latest: Any,
) -> dict:
    """构造 mood_stress rule proposal 的 context 载荷。

    从 fatigue_manager / daily_brief 模块的 Proposal 中提取关键信号
    （不复制原 Proposal 避免循环），并附带用户最新手动记录的核心数值。
    """
    fatigue_summaries: list[dict] = []
    for p in fatigue_proposals or []:
        fatigue_summaries.append({
            "title": p.title,
            "action_type": p.action_type,
            "priority": p.priority,
            "payload": dict(p.payload or {}),
        })

    brief_summaries: list[dict] = []
    for p in brief_proposals or []:
        brief_summaries.append({
            "title": p.title,
            "action_type": p.action_type,
            "priority": p.priority,
            "payload": dict(p.payload or {}),
        })

    return {
        "latest_pressure_score": getattr(latest, "pressure_score", None),
        "latest_energy_score": getattr(latest, "energy_score", None),
        "latest_emotion_tags": list(getattr(latest, "emotion_tags", []) or []),
        "fatigue_proposals": fatigue_summaries,
        "brief_proposals": brief_summaries,
        "reuse_modules": ["fatigue_manager", "daily_brief"],
    }


# ──────────────────────────────────────────────
# 领域服务：用户主动记录
# ──────────────────────────────────────────────

async def record_manual(
    user_id: str,
    emotion_tags: list[str],
    pressure_score: int | None = None,
    energy_score: int | None = None,
    text_note: str | None = None,
    related_event_ids: list[str] | None = None,
) -> dict:
    """用户主动记录心情/压力/能量（手动优先）"""
    # 校验标签
    invalid = [t for t in (emotion_tags or []) if t not in VALID_EMOTION_TAGS]
    if invalid:
        raise ValueError(f"非法的情绪标签: {invalid}; 必须是 11 类之一: {sorted(VALID_EMOTION_TAGS)}")
    if pressure_score is not None and not (1 <= pressure_score <= 10):
        raise ValueError("pressure_score 必须在 1-10")
    if energy_score is not None and not (1 <= energy_score <= 10):
        raise ValueError("energy_score 必须在 1-10")

    from app.services.secretary.mood_stress_store import mood_stress_store
    row = mood_stress_store.insert_emotion_record(
        user_id=user_id,
        source="manual",
        emotion_tags=emotion_tags or [],
        pressure_score=pressure_score,
        energy_score=energy_score,
        text_note=text_note,
        related_event_ids=related_event_ids,
    )

    # 发布事件 (Task 架构 P0-1: 委托 publish_event_safe)
    from app.infrastructure.event_bus_utils import publish_event_safe
    from shared.events import MoodStressRecorded
    publish_event_safe(MoodStressRecorded(
        user_id=user_id,
        record_id=row.id,
        source="manual",
        emotion_tags=row.emotion_tags,
        pressure_score=row.pressure_score,
        energy_score=row.energy_score,
        text_note=row.text_note,
        related_event_ids=row.related_event_ids,
        recorded_at=row.created_at,
    ))

    return row.to_dict()


async def record_intervention(
    user_id: str,
    intervention_type: str,
    duration_seconds: int | None = None,
    trigger_event: str | None = None,
    notes: str | None = None,
) -> dict:
    """记录干预工具使用

    关键约束：干预**不修改**学习数据，仅本地记录 + 入事件流。
    """
    if intervention_type not in VALID_INTERVENTION_TYPES:
        raise ValueError(
            f"非法的干预类型: {intervention_type}; 必须是 {sorted(VALID_INTERVENTION_TYPES)}"
        )

    from app.services.secretary.mood_stress_store import mood_stress_store
    row = mood_stress_store.log_intervention(
        user_id=user_id,
        intervention_type=intervention_type,
        duration_seconds=duration_seconds,
        trigger_event=trigger_event,
        notes=notes,
    )

    # 发布事件 (Task 架构 P0-1: 委托 publish_event_safe)
    from app.infrastructure.event_bus_utils import publish_event_safe
    from shared.events import MoodStressInterventionTriggered
    publish_event_safe(MoodStressInterventionTriggered(
        user_id=user_id,
        intervention_type=intervention_type,
        duration_seconds=duration_seconds or 0,
    ))

    return row.to_dict()


async def build_dashboard(user_id: str, days: int = 7) -> dict:
    """构建情绪仪表盘数据

    手动优先：顶部展示用户最近一次主动记录
    自动检测：作为参考信号在下方展示（复用 EmotionAnalyzer）

    实际化复用 (Task #36 Part B):
      - 复用 fatigue_manager 的 predict_fatigue_risk（来自 secretary.analysis）
      - 复用 daily_brief 模块的 _collect_today_events（今日学习事件）
      - 两者以 "related_signals" 字段暴露给前端
    """
    from app.services.secretary.mood_stress_store import mood_stress_store

    prefs = mood_stress_store.get_prefs(user_id)
    latest_manual = mood_stress_store.latest_manual_record(user_id)
    stats = mood_stress_store.emotion_stats(user_id, days=days)
    recent_records = mood_stress_store.list_emotion_records(user_id, days=days, limit=20)
    recent_interventions = mood_stress_store.list_interventions(user_id, days=days, limit=20)
    unread_signals = mood_stress_store.list_unread_signals(user_id, limit=10)
    rules = mood_stress_store.list_rules(user_id)

    # 自动检测（复用 EmotionAnalyzer）
    auto_summary: dict = {}
    try:
        from app.services.analytics.emotion_analyzer import emotion_analyzer
        trend = await emotion_analyzer.analyze_trend(user_id, window_hours=days * 24)
        auto_summary = trend.to_dict()
    except Exception as e:
        logger.debug("自动检测趋势获取失败: %s", e)

    # ── 实际化复用：fatigue_manager (predict_fatigue_risk) ──
    fatigue_signal: dict = {}
    try:
        from app.domain.secretary.analysis import predict_fatigue_risk
        fatigue_signal = predict_fatigue_risk(user_id)
    except Exception as e:  # noqa: BLE001
        logger.debug("predict_fatigue_risk 失败: %s", e)

    # ── 实际化复用：daily_brief (_collect_today_events) ──
    brief_signal: dict = {}
    try:
        from app.domain.secretary.engines.builtin_daily_brief import DailyBriefModule
        # 实例化一个临时模块实例来复用其 _collect_today_events
        # 不调用 run_check 避免触发 Proposal 副作用
        daily_module = DailyBriefModule()
        brief_signal = daily_module._collect_today_events(user_id)
    except Exception as e:  # noqa: BLE001
        logger.debug("daily_brief _collect_today_events 失败: %s", e)

    return {
        "days": days,
        "prefs": prefs,
        "latest_manual": latest_manual.to_dict() if latest_manual else None,
        "stats": stats,
        "recent_records": [r.to_dict() for r in recent_records],
        "recent_interventions": [r.to_dict() for r in recent_interventions],
        "unread_behavior_signals": [s.to_dict() for s in unread_signals],
        "rules": rules,
        "auto_summary": auto_summary,
        "related_signals": {
            "fatigue": fatigue_signal,
            "daily_brief_today": brief_signal,
        },
        "principles": {
            "manual_priority": True,
            "intervention_isolated_from_knowledge_graph": True,
            "voice_features_default_off": True,
            "reminder_default_off": True,
        },
    }


async def emit_behavior_signal(
    user_id: str,
    signal_type: str,
    signal_data: dict,
    severity: int = 1,
) -> dict:
    """写入行为信号（由秘书事件消费或外部调用）

    重要：行为信号**仅提示用户**，**不**自动修改学习数据。
    """
    from app.services.secretary.mood_stress_store import mood_stress_store

    prefs = mood_stress_store.get_prefs(user_id)
    # 检查用户级细粒度开关
    flag_key = f"auto_collect_{signal_type}"
    if signal_type != "voice_features" and prefs.get(flag_key, True) is False:
        return {"status": "disabled", "reason": f"{flag_key}=false"}
    if signal_type == "voice_features" and not prefs.get("auto_collect_voice_features", False):
        return {"status": "disabled", "reason": "voice_features_disabled_by_default"}

    row = mood_stress_store.log_behavior_signal(
        user_id=user_id,
        signal_type=signal_type,
        signal_data=signal_data,
        severity=severity,
    )

    # 发布事件 (Task 架构 P0-1: 委托 publish_event_safe)
    from app.infrastructure.event_bus_utils import publish_event_safe
    from shared.events import MoodStressBehaviorSignalDetected
    publish_event_safe(MoodStressBehaviorSignalDetected(
        user_id=user_id,
        signal_type=signal_type,
        signal_data=signal_data,
        severity=severity,
    ))

    return row.to_dict()
