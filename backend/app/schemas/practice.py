"""
练习系统数据模型 v2.0
支持：多维知识状态、Bloom分类、自适应调度、错因分析、用户资料索引
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 枚举定义
# ──────────────────────────────────────────────

class BloomLevel(str, Enum):
    """Bloom认知层次"""
    REMEMBER = "remember"       # 记忆
    UNDERSTAND = "understand"   # 理解
    APPLY = "apply"             # 应用
    ANALYZE = "analyze"         # 分析
    EVALUATE = "evaluate"       # 评价
    CREATE = "create"           # 创造


class Difficulty(str, Enum):
    """难度等级"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AnswerType(str, Enum):
    """答案类型"""
    CHOICE = "choice"
    FILL = "fill"
    FREE_FORM = "free_form"
    CALCULATION = "calculation"


class ErrorType(str, Enum):
    """错误类型"""
    CONCEPTUAL = "conceptual"       # 概念错误
    PROCEDURAL = "procedural"       # 程序错误
    COMPUTATION = "computation"     # 计算错误
    READING = "reading"             # 审题错误
    TRANSFER = "transfer"           # 迁移错误
    META_COGNITIVE = "meta"         # 元认知错误


class SessionStatus(str, Enum):
    """练习会话状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class QuestionStatus(str, Enum):
    """题目状态"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"       # 质量差，已降权
    UNDER_REVIEW = "under_review"   # 待人工审核


# ──────────────────────────────────────────────
# 知识状态（多维）
# ──────────────────────────────────────────────

class KnowledgeDimension(BaseModel):
    """单个知识维度的状态"""
    dimension_id: str                           # concept/procedure/application/transfer
    p_known: float = Field(default=0.0, ge=0.0, le=1.0)
    p_learned: float = Field(default=0.0, ge=0.0, le=1.0)
    last_practiced: datetime = Field(default_factory=datetime.now)
    attempt_count: int = 0
    correct_count: int = 0
    streak: int = 0
    error_patterns: list[str] = Field(default_factory=list)


class ExplanationState(BaseModel):
    """解释能力状态"""
    last_explained: datetime = Field(default_factory=datetime.now)
    explanation_count: int = 0
    avg_explanation_score: float = 0.0
    stability: float = 1.0  # 知识稳定性（影响遗忘曲线）


class KnowledgeState(BaseModel):
    """知识点的多维状态"""
    skill_id: str
    dimensions: dict[str, KnowledgeDimension] = Field(default_factory=lambda: {
        "concept": KnowledgeDimension(dimension_id="concept"),
        "procedure": KnowledgeDimension(dimension_id="procedure"),
        "application": KnowledgeDimension(dimension_id="application"),
        "transfer": KnowledgeDimension(dimension_id="transfer"),
    })
    prerequisite_states: dict[str, float] = Field(default_factory=dict)
    misconception_flags: list[str] = Field(default_factory=list)
    pseudo_mastery_flags: list[str] = Field(default_factory=list)
    confidence_level: float = 0.5
    explanation_state: Optional[ExplanationState] = None

    # BKT参数
    p_known: float = Field(default=0.0, ge=0.0, le=1.0)
    p_learned: float = Field(default=0.0, ge=0.0, le=1.0)
    p_guess: float = Field(default=0.25, ge=0.0, le=1.0)
    p_slip: float = Field(default=0.1, ge=0.0, le=1.0)
    p_transit: float = Field(default=0.3, ge=0.0, le=1.0)
    attempt_count: int = 0
    correct_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.now)
    mastery_threshold: float = Field(default=0.8)

    @property
    def is_mastered(self) -> bool:
        return self.p_known >= self.mastery_threshold

    @property
    def accuracy(self) -> float:
        if self.attempt_count == 0:
            return 0.0
        return self.correct_count / self.attempt_count

    @property
    def avg_dimension_p(self) -> float:
        """四个维度的平均掌握度"""
        dims = list(self.dimensions.values())
        if not dims:
            return 0.0
        return sum(d.p_known for d in dims) / len(dims)


# ──────────────────────────────────────────────
# 题目
# ──────────────────────────────────────────────

class ImageContent(BaseModel):
    """图片内容"""
    image_type: str = "diagram"     # geometry/diagram/graph/photo/equation
    svg_data: Optional[str] = None
    image_url: Optional[str] = None
    description: str = ""


