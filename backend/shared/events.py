"""
Phase 4: 领域事件定义

所有领域事件是不可变数据类，只定义数据不包含行为。
事件由 use_case 层发布，由 domain 层的异步 handler 消费。

依赖规则:
- 零外部依赖（只依赖 Python 标准库 + dataclasses）
- 不被任何业务模块反向依赖
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return str(uuid4())[:12]


@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类"""
    event_id: str = field(default_factory=_uid)
    occurred_at: datetime = field(default_factory=_now)


# ──────────────────────────────────────────────
# 练习域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class AnswerSubmitted(DomainEvent):
    """答题提交事件 — submit_answer 核心路径发布"""
    user_id: str = ""
    session_id: str = ""
    question_id: str = ""
    skill_id: str = ""
    is_correct: bool = False
    answer: str = ""
    correct_answer: str = ""
    time_spent: float = 0.0
    hints_used: int = 0
    p_known_before: float = 0.5
    p_known_after: float = 0.5

    @property
    def event_type(self) -> str:
        return "AnswerSubmitted"


@dataclass(frozen=True)
class ErrorRecorded(DomainEvent):
    """错题记录事件 — 答错时发布，驱动错题本 + 多媒体讲解"""
    user_id: str = ""
    question_id: str = ""
    skill_id: str = ""
    error_type: str = "careless"
    user_answer: str = ""
    correct_answer: str = ""

    @property
    def event_type(self) -> str:
        return "ErrorRecorded"


@dataclass(frozen=True)
class SessionCompleted(DomainEvent):
    """练习会话完成事件"""
    user_id: str = ""
    session_id: str = ""
    total_questions: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    duration_minutes: float = 0.0

    @property
    def event_type(self) -> str:
        return "SessionCompleted"


@dataclass(frozen=True)
class HintRequested(DomainEvent):
    """提示请求事件"""
    user_id: str = ""
    question_id: str = ""
    skill_id: str = ""
    hint_level: int = 1

    @property
    def event_type(self) -> str:
        return "HintRequested"


# ──────────────────────────────────────────────
# 知识域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class KnowledgeStateUpdated(DomainEvent):
    """知识状态变化事件 — BKT mastery 级别变化"""
    user_id: str = ""
    skill_id: str = ""
    old_mastery: str = "未接触"
    new_mastery: str = "未接触"
    p_known_before: float = 0.0
    p_known_after: float = 0.0
    attempt_count: int = 0

    @property
    def event_type(self) -> str:
        return "KnowledgeStateUpdated"


@dataclass(frozen=True)
class WeaknessDetected(DomainEvent):
    """薄弱点检测事件"""
    user_id: str = ""
    skill_id: str = ""
    error_count: int = 0
    last_error_type: str = ""

    @property
    def event_type(self) -> str:
        return "WeaknessDetected"


# ──────────────────────────────────────────────
# 规划域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class StudyPlanGenerated(DomainEvent):
    """学习计划生成事件"""
    user_id: str = ""
    plan_items: int = 0
    week_number: int = 0

    @property
    def event_type(self) -> str:
        return "StudyPlanGenerated"


@dataclass(frozen=True)
class DailyGoalAchieved(DomainEvent):
    """每日目标达成事件"""
    user_id: str = ""
    level: str = "basic"
    streak_days: int = 0
    questions_done: int = 0

    @property
    def event_type(self) -> str:
        return "DailyGoalAchieved"


# ──────────────────────────────────────────────
# 成就 + 资料域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class AchievementUnlocked(DomainEvent):
    """成就解锁事件"""
    user_id: str = ""
    achievement_id: str = ""
    name: str = ""
    level: int = 1

    @property
    def event_type(self) -> str:
        return "AchievementUnlocked"


@dataclass(frozen=True)
class MaterialIndexed(DomainEvent):
    """资料索引完成事件"""
    user_id: str = ""
    material_id: str = ""
    chunk_count: int = 0
    partition_id: str = ""

    @property
    def event_type(self) -> str:
        return "MaterialIndexed"


@dataclass(frozen=True)
class MaterialUploaded(DomainEvent):
    """资料上传事件"""
    user_id: str = ""
    material_id: str = ""
    file_name: str = ""
    file_size: int = 0
    partition_id: str = ""

    @property
    def event_type(self) -> str:
        return "MaterialUploaded"


# ──────────────────────────────────────────────
# 对话域事件 (Phase 5)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class AssistantReplied(DomainEvent):
    """AI 助手回复完成事件 — 触发多媒体生成"""
    user_id: str = ""
    partition_id: str = ""
    branch_id: str = ""
    conversation_id: str = ""
    message_id: str = ""
    content: str = ""
    skill_ids: list[str] = field(default_factory=list)
    contains_math: bool = False

    @property
    def event_type(self) -> str:
        return "AssistantReplied"


# ──────────────────────────────────────────────
# 多媒体域事件 (Phase 5)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class AudioSynthesized(DomainEvent):
    """TTS 音频合成完成事件"""
    user_id: str = ""
    skill_id: str = ""
    message_id: str = ""
    audio_url: str = ""
    duration_ms: int = 0
    format: str = "mp3"

    @property
    def event_type(self) -> str:
        return "AudioSynthesized"


@dataclass(frozen=True)
class ImageRendered(DomainEvent):
    """知识点配图渲染完成事件"""
    user_id: str = ""
    skill_id: str = ""
    message_id: str = ""
    image_url: str = ""
    image_type: str = "svg"  # svg | png
    prompt: str = ""

    @property
    def event_type(self) -> str:
        return "ImageRendered"


# ──────────────────────────────────────────────
# 认知域事件 (Phase 9)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class CognitiveNodeUpdated(DomainEvent):
    """CognitiveNode 更新事件 — 知识信念/掌握度变化后发布"""
    user_id: str = ""
    node_id: str = ""
    label: str = ""
    path_id: str = ""
    level: str = "atom"
    proficiency_before: float = 0.5
    proficiency_after: float = 0.5
    update_type: str = "practice"  # practice | secretary | auto_growth

    @property
    def event_type(self) -> str:
        return "CognitiveNodeUpdated"


# ──────────────────────────────────────────────
# 事件类型注册表（用于 event_bus 订阅路由）
# ──────────────────────────────────────────────

EVENT_TYPES: dict[str, type[DomainEvent]] = {
    cls().event_type: cls  # type: ignore[misc]
    for cls in [
        AnswerSubmitted,
        SessionCompleted,
        HintRequested,
        KnowledgeStateUpdated,
        WeaknessDetected,
        StudyPlanGenerated,
        DailyGoalAchieved,
        AchievementUnlocked,
        MaterialIndexed,
        MaterialUploaded,
        AssistantReplied,
        AudioSynthesized,
        ImageRendered,
        CognitiveNodeUpdated,
    ]
}
