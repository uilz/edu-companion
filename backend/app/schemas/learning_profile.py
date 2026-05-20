"""
v3.0 学习画像数据模型

核心实体：SkillAtom — 唯一的「知识点」实体
分区画像：PartitionProgress — 一个分区的完整学习进度
全局画像：StudentProfile — 跨分区学习状态

所有模块通过 SkillAtom 交汇，不再各自维护独立副本。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════
# SkillAtom — 原子学习单元
# ═══════════════════════════════════════════════════

class SkillAtom(BaseModel):
    """唯一的「知识点」实体。图谱/BKT/练习/会话 都读/写这一个对象。"""

    # ── 身份 ──
    id: str = ""
    label: str = ""
    description: str = ""
    partition_id: str = ""
    created_by: str = "ai"                       # "ai" | "user"

    # ── 图谱属性 ──
    priority: int = 5                            # 学习优先级 1-10
    depth: int = 0                               # 拓扑层级（计算得出）
    prerequisites: list[str] = Field(default_factory=list)
    unlocks: list[str] = Field(default_factory=list)

    # ── BKT 掌握度（嵌入在实体上）──
    bkt_p_know: float = 0.1
    bkt_p_learn: float = 0.3
    bkt_p_guess: float = 0.25
    bkt_p_slip: float = 0.1
    mastery: float = 0.0                         # p_know × 100
    mastery_level: str = "未接触"                 # 已掌握|接近掌握|发展中|初学|未接触
    confidence: float = 0.0                      # BKT 观测信度（0-1，样本少→低）

    # ── 练习历史 ──
    attempt_count: int = 0
    correct_count: int = 0
    last_practiced: Optional[datetime] = None
    time_spent_minutes: float = 0.0
    error_clusters: list[str] = Field(default_factory=list)

    # ── 趋势 ──
    trend: str = "stable"                        # improving|stable|declining|plateau
    stagnation_days: int = 0
    velocity: float = 0.0                        # 本周 mastery 变化

    # ── 遗忘 ──
    forgetting_curve: float = 1.0                # 1=刚学，指数衰减
    review_urgency: float = 0.0                  # 0-1，>0.7 需立即复习

    # ── 时间戳 ──
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════
# PartitionProgress — 一个分区的完整进度画像
# ═══════════════════════════════════════════════════

class Coverage(BaseModel):
    total: int = 0
    touched: int = 0
    assessed: int = 0
    mastered: int = 0
    learning: int = 0
    weak: int = 0
    untouched: int = 0


class SkillNodeState(BaseModel):
    """知识点在某个学生身上的完整状态（PartitionProgress 内嵌）"""
    skill_id: str
    label: str
    description: str = ""
    mastery: float = 0.0
    mastery_level: str = "未接触"
    confidence: float = 0.0
    trend: str = "stable"
    depth: int = 0
    prerequisites: list[str] = Field(default_factory=list)
    prerequisites_met: bool = False
    blocked: bool = True
    attempt_count: int = 0
    correct_count: int = 0
    last_practiced: Optional[datetime] = None
    error_clusters: list[str] = Field(default_factory=list)
    forgetting_curve: float = 1.0
    review_urgency: float = 0.0


class Dependency(BaseModel):
    from_skill: str
    to_skill: str
    relation: str = "prerequisite"
    satisfied: bool = False
    student_deviation: Optional[str] = None      # "跳过了前置但学会了后置"


class PathDeviation(BaseModel):
    skill_id: str
    expected_at: int
    actual_at: int
    reason: str = ""


class LearningPath(BaseModel):
    ideal_order: list[str] = Field(default_factory=list)
    actual_order: list[str] = Field(default_factory=list)
    deviations: list[PathDeviation] = Field(default_factory=list)
    frontier: list[str] = Field(default_factory=list)
    review_queue: list[str] = Field(default_factory=list)


class SkillCluster(BaseModel):
    skills: list[str] = Field(default_factory=list)
    correlation: float = 0.0
    type: str = ""                               # co-mastered|co-weak|co-confused
    interpretation: str = ""


class Anomaly(BaseModel):
    type: str = ""                               # mastered_without_prereq|long_stagnation|rapid_forgetting|high_variance
    skills: list[str] = Field(default_factory=list)
    detail: str = ""
    severity: str = "info"                       # warning | info


class TemporalMetrics(BaseModel):
    learning_velocity: float = 0.0               # 每周掌握技能数
    estimated_completion_days: int = 0
    review_backlog: int = 0
    daily_practice_minutes: float = 0.0


class PartitionProgress(BaseModel):
    """一个分区的完整学习进度画像"""
    partition_id: str
    partition_name: str = ""
    partition_emoji: str = "📁"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    coverage: Coverage = Field(default_factory=Coverage)
    skills: dict[str, SkillNodeState] = Field(default_factory=dict)
    dependencies: list[Dependency] = Field(default_factory=list)
    learning_path: LearningPath = Field(default_factory=LearningPath)
    clusters: list[SkillCluster] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)
    temporal: TemporalMetrics = Field(default_factory=TemporalMetrics)


# ═══════════════════════════════════════════════════
# StudentProfile — 跨分区全局画像
# ═══════════════════════════════════════════════════

class LearningContext(BaseModel):
    """当前学习情境"""
    partition_id: Optional[str] = None
    session_duration_minutes: int = 0
    time_of_day: str = "morning"
    recent_correct_rate: float = 1.0
    recent_switch_count: int = 0
    explicit_goal: Optional[str] = None
    emotion_trend: str = "stable"


class StudentProfile(BaseModel):
    """跨分区全局学习画像"""
    user_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 各分区进度
    partition_progresses: dict[str, PartitionProgress] = Field(default_factory=dict)

    # 认知状态
    cognitive_load: float = 0.0
    frustration_level: float = 0.0
    fatigue_index: float = 0.0

    # 学习节奏
    daily_practice_minutes: list[int] = Field(default_factory=list)
    streak_days: int = 0
    subject_switch_frequency: float = 0.0
    peak_hours: list[int] = Field(default_factory=list)

    # 近期事件
    recent_events: list[dict] = Field(default_factory=list)
    upcoming_deadlines: list[dict] = Field(default_factory=list)

    # 当前情境
    current_context: LearningContext = Field(default_factory=LearningContext)
