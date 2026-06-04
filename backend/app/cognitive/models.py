"""CognitiveNode — 统一认知量子实体

基于 AI 伴学系统中枢数据设计文档 v2.10
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════
# 身份与层级
# ═══════════════════════════════════════════

class Prerequisite(BaseModel):
    id: str
    type: str = "strict"  # strict | suggested
    auto_required: bool = False


class UnlockGate(BaseModel):
    ref: str = "student.mastery_gate"
    value: float = 0.85
    cached_at: float = 0
    ttl_seconds: int = 3600


class Unlock(BaseModel):
    id: str
    gate: UnlockGate | None = None


class Associate(BaseModel):
    id: str
    strength: float = 0.5
    plasticity: dict[str, float] = Field(default_factory=lambda: {"hebbian": 0.01, "anti_hebbian": 0.005})
    label: str = ""
    domain: str = ""
    type: str = "analogy"  # analogy | prerequisite | contrast


# ═══════════════════════════════════════════
# ACT‑R 激活
# ═══════════════════════════════════════════

class Activation(BaseModel):
    base_level: float = 0.0
    retrieval_prob: float = 0.5
    latency_ms: float = 5000.0
    noise_sigma: dict[str, Any] = Field(default_factory=lambda: {"ref": "student.retrieval_sigma", "value": 0.3})
    spread_from_network: float = 0.0


# ═══════════════════════════════════════════
# 贝叶斯信念（Beta分布）
# ═══════════════════════════════════════════

class Belief(BaseModel):
    alpha: float = 2.0
    beta: float = 2.0
    proficiency_mean: float = 0.5  # α/(α+β)
    proficiency_precision: float = 4.0  # α+β
    peak_proficiency: float = 0.5
    last_updated: float = Field(default_factory=time.time)


# ═══════════════════════════════════════════
# 预测编码
# ═══════════════════════════════════════════

class Prediction(BaseModel):
    top_down_mean: float = 0.5
    prediction_error: float = 0.0
    error_flag: bool = False


# ═══════════════════════════════════════════
# 练习事件与摘要
# ═══════════════════════════════════════════

class PracticeEvent(BaseModel):
    timestamp: float
    success: bool
    latency_ms: float = 0
    weight: float = 1.0
    error_embedding: list[float] | None = None


class PracticeSummary(BaseModel):
    total_attempts: int = 0
    correct_attempts: int = 0
    total_time_spent: float = 0.0
    recent_success_rate_7d: float = 0.0
    mean_latency_7d: float = 0.0
    decayed_event_count: float = 0.0
    rapid_relearn_cooldown_until: float = 0.0
    last_practiced: float | None = None


# ═══════════════════════════════════════════
# 学习趋势
# ═══════════════════════════════════════════

class Trend(BaseModel):
    recent_proficiencies: list[float] = Field(default_factory=list)
    velocity_ewma: float = 0.0
    stagnation_days: float = 0.0
    volatility_std: float = 0.0
    direction: str = "stable"  # ascending | descending | plateau | volatile


# ═══════════════════════════════════════════
# 错误诊断
# ═══════════════════════════════════════════

class ErrorCluster(BaseModel):
    cluster_id: str
    count: int = 1
    last_seen: float = 0.0
    embedding: list[float] = Field(default_factory=list)


# ═══════════════════════════════════════════
# 认知负荷
# ═══════════════════════════════════════════

class CognitiveLoad(BaseModel):
    intrinsic: float = 0.5
    dynamic: float = 0.0
    aggregation_k: float = 1.0


# ═══════════════════════════════════════════
# 统一调度
# ═══════════════════════════════════════════

class Scheduling(BaseModel):
    urgency: float = 0.0
    next_review: float = 0.0
    interleaving_group: str = "default"
    last_interleaved_with: list[str] = Field(default_factory=list)
    next_action_type: str = "none"  # review | deep_processing | none


# ═══════════════════════════════════════════
# 目标对齐
# ═══════════════════════════════════════════

class GoalAlignment(BaseModel):
    toward_goal: str = ""
    distance: float = 0.0
    on_critical_path: bool = False


# ═══════════════════════════════════════════
# 诊断评估
# ═══════════════════════════════════════════

class Diagnostic(BaseModel):
    administered: bool = False
    score: float = 0.0
    inferred_proficiency: float = 0.0
    overrides_activation: bool = True
    timestamp: float = 0.0


# ═══════════════════════════════════════════
# 深度思考催化
# ═══════════════════════════════════════════

class DeepProcessingTrigger(BaseModel):
    pointer: str
    op: str  # >= | > | <= | < | == | != | array_length_gt | non_empty
    value: Any | None = None


class Template(BaseModel):
    id: str
    template: str
    trigger: dict[str, Any] | None = None
    plasticity_effects: dict[str, Any] | None = None


class DeepProcessing(BaseModel):
    task_templates: list[Template] = Field(default_factory=list)
    task_instances: list[dict[str, Any]] = Field(default_factory=list)


# ═══════════════════════════════════════════
# 深度连接
# ═══════════════════════════════════════════

class DeepLink(BaseModel):
    target: str
    strength: float = 0.3
    source: str = "student_insight"
    domain: str = ""
    type: str = "contrast"


# ═══════════════════════════════════════════
# 对话上下文联动
# ═══════════════════════════════════════════

class DialogueContext(BaseModel):
    session_id: str
    branch_id: str
    version: int = 1
    context_type: str = "upper"  # upper | lower
    last_discussed: float = Field(default_factory=time.time)
    relevance_score: float = 0.5
    summary_text: str = ""


# ═══════════════════════════════════════════
# 元认知
# ═══════════════════════════════════════════

class Metacognition(BaseModel):
    self_assessment: float = 0.5
    calibration_error: float = 0.0
    direction: str = "accurate"  # overconfident | underconfident | accurate


# ═══════════════════════════════════════════
# 激励
# ═══════════════════════════════════════════

class Engagement(BaseModel):
    xp: float = 0.0
    streak_current: int = 0
    effort_estimate: float = 0.5


# ═══════════════════════════════════════════
# 知识编译与Chunk演化
# ═══════════════════════════════════════════

class FormationCriteria(BaseModel):
    min_co_occurrence_sessions: int = 10
    min_individual_auto_probability: float = 0.8
    consecutive_sessions: int = 5


class SessionSnapshot(BaseModel):
    skill_ids: list[str] = Field(default_factory=list)
    all_proficient: bool = False


class FormationTracker(BaseModel):
    co_occurrence_sessions: int = 0
    consecutive_sessions_met: int = 0
    last_session_id: str = ""
    last_session_snapshot: SessionSnapshot | None = None


class Composition(BaseModel):
    chunk_id: str | None = None
    chunking_status: str = "none"  # none | forming | formed
    formation_criteria: FormationCriteria = Field(default_factory=FormationCriteria)
    formation_tracker: FormationTracker = Field(default_factory=FormationTracker)


# ═══════════════════════════════════════════
# 事件
# ═══════════════════════════════════════════

class CognitiveEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    event_type: str
    user_id: str
    node_id: str | None = None
    timestamp: float = Field(default_factory=time.time)
    payload: dict[str, Any] = Field(default_factory=dict)


class MetaInfo(BaseModel):
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: int = 1


# ═══════════════════════════════════════════
# CognitiveNode
# ═══════════════════════════════════════════

class CognitiveNode(BaseModel):
    """统一的认知量子实体——每个知识点（从分区到原子技能）共用同一种结构"""

    # ─── 身份与层级 ───
    id: str
    label: str = ""
    level: str = "atom"  # partition | domain | topic | concept | atom
    parent: str | None = None
    children: list[str] = Field(default_factory=list)
    is_core: bool = False
    brief: str = ""  # 节点简介（由 AI 或用户维护的内容摘要）

    # ─── 图谱结构 ───
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    unlocks: list[Unlock] = Field(default_factory=list)
    associates: list[Associate] = Field(default_factory=list)

    # ─── ACT‑R 激活 ───
    activation: Activation = Field(default_factory=Activation)

    # ─── 贝叶斯信念 ───
    belief: Belief = Field(default_factory=Belief)

    # ─── 预测编码 ───
    prediction: Prediction = Field(default_factory=Prediction)

    # ─── 认知负荷 ───
    cognitive_load: CognitiveLoad = Field(default_factory=CognitiveLoad)

    # ─── 练习 ───
    practice_events: list[PracticeEvent] = Field(default_factory=list)
    practice_summary: PracticeSummary = Field(default_factory=PracticeSummary)

    # ─── 学习趋势 ───
    trend: Trend = Field(default_factory=Trend)

    # ─── 错误诊断 ───
    error_clusters: list[ErrorCluster] = Field(default_factory=list)

    # ─── 统一调度 ───
    scheduling: Scheduling = Field(default_factory=Scheduling)

    # ─── 目标对齐 ───
    goal_alignment: GoalAlignment = Field(default_factory=GoalAlignment)

    # ─── 诊断 ───
    diagnostic: Diagnostic = Field(default_factory=Diagnostic)

    # ─── 深度思考 ───
    deep_processing: DeepProcessing = Field(default_factory=DeepProcessing)

    # ─── 深度连接 ───
    deep_links: list[DeepLink] = Field(default_factory=list)

    # ─── 对话上下文联动 ───
    dialogue_contexts: list[DialogueContext] = Field(default_factory=list)

    # ─── 元认知 ───
    metacognition: Metacognition = Field(default_factory=Metacognition)

    # ─── 激励 ───
    engagement: Engagement = Field(default_factory=Engagement)

    # ─── 知识编译 ───
    composition: Composition = Field(default_factory=Composition)

    # ─── 参数引用 ───
    param_refs: dict[str, str] = Field(default_factory=lambda: {
        "decay_factor": "student.decay_factor",
        "mastery_gate": "student.mastery_gate",
        "retrieval_sigma": "student.retrieval_sigma",
        "min_pseudo_count": "student.min_pseudo_count",
        "diagnostic_precision": "student.diagnostic_precision",
        "sched_retention_weight": "student.sched_retention_weight",
        "sched_mastery_push_weight": "student.sched_mastery_push_weight",
        "sched_interleaving_weight": "student.sched_interleaving_weight",
        "sched_core_boost": "student.sched_core_boost",
        "sched_stagnation_penalty": "student.sched_stagnation_penalty",
        "fatigue_decay_lambda": "student.fatigue_decay_lambda",
        "fatigue_increment_eta": "student.fatigue_increment_eta",
        "velocity_decay_lambda": "student.velocity_decay_lambda",
    })

    # ─── 元信息 ───
    meta: MetaInfo = Field(default_factory=MetaInfo)

    # ─── Phase 8 认知图字段 ───
    path_id: str = ""           # 不变路径标识，如 "大学物理.电磁学.静电场"
    node_type: str = "explicit"  # explicit | auto_generated | user_created | suggested
    is_visible: bool = False
    subsystems: dict = Field(default_factory=dict)
    embedding: list[float] | None = None
    is_active: bool = True

    # ─── 结构字段（从 user_meta JSONB 迁移） ───
    emoji: str = ""
    color: str = ""
    sort_order: int = 0

    def update_timestamp(self):
        self.meta.updated_at = time.time()

    def bump_version(self):
        self.meta.version += 1
        self.update_timestamp()

    @property
    def proficiency(self) -> float:
        return self.belief.proficiency_mean

    @property
    def precision(self) -> float:
        return self.belief.proficiency_precision


# ═══════════════════════════════════════════
# 用户级全局状态
# ═══════════════════════════════════════════

class UserCognitiveState(BaseModel):
    user_id: str
    daily_practice_count: int = 0
    fatigue_level: float = 0.0
    current_session_id: str = ""
    session_start_time: float = Field(default_factory=time.time)
    last_activity_time: float = Field(default_factory=time.time)
    practice_count_this_session: int = 0