class QuestionOption(BaseModel):
    """选择题选项"""
    letter: str                     # A/B/C/D
    text: str
    is_correct: bool
    distractor_type: Optional[str] = None  # 干扰项类型（用于错因分析）


class Question(BaseModel):
    """练习题（增强版）"""
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str
    subject: str

    # Bloom分类
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    cognitive_skills: list[str] = Field(default_factory=list)

    # 内容
    text: str                               # 题目文本
    math_latex: list[str] = Field(default_factory=list)
    images: list[ImageContent] = Field(default_factory=list)
    options: Optional[list[QuestionOption]] = None  # 选择题选项
    answer_type: AnswerType = AnswerType.CHOICE
    correct_answer: str = ""
    answer_format: str = ""

    # 难度与质量
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    discrimination: float = Field(default=1.0, ge=0.0, le=2.0)
    guessing: float = Field(default=0.25, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # 元数据
    source: str = "llm"                     # llm/manual/imported/material
    tags: list[str] = Field(default_factory=list)
    explanation: str = ""
    hints: list[str] = Field(default_factory=list)
    video_url: Optional[str] = None
    related_skills: list[str] = Field(default_factory=list)
    material_chunk_id: Optional[str] = None  # 来源的资料chunk

    # 验证
    status: QuestionStatus = QuestionStatus.ACTIVE
    verified: bool = False
    usage_count: int = 0
    avg_correct_rate: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)


# ──────────────────────────────────────────────
# 答题记录
# ──────────────────────────────────────────────

class ErrorAnalysis(BaseModel):
    """错因分析"""
    error_type: ErrorType
    error_subtype: str = ""
    misconception: Optional[str] = None
    related_skills: list[str] = Field(default_factory=list)
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    suggestion: str = ""


class AttemptRecord(BaseModel):
    """单次答题记录"""
    attempt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    question_id: str
    session_id: Optional[str] = None

    # 答题
    user_answer: str
    is_correct: bool
    time_spent_seconds: float = 0.0

    # 认知诊断
    error_analysis: Optional[ErrorAnalysis] = None
    bloom_level_attempted: BloomLevel = BloomLevel.UNDERSTAND

    # 提示使用
    hints_used: int = 0
    hint_levels: list[int] = Field(default_factory=list)

    # 解释评分
    explanation_text: Optional[str] = None
    explanation_score: Optional[float] = None

    # 知识状态快照
    knowledge_before: dict[str, float] = Field(default_factory=dict)
    knowledge_after: dict[str, float] = Field(default_factory=dict)

    # 时间戳
    started_at: datetime = Field(default_factory=datetime.now)
    submitted_at: datetime = Field(default_factory=datetime.now)


# ──────────────────────────────────────────────
# 练习会话
# ──────────────────────────────────────────────

