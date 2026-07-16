"""
Learning Runtime — Core Data Models.

These are the Pydantic models for AppleGo's Learning Runtime.
All LI modules read/write through RuntimeContext,
which is the single mutable source for a Session.

Principles:
  P4 — Shared Context, Isolated Capability
  P8 — RuntimeContext is the single mutable source

This module should NOT import from other domain modules.
It defines the Runtime data contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────
# 1. RuntimeContext — Session 内唯一可变对象
# ────────────────────────────────────────────────────────────

class RuntimeContext(BaseModel):
    """一次 Session 的运行时上下文。所有 LI 模块读写此对象。"""
    session_id: str
    user_id: str
    mission: "MissionContext"
    learner: "LearnerContext"
    flow: "FlowContext"
    understanding: "UnderstandingContext"
    reflection: "ReflectionContext"
    conversation: "ConversationContext"


# ────────────────────────────────────────────────────────────
# 2. Mission Context
# ────────────────────────────────────────────────────────────

class MissionSource(str, Enum):
    USER_TOPIC = "user_topic"
    WELCOME_BACK = "welcome_back"
    SYSTEM_RECOMMEND = "system_recommend"


class MissionContext(BaseModel):
    title: str
    source: MissionSource
    analysis: Optional["MissionAnalysis"] = None


class MissionAnalysis(BaseModel):
    """LI-01 输出的结构化 Mission 理解。"""
    concepts: list["ConceptItem"]
    dependencies: list["DependencyItem"]
    learning_objectives: list[str]
    difficulty_spots: list["DifficultySpot"]
    practice_strategy: Optional["PracticeStrategy"] = None
    reflection_focus: list[str]
    growth_signals: "GrowthSignals"


class ConceptItem(BaseModel):
    name: str
    importance: str  # "high" | "medium" | "low"
    description: str
    confidence: Optional[float] = None  # P7


class DependencyItem(BaseModel):
    concept: str
    importance: str  # "required" | "recommended"


class DifficultySpot(BaseModel):
    point: str
    common_misconception: str
    difficulty_level: int = Field(ge=1, le=5)
    confidence: Optional[float] = None


class PracticeStrategy(BaseModel):
    type: str  # "explanation" | "comparison" | "correction"
    focus: str


class GrowthSignals(BaseModel):
    expected_gains: list[str]
    observation_points: list[str]


# ────────────────────────────────────────────────────────────
# 3. Learner Context
# ────────────────────────────────────────────────────────────

class SkillState(BaseModel):
    proficiency: float = Field(ge=0.0, le=1.0)
    precision: float = Field(ge=0.0, le=1.0)
    trend: str  # "ascending" | "stable" | "declining"
    last_active: Optional[datetime] = None


class LearnerProfile(BaseModel):
    subjects: list[str]
    grade_level: str
    learning_style: Optional[str] = None  # "visual" | "reading" | "kinesthetic"


class GrowthRecord(BaseModel):
    session_id: str
    skill_gains: list[str]
    summary: str
    key_takeaways: list[str]
    reflection_snippet: Optional[str] = None
    created_at: datetime


class ReasoningPattern(BaseModel):
    prefers_analogy: Optional[bool] = None
    needs_visualization: Optional[bool] = None
    tends_to_overgeneralize: Optional[bool] = None
    catches_edge_cases: Optional[bool] = None


class LearnerContext(BaseModel):
    knowledge: Dict[str, SkillState]
    profile: LearnerProfile
    recent_growth: Optional[GrowthRecord] = None
    patterns: Optional[ReasoningPattern] = None


# ────────────────────────────────────────────────────────────
# 4. Flow Context
# ────────────────────────────────────────────────────────────

class Exp04Stage(str, Enum):
    ENTER = "ENTER"
    LEARN = "LEARN"
    COGNITIVE_SEARCH = "COGNITIVE_SEARCH"
    SELF_VALIDATION = "SELF_VALIDATION"
    REFLECTION = "REFLECTION"
    END = "END"


class FlowContext(BaseModel):
    current_stage: Exp04Stage
    cognitive_search_triggered: bool = False
    cognitive_search_duration_ms: Optional[int] = None


# ────────────────────────────────────────────────────────────
# 5. Understanding Context
# ────────────────────────────────────────────────────────────

class UnderstandingContext(BaseModel):
    user_text: str
    reference_text: str
    analysis: Optional["UnderstandingAnalysis"] = None
    guidance_given: Optional[str] = None


class UnderstandingAnalysis(BaseModel):
    """LI-02 输出。使用 Observation / Evidence / Hypothesis 三元组。"""
    concept_observations: list["ConceptObservation"]
    reasoning_evidence: "ReasoningEvidence"
    gaps: list["UnderstandingGap"]
    metacognitive_signals: "MetacognitiveSignals"
    learner_delta: "LearnerDelta"


class ConceptObservation(BaseModel):
    concept: str
    observation: str
    evidence: str
    hypothesis: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReasoningEvidence(BaseModel):
    uses_own_words: bool
    makes_connections: list[str]
    asks_questions: list[str]


class UnderstandingGap(BaseModel):
    concept: str
    observation: str
    evidence: str
    hypothesis: str
    severity: int = Field(ge=1, le=3)
    confidence: float = Field(ge=0.0, le=1.0)


class MetacognitiveSignals(BaseModel):
    aware_of_gap: bool
    overconfident_on: list[str]


class KnowledgeUpdate(BaseModel):
    skill_id: str
    confidence_shift: float = Field(ge=-1.0, le=1.0)
    evidence: str


class LearnerDelta(BaseModel):
    knowledge_updates: list[KnowledgeUpdate]
    reasoning_insights: list[str]
    growth_insights: list[str]


# ────────────────────────────────────────────────────────────
# 6. Reflection Context
# ────────────────────────────────────────────────────────────

class ReflectionContext(BaseModel):
    content: Optional[str] = None
    was_skipped: bool = False


# ────────────────────────────────────────────────────────────
# 7. Conversation Context
# ────────────────────────────────────────────────────────────

class ChatMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    id: str
    role: ChatMessageRole
    content: str
    created_at: datetime


class ConversationContext(BaseModel):
    is_open: bool = False
    round_count: int = 0
    messages: list[ChatMessage] = []


# ────────────────────────────────────────────────────────────
# Forward references for Pydantic v2
# ────────────────────────────────────────────────────────────

RuntimeContext.model_rebuild()
UnderstandingContext.model_rebuild()
