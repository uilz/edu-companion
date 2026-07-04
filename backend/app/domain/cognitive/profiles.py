"""
CognitiveNode 场景化 Profile — 按需加载

MasteryAtom: 核心字段（5 个），对话注入时使用
PracticeProfile: 练习场景扩展
PlanningProfile: 调度场景扩展
DiagnosisProfile: 诊断场景扩展
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class MasteryAtom:
    """核心掌握度原子 — 最小接口，对话注入时使用"""
    node_id: str
    label: str
    level: str  # partition/domain/topic/concept/atom
    proficiency_mean: float = 0.5  # Beta 分布均值
    proficiency_precision: float = 4.0  # Beta 分布精度 (alpha+beta)
    mastery_level: str = "未接触"  # 未接触/初学/发展中/接近掌握/已掌握
    last_updated: float = 0.0


@dataclass
class PracticeProfile:
    """练习场景扩展 — 练习反馈时加载"""
    atom: MasteryAtom
    total_attempts: int = 0
    correct_attempts: int = 0
    recent_success_rate: float = 0.0
    mean_latency_ms: float = 5000.0
    error_clusters: list[str] = field(default_factory=list)
    trend_direction: str = "stable"  # improving/stable/declining


@dataclass
class PlanningProfile:
    """调度场景扩展 — 学习计划时加载"""
    atom: MasteryAtom
    urgency: float = 0.0
    next_review: Optional[float] = None
    ease_factor: float = 2.5
    interval_days: int = 1
    repetitions: int = 0
    stagnation_days: float = 0.0
    cognitive_load: float = 1.0


@dataclass
class DiagnosisProfile:
    """诊断场景扩展 — 秘书诊断时加载"""
    atom: MasteryAtom
    error_pattern: Optional[str] = None
    forgetting_curve: float = 1.0
    review_urgency: float = 0.0
    engagement_score: float = 0.5
    goal_alignment: float = 0.0
    metacognition_score: float = 0.5


def extract_mastery_atom(node) -> MasteryAtom:
    """从 CognitiveNode 提取核心 MasteryAtom"""
    from app.domain.cognitive.models import CognitiveNode
    if isinstance(node, dict):
        return MasteryAtom(
            node_id=node.get("id", ""),
            label=node.get("label", ""),
            level=node.get("level", "atom"),
            proficiency_mean=node.get("proficiency_mean", 0.5),
            proficiency_precision=node.get("proficiency_precision", 4.0),
            mastery_level=_get_mastery_label(node.get("proficiency_mean", 0.5)),
            last_updated=node.get("last_updated", 0.0),
        )
    belief = node.belief
    return MasteryAtom(
        node_id=node.id,
        label=node.label,
        level=node.level,
        proficiency_mean=belief.proficiency_mean if belief else 0.5,
        proficiency_precision=belief.proficiency_precision if belief else 4.0,
        mastery_level=_get_mastery_label(belief.proficiency_mean if belief else 0.5),
        last_updated=belief.last_updated if belief else 0.0,
    )


def extract_practice_profile(node) -> PracticeProfile:
    """从 CognitiveNode 提取练习 Profile"""
    atom = extract_mastery_atom(node)
    summary = node.practice_summary if hasattr(node, 'practice_summary') else None
    trend = node.trend if hasattr(node, 'trend') else None
    error_clusters = node.error_clusters if hasattr(node, 'error_clusters') else None
    return PracticeProfile(
        atom=atom,
        total_attempts=summary.total_attempts if summary else 0,
        correct_attempts=summary.correct_attempts if summary else 0,
        recent_success_rate=summary.recent_success_rate_7d if summary else 0.0,
        mean_latency_ms=summary.mean_latency_7d if summary else 5000.0,
        error_clusters=[c.cluster_id for c in error_clusters] if error_clusters else [],
        trend_direction=trend.direction if trend else "stable",
    )


def extract_planning_profile(node) -> PlanningProfile:
    """从 CognitiveNode 提取调度 Profile"""
    atom = extract_mastery_atom(node)
    scheduling = node.scheduling if hasattr(node, 'scheduling') else None
    cognitive_load = node.cognitive_load if hasattr(node, 'cognitive_load') else None
    trend = node.trend if hasattr(node, 'trend') else None
    return PlanningProfile(
        atom=atom,
        urgency=scheduling.urgency if scheduling else 0.0,
        next_review=scheduling.next_review if scheduling else None,
        ease_factor=2.5,  # CognitiveNode 调度不含此字段，使用默认值
        interval_days=1,
        repetitions=0,
        stagnation_days=trend.stagnation_days if trend else 0.0,
        cognitive_load=cognitive_load.dynamic if cognitive_load else 1.0,
    )


def extract_diagnosis_profile(node) -> DiagnosisProfile:
    """从 CognitiveNode 提取诊断 Profile"""
    atom = extract_mastery_atom(node)
    diagnostic = node.diagnostic if hasattr(node, 'diagnostic') else None
    engagement = node.engagement if hasattr(node, 'engagement') else None
    goal = node.goal_alignment if hasattr(node, 'goal_alignment') else None
    meta = node.metacognition if hasattr(node, 'metacognition') else None
    scheduling = node.scheduling if hasattr(node, 'scheduling') else None
    return DiagnosisProfile(
        atom=atom,
        error_pattern=None,  # CognitiveNode 诊断不包含 error_pattern 字段
        forgetting_curve=1.0,
        review_urgency=scheduling.urgency if scheduling else 0.0,
        engagement_score=engagement.effort_estimate if engagement else 0.5,
        goal_alignment=goal.distance if goal else 0.0,
        metacognition_score=meta.self_assessment if meta else 0.5,
    )


def _get_mastery_label(mean: float) -> str:
    """[DEPRECATED] 使用 constants.proficiency_to_mastery_level 替代"""
    from app.domain.cognitive import constants as C
    return C.proficiency_to_mastery_level(mean)