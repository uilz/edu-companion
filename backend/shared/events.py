"""
领域事件定义 — 所有模块通过事件通信

设计原则:
- 事件是不可变的 (frozen dataclass)
- 每个事件有唯一 event_id + 时间戳
- 事件是事实陈述，不是命令
- 消费者自行决定如何响应
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


# ═══════════════════════════════════════════════════════════
# 事件基类
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类 — 所有事件继承自此"""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def event_type(self) -> str:
        return type(self).__name__

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于跨进程传输）"""
        import dataclasses
        d = dataclasses.asdict(self)
        d["event_type"] = self.event_type
        d["event_version"] = 1
        if isinstance(d.get("occurred_at"), datetime):
            d["occurred_at"] = d["occurred_at"].isoformat()
        return d


# ═══════════════════════════════════════════════════════════
# 练习域事件
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AnswerSubmitted(DomainEvent):
    """答题提交 — 练习系统最重要的领域事件"""
    user_id: str = ""
    session_id: str = ""
    question_id: str = ""
    skill_id: str = ""
    is_correct: bool = False
    answer: str = ""
    correct_answer: str = ""
    time_spent: float = 0.0
    hints_used: int = 0
    p_known_before: float = 0.0
    p_known_after: float = 0.0


@dataclass(frozen=True)
class SessionStarted(DomainEvent):
    """练习会话开始"""
    user_id: str = ""
    session_id: str = ""
    question_count: int = 0
    mode: str = "adaptive"


@dataclass(frozen=True)
class SessionCompleted(DomainEvent):
    """练习会话完成"""
    user_id: str = ""
    session_id: str = ""
    total_questions: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    duration_minutes: float = 0.0
    skills_practiced: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ErrorRecorded(DomainEvent):
    """错题记录 — 触发错题本更新"""
    user_id: str = ""
    question_id: str = ""
    skill_id: str = ""
    error_type: str = "careless"
    user_answer: str = ""
    correct_answer: str = ""


# ═══════════════════════════════════════════════════════════
# 知识域事件
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class KnowledgeStateUpdated(DomainEvent):
    """知识状态变化 — 可能触发计划重调、图谱更新"""
    user_id: str = ""
    skill_id: str = ""
    old_mastery: str = "未接触"       # 未接触/初学/发展中/接近掌握/已掌握
    new_mastery: str = "未接触"
    p_known_before: float = 0.0
    p_known_after: float = 0.0
    attempt_count: int = 0


@dataclass(frozen=True)
class PseudoMasteryDetected(DomainEvent):
    """伪掌握检测 — 答对但解释不出来"""
    user_id: str = ""
    skill_id: str = ""


# ═══════════════════════════════════════════════════════════
# 规划域事件
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StudyPlanGenerated(DomainEvent):
    """学习计划生成/更新"""
    user_id: str = ""
    plan_items: int = 0
    week_number: int = 0
    skills_covered: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DailyGoalAchieved(DomainEvent):
    """每日目标达成"""
    user_id: str = ""
    level: str = "beginner"           # beginner/regular/intensive
    streak_days: int = 0
    questions_done: int = 0


# ═══════════════════════════════════════════════════════════
# 资料域事件
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MaterialUploaded(DomainEvent):
    """资料上传完成"""
    user_id: str = ""
    material_id: str = ""
    file_name: str = ""
    file_type: str = ""
    file_size: int = 0


@dataclass(frozen=True)
class MaterialIndexed(DomainEvent):
    """资料索引完成 — 触发后续出题"""
    user_id: str = ""
    material_id: str = ""
    chunk_count: int = 0
    skills_covered: list[str] = field(default_factory=list)
