"""秘书系统核心数据模型 — 分析洞察层 + 诊断 + 提案的共享模型

设计原则：
- 所有分析函数统一使用 ScopedInsight / AnalysisResult 返回
- 归一化评分 (norm_urgency / norm_priority) 让策略引擎可跨类型比较优先级
- ScopeSpec 覆盖 6 层 (user → partition → domain → topic → concept → atom)
"""

from __future__ import annotations

import time
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════
# 范围控制
# ═══════════════════════════════════════════

ScopeLevel = Literal["user", "partition", "domain", "topic", "concept", "atom"]


class ScopeSpec(BaseModel):
    """分析范围 — 支持 6 层粒度"""
    level: ScopeLevel = "user"
    node_id: str | None = None  # level=user 时不需要

    def to_dict(self) -> dict:
        return {"level": self.level, "node_id": self.node_id}


class AnalyzeOptions(BaseModel):
    """分析参数 — 所有分析函数共用"""
    threshold: float = 0.6               # 薄弱/紧迫阈值
    max_items: int = 10                  # 结果上限
    min_confidence: float = 0.0          # 最低置信度 (α+β)
    sort_by: Literal["urgency", "decline", "stagnation"] = "urgency"
    include_children: bool = False       # 是否展开子层详情
    lookback_days: int = 7               # 回顾窗口
    lookahead_hours: int = 24            # 预测窗口


# ═══════════════════════════════════════════
# 统一分析结果
# ═══════════════════════════════════════════

class AnalysisMeta(BaseModel):
    """分析元信息"""
    scope: ScopeSpec
    source_nodes: int = 0                # 涉及节点数
    data_quality: Literal["high", "medium", "low", "cold_start"] = "medium"
    computed_at: float = Field(default_factory=time.time)


class ScoredInsight(BaseModel):
    """带评分的洞察项 — 所有分析函数的通用产出单元

    归一化评分说明:
      - norm_urgency: 0-1，越高越紧迫（跨类型可比）
      - norm_priority: 0-1，越高越优先（urgency * confidence * 数据量加权）
    """
    node_id: str
    label: str
    level: str                           # atom | concept | topic | ...
    parent_path: list[str] = Field(default_factory=list)

    # 核心值
    primary_value: float = 0.0           # 主值
    primary_label: str = ""              # 主值说明，如 "掌握度 / 紧迫度 / 变化率"

    # 归一化评分
    norm_urgency: float = 0.0            # 0-1，越高越紧迫
    norm_priority: float = 0.0           # 0-1，组合优先级

    # 置信度
    confidence: float = 1.0              # 0-1
    data_points: int = 0                 # 涉及的数据点数量

    # 补充字段
    trend: str = "stable"                # ascending | descending | plateau
    top_error_pattern: str = ""          # 主要错误类型
    extra: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """所有分析函数的统一返回值"""
    analysis_type: str
    meta: AnalysisMeta
    items: list[ScoredInsight] = Field(default_factory=list)
    summary: str = ""                    # 一句话总结（可由规则或 LLM 生成）
    top_priority: str | None = None     # "建议优先处理: ..."


# ═══════════════════════════════════════════
# 归一化工具
# ═══════════════════════════════════════════

ValueType = Literal[
    "proficiency", "stagnation_days", "forgetting_risk",
    "cognitive_load", "error_frequency", "latency_ms",
]


def normalize_value(raw: float, value_type: ValueType) -> float:
    """将不同类型的原始值映射到 0-1 紧迫度"""
    if value_type == "proficiency":
        return max(0.0, min(1.0, 1.0 - raw))
    elif value_type == "stagnation_days":
        return max(0.0, min(1.0, raw / 14.0))
    elif value_type == "forgetting_risk":
        return max(0.0, min(1.0, raw * 1.2))
    elif value_type == "cognitive_load":
        return max(0.0, min(1.0, (raw - 0.5) * 2.0))
    elif value_type == "error_frequency":
        return max(0.0, min(1.0, raw))
    elif value_type == "latency_ms":
        # 延迟异常：> 3x 基线
        return max(0.0, min(1.0, (raw - 1000.0) / 10000.0))
    return max(0.0, min(1.0, raw))


def compute_priority(norm_urgency: float, confidence: float, data_points: int) -> float:
    """计算组合优先级 — urgency * confidence * 数据量衰减"""
    data_factor = min(data_points / 10.0, 1.0)
    return round(norm_urgency * confidence * (0.5 + 0.5 * data_factor), 4)


