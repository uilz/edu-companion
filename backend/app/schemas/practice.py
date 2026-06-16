"""
练习系统数据模型 v2.1 — 直接映射 DB 列名
v2.1 变更:
  - Question.question_id → id, 砍 skill_id/correct_answer/cognitive_skills/discrimination/guessing
  - PracticeSession.session_id → id, 砍 planned_skills/question_ids/attempts/frustration
  - AttemptRecord.attempt_id → id
  - 砍 KnowledgeState BKT 参数 (统一 CognitiveNode.Belief 为唯一权威源)
  - 保留枚举, 保留面向前端渲染的 DTO
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
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


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
    CREATED = "created"
    STARTED = "started"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class QuestionStatus(str, Enum):
    """题目状态"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    UNDER_REVIEW = "under_review"


# ──────────────────────────────────────────────
# 题目模型
# ──────────────────────────────────────────────

class QuestionOption(BaseModel):
    """选择题选项"""
    letter: str                     # A/B/C/D
    text: str
    is_correct: bool
    distractor_type: Optional[str] = None  # 干扰项类型（用于错因分析）


class ImageContent(BaseModel):
    """图片内容"""
    image_type: str = "diagram"
    svg_data: Optional[str] = None
    image_url: Optional[str] = None
    description: str = ""


class Question(BaseModel):
    """练习题 — 直接映射 DB questions 表"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bank_id: str = ""
    user_id: str = ""
    question_type: str = "single"           # single/multiple/judge/fill/free_form/calculation
    stem: str = ""
    options: list[QuestionOption] = Field(default_factory=list)  # JSONB
    answer: list[str] = Field(default_factory=list)              # JSONB — 从 options[].is_correct 推导
    explanation: str = ""                   # 解析
    hints: list[str] = Field(default_factory=list)               # JSONB
    difficulty: int = 3                     # 1~5 (DB: difficulty)
    source: str = "manual"                  # llm/manual/imported/material
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)       # JSONB
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    deleted_at: Optional[str] = None

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# 答题记录 + 错因分析
# ──────────────────────────────────────────────

class ErrorAnalysis(BaseModel):
    """错因分析"""
    error_type: ErrorType = ErrorType.CONCEPTUAL
    error_subtype: str = ""
    misconception: Optional[str] = None
    related_skills: list[str] = Field(default_factory=list)
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    suggestion: str = ""


class AttemptRecord(BaseModel):
    """单次答题记录 — 直接映射 DB practice_attempts 表"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    question_id: str = ""
    user_id: str = ""
    user_answer: list[str] = Field(default_factory=list)         # JSONB
    is_correct: bool = False
    time_spent_seconds: int = 0
    is_wrong: bool = False
    wrong_count: int = 0
    consecutive_correct: int = 0
    mastered: bool = False
    cognitive_node_ids: list[str] = Field(default_factory=list)  # 待迁移至 cognitive_links
    error_pattern: Optional[str] = None                          # 错因分类
    error_analysis: dict[str, Any] = Field(default_factory=dict) # JSONB (LLM 详细分析)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# 练习会话
# ──────────────────────────────────────────────

class PracticeSession(BaseModel):
    """一次练习会话 — 直接映射 DB practice_sessions 表"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    bank_id: Optional[str] = None
    session_type: str = "practice"
    mode: str = "adaptive"
    config: dict[str, Any] = Field(default_factory=dict)         # JSONB
    status: str = "created"
    total_count: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    score: Optional[float] = None
    cognitive_node_ids: list[str] = Field(default_factory=list)  # 待迁移至 cognitive_links
    conversation_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @property
    def accuracy(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.correct_count / self.total_count

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# 会话题目关联 (从 DB session_questions)
# ──────────────────────────────────────────────

class SessionQuestion(BaseModel):
    """会话题目关联 — 无状态, 仅排序"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    question_id: str = ""
    sort_order: int = 0
    question_type: str = ""
    bloom_level: str = ""
    difficulty: int = 3
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# 知识状态 (CognitiveNode.Belief DTO, 无 BKT)
# ──────────────────────────────────────────────

class KnowledgeState(BaseModel):
    """知识点掌握度 (从 CognitiveNode.Belief 读取, 仅 DTO)"""
    skill_id: str
    p_known: float = Field(default=0.0, ge=0.0, le=1.0)
    attempt_count: int = 0
    correct_count: int = 0
    last_updated: Optional[str] = None

    @property
    def accuracy(self) -> float:
        if self.attempt_count == 0:
            return 0.0
        return self.correct_count / self.attempt_count


# ──────────────────────────────────────────────
# 错题本
# ──────────────────────────────────────────────

class ErrorBookEntry(BaseModel):
    """错题本条目 — 从 practice_attempts 聚合"""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    question_id: str = ""
    error_type: str = ""
    misconception: Optional[str] = None
    user_answer: str = ""
    question_text: str = ""
    review_count: int = 0
    is_resolved: bool = False
    consecutive_correct: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ──────────────────────────────────────────────
# 统计模型
# ──────────────────────────────────────────────

class SkillStat(BaseModel):
    """单个知识点的统计"""
    skill_id: str
    subject: str = ""
    total_attempts: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    mastery_level: str = "未接触"
    last_practiced: Optional[str] = None


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
    user_id: str = ""
    total_questions: int = 0
    total_correct: int = 0
    accuracy: float = 0.0
    study_minutes: float = 0.0
    weak_skills: list[tuple[str, float]] = Field(default_factory=list)
    strong_skills: list[tuple[str, float]] = Field(default_factory=list)
    improvement: str = ""
    error_distribution: dict[str, int] = Field(default_factory=dict)