class PracticeSession(BaseModel):
    """一次练习会话"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str

    # 规划
    planned_skills: list[str] = Field(default_factory=list)
    planned_bloom_levels: list[BloomLevel] = Field(default_factory=list)
    estimated_minutes: int = 30
    mode: str = "adaptive"  # adaptive/targeted/review/challenge/contextual

    # 执行
    question_ids: list[str] = Field(default_factory=list)
    current_index: int = 0
    attempts: list[AttemptRecord] = Field(default_factory=list)

    # 统计
    correct_count: int = 0
    total_hints_used: int = 0
    avg_time_per_question: float = 0.0

    # 状态
    status: SessionStatus = SessionStatus.ACTIVE
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # 情感状态
    frustration_level: float = 0.0
    engagement_level: float = 0.5

    @property
    def total_questions(self) -> int:
        return len(self.question_ids)

    @property
    def accuracy(self) -> float:
        if self.total_questions == 0:
            return 0.0
        return self.correct_count / self.total_questions

    @property
    def duration_minutes(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() / 60
        return (datetime.now() - self.started_at).total_seconds() / 60

    @property
    def struggling_skills(self) -> list[str]:
        """找出薄弱知识点"""
        skill_errors: dict[str, int] = {}
        for attempt in self.attempts:
            if not attempt.is_correct:
                skill = attempt.error_analysis.related_skills[0] if attempt.error_analysis and attempt.error_analysis.related_skills else "unknown"
                skill_errors[skill] = skill_errors.get(skill, 0) + 1
        return sorted(skill_errors.keys(), key=lambda s: skill_errors[s], reverse=True)

    def last_n_results(self, n: int) -> list[AttemptRecord]:
        return self.attempts[-n:] if self.attempts else []

    def recent_errors_for_skill(self, skill_id: str, n: int) -> list[AttemptRecord]:
        errors = [a for a in self.attempts if not a.is_correct and a.error_analysis and skill_id in a.error_analysis.related_skills]
        return errors[-n:]


# ──────────────────────────────────────────────
# 错题本
# ──────────────────────────────────────────────

class ErrorBookEntry(BaseModel):
    """错题本条目"""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    question_id: str
    skill_id: str

    # 错误信息
    error_type: ErrorType
    misconception: Optional[str] = None
    user_answer: str = ""
    correct_answer: str = ""
    question_text: str = ""

    # 复习
    review_count: int = 0
    next_review: datetime = Field(default_factory=datetime.now)
    mastery_after_review: float = 0.0

    # 关联材料
    referenced_materials: list[dict[str, Any]] = Field(default_factory=list)

    # 状态
    is_resolved: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    # 深度错因分析
    attribution: Optional[dict[str, Any]] = None  # {primary, secondary, analysis, recommendation}


# ──────────────────────────────────────────────
# 用户资料
# ──────────────────────────────────────────────

class MaterialChunk(BaseModel):
    """用户上传资料的一个分块"""
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    material_id: str

    # 内容
    text: str
    image_urls: list[str] = Field(default_factory=list)
    chunk_type: str = "text"  # text/question/solution/diagram/formula

    # 知识点
    skill_ids: list[str] = Field(default_factory=list)
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    difficulty_estimate: float = 0.5

    # 向量
    embedding: list[float] = Field(default_factory=list)

    # 来源
    source_file: str = ""
    page_number: Optional[int] = None
    chunk_index: int = 0

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    indexed_at: Optional[datetime] = None
    indexing_status: str = "pending"  # pending/processing/done/failed


class Material(BaseModel):
    """用户上传的一份完整资料"""
    material_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    file_name: str
    file_type: str
    file_size: int = 0

    # 状态
    status: str = "uploading"  # uploading/processing/ready/failed
    chunk_count: int = 0
    question_count: int = 0

    # 知识点覆盖
    skills_covered: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.now)
    indexed_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# 调度相关
# ──────────────────────────────────────────────

class ReviewTask(BaseModel):
    """复习任务"""
    type: str = "knowledge_review"  # knowledge_review/material_review/explanation_review
    skill_id: str = ""
    chunk_id: Optional[str] = None
    priority: float = 0.0
    next_review: datetime = Field(default_factory=datetime.now)
    instruction: str = ""


class PracticeSessionPlan(BaseModel):
    """练习会话规划"""
    skills: list[str] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    estimated_minutes: int = 30
    bloom_distribution: dict[BloomLevel, int] = Field(default_factory=dict)
    contrast_pairs: list[dict] = Field(default_factory=list)


class CoverageGap(BaseModel):
    """知识点覆盖缺口"""
    skill_id: str
    gap_type: str  # no_questions/insufficient_questions/missing_bloom_levels
    severity: str  # critical/warning/info
    suggestion: str = ""


# ──────────────────────────────────────────────
# 统计
# ──────────────────────────────────────────────

class SkillStat(BaseModel):
    """单个知识点的统计"""
    skill_id: str
    subject: str = ""
    total_attempts: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    p_known: float = 0.0
    mastery_level: str = "未接触"
    last_practiced: Optional[datetime] = None


class DailyStat(BaseModel):
    """每日统计"""
    date: str
    questions_done: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    study_minutes: float = 0.0
    new_skills_touched: int = 0


class BehaviorReport(BaseModel):
    """学习行为报告"""
    best_study_hours: list[int] = Field(default_factory=list)
    current_streak: int = 0
    regularity_score: float = 0.0
    fatigue_curve: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class PracticeStats(BaseModel):
    """练习统计汇总"""
    user_id: str
    total_questions: int = 0
    total_correct: int = 0
    accuracy: float = 0.0
    study_minutes: float = 0.0
    weak_skills: list[tuple[str, float]] = Field(default_factory=list)
    strong_skills: list[tuple[str, float]] = Field(default_factory=list)
    improvement: str = ""
    error_distribution: dict[ErrorType, int] = Field(default_factory=dict)