# ═══════════════════════════════════════════
# 秘书特定模型
# ═══════════════════════════════════════════

class WeakPoint(BaseModel):
    """诊断报告中的薄弱点"""
    knowledge_point_id: str
    name: str
    mastery: float
    error_pattern: str = ""
    trend: str = "stable"

    @classmethod
    def from_insight(cls, insight: ScoredInsight) -> "WeakPoint":
        # primary_value 存储的就是 proficiency_mean
        mastery = insight.primary_value if insight.primary_label == "平均掌握度" else 1.0 - insight.norm_urgency
        return cls(
            knowledge_point_id=insight.node_id,
            name=insight.label,
            mastery=round(mastery, 4),
            error_pattern=insight.top_error_pattern,
            trend=insight.trend,
        )


class DiagnosisReport(BaseModel):
    """诊断报告"""
    user_id: str
    snapshot_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    generated_at: float = Field(default_factory=time.time)
    weak_points: list[WeakPoint] = Field(default_factory=list)
    cognitive_load: float = 0.0
    highlight: str = ""
    summary: str = ""
    source_findings: list[str] = Field(default_factory=list)  # 使用了哪些分析函数


class Proposal(BaseModel):
    """协商提案"""
    id: str = Field(default_factory=lambda: str(uuid4())[:12])
    emoji: str = ""
    title: str
    description: str = ""
    action_type: str = ""                # review / practice / rest / explore / exam_prep / plan / deep_process / daily_brief / conversation
    payload: dict = Field(default_factory=dict)
    priority: int = 3                    # 1-5
    generated_by: str = ""               # 来源模块名
    overrideable: bool = True
    meta_reflection_prompt: str | None = None
    insight_source: str | None = None    # 关联的分析函数名
    insight_evidence: list[str] = Field(default_factory=list)  # 可解释证据摘要
    correlation_id: str = ""             # 关联事件/会话 ID
    caused_by_event_id: str | None = None
    created_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    presented_at: float | None = None    # 首次展示给用户的时间


class UserContext(BaseModel):
    """用户情境快照"""
    user_id: str
    current_session_active: bool = False
    last_active_at: float = 0.0
    cognitive_load_estimate: float = 0.0
    is_quiet_hours: bool = False
    predicted_intent: str = "learning"
    interaction_preferences: dict = Field(default_factory=dict)


class RelationMemoryEntry(BaseModel):
    """用户对某类提案的关系记忆"""
    action_type: str
    target_id: str = ""
    accept_count: int = 0
    ignore_count: int = 0
    last_interaction_at: float | None = None
    effective_priority_bias: int = 0


class UserOrchestrationProfile(BaseModel):
    """用户编排画像 — 秘书对用户的长期记忆与策略状态"""
    user_id: str
    trust_score: float = 0.5             # 0-1，越高用户越信任秘书提案
    fatigue_score: float = 0.0           # 0-1，越高越应减少打扰
    proactive_quota_today: int = 5       # 今日剩余可推送提案数
    last_proactive_at: float | None = None
    enabled_modules: list[str] = Field(default_factory=lambda: [
        "review_reminder", "fatigue_manager", "daily_brief", "behavior_trigger"
    ])
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    relation_memory: dict[str, RelationMemoryEntry] = Field(default_factory=dict)
    version: int = 0


class SilentTask(BaseModel):
    """静默后台任务 — 秘书编排器在后台执行的预计算任务"""
    id: str = Field(default_factory=lambda: str(uuid4())[:12])
    user_id: str = ""
    task_type: str                        # prepare_review_list / pre_generate_quiz / compute_diagnosis / generate_daily_brief / expand_knowledge_graph
    payload: dict = Field(default_factory=dict)
    status: str = "pending"               # pending / running / ready / failed / consumed
    result_ref: str = ""                  # 结果引用 ID
    priority: int = 3                     # 1-5，越小越优先
    created_at: float = Field(default_factory=time.time)
    ready_at: float | None = None         # 预计/实际可消费时间
    consumed_at: float | None = None


class SecretaryPrefs(BaseModel):
    """用户秘书偏好设置"""
    enabled_extensions: list[str] = Field(default_factory=lambda: [
        "review_reminder", "fatigue_manager", "daily_brief"
    ])
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    max_proactive_per_day: int = 5
    custom_rules: list[dict] = Field(default_factory=list)
    privacy_calendar_enabled: bool = False
    privacy_device_activity_enabled: bool = False
