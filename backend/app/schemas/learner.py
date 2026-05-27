"""
学习者相关的Pydantic数据模型
定义学习者画像、知识状态、学习记录等数据结构
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 枚举定义
# ──────────────────────────────────────────────
class IntentType(str, Enum):
    """学习意图类型"""
    QUESTION = "question"           # 提问
    EXPLAIN = "explain"             # 请求解释
    PRACTICE = "practice"           # 想要练习
    REVIEW = "review"               # 复习
    ENCOURAGEMENT = "encouragement" # 寻求鼓励
    FRUSTRATION = "frustration"     # 挫败感/抱怨
    CHITCHAT = "chitchat"           # 闲聊
    NEGOTIATE = "negotiate"         # 提案协商（\"改成明天行吗？\"）
    UNKNOWN = "unknown"


class EmotionType(str, Enum):
    """情绪类型"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    TIRED = "tired"
    CONFIDENT = "confident"


class LearningStyle(str, Enum):
    """学习风格"""
    VISUAL = "visual"           # 视觉型
    AUDITORY = "auditory"       # 听觉型
    READING = "reading"         # 阅读型
    KINESTHETIC = "kinesthetic" # 动手型


# ──────────────────────────────────────────────
# 知识点状态
# ──────────────────────────────────────────────
from app.schemas.practice import KnowledgeState

# 知识点状态（统一使用 practice.py 的多维版 KnowledgeState）
# 此 re-export 保持向后兼容，消除 duplicate schema 问题


# ──────────────────────────────────────────────
# 学习者画像
# ──────────────────────────────────────────────
class LearnerProfile(BaseModel):
    """学习者数字孪生画像"""
    user_id: str
    nickname: Optional[str] = None
    subjects: list[str] = Field(default_factory=list)
    grade_level: Optional[int] = Field(default=None, ge=1, le=12)
    learning_style: LearningStyle = LearningStyle.READING
    knowledge_states: dict[str, KnowledgeState] = Field(default_factory=dict)
    total_study_minutes: float = 0.0
    streak_days: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    preferences: dict[str, Any] = Field(default_factory=dict)

    def get_knowledge_state(self, skill_id: str) -> KnowledgeState:
        """获取指定知识点的状态，不存在则创建默认状态"""
        if skill_id not in self.knowledge_states:
            self.knowledge_states[skill_id] = KnowledgeState(skill_id=skill_id)
        return self.knowledge_states[skill_id]


# ──────────────────────────────────────────────
# 学习计划
# ──────────────────────────────────────────────
class StudyPlanItem(BaseModel):
    """学习计划中的单个任务"""
    task_id: str
    title: str
    description: str
    subject: str
    skill_ids: list[str] = Field(default_factory=list)
    estimated_minutes: int = 30
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    priority: int = Field(default=5, ge=1, le=10)
    completed: bool = False
    due_date: Optional[datetime] = None


class StudyPlan(BaseModel):
    """完整的学习计划"""
    user_id: str
    items: list[StudyPlanItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    week_number: int = 0


# ──────────────────────────────────────────────
# 练习题模型
# ──────────────────────────────────────────────
class Difficulty(str, Enum):
    """难度等级"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class PracticeQuestion(BaseModel):
    """练习题"""
    question_id: str
    subject: str
    skill_id: str
    difficulty: Difficulty = Difficulty.MEDIUM
    question_text: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    explanation: str = ""
    hints: list[str] = Field(default_factory=list)


class PracticeResult(BaseModel):
    """练习结果"""
    question_id: str
    user_answer: str
    is_correct: bool
    time_spent_seconds: float = 0.0
    knowledge_update: Optional[dict[str, Any]] = None


# ──────────────────────────────────────────────
# 进度统计
# ──────────────────────────────────────────────
class ProgressSummary(BaseModel):
    """学习进度摘要"""
    user_id: str
    total_questions: int = 0
    correct_answers: int = 0
    accuracy_rate: float = 0.0
    study_minutes: float = 0.0
    mastered_skills: list[str] = Field(default_factory=list)
    struggling_skills: list[str] = Field(default_factory=list)
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ContentItem(BaseModel):
    """内容搜索结果"""
    content_id: str
    title: str
    subject: str
    content_type: str  # "video" | "article" | "exercise" | "quiz"
    description: str = ""
    url: Optional[str] = None
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
