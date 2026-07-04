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


# ──────────────────────────────────────────────
# 对话域事件 (Phase 5)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class AssistantReplied(DomainEvent):
    """AI 助手回复完成事件 — 触发多媒体生成 + 认知同步 + 知识证据 + 元历史"""
    user_id: str = ""
    dir_id: str = ""
    branch_id: str = ""
    conv_id: str = ""
    message_id: str = ""
    assistant_message_id: str = ""
    content: str = ""
    user_text: str = ""
    skill_ids: list[str] = field(default_factory=list)
    contains_math: bool = False

    @property
    def event_type(self) -> str:
        return "AssistantReplied"


# ──────────────────────────────────────────────
# v6 Phase 4: 业务域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class MessageClassified(DomainEvent):
    """消息分类确认事件 — 用户确认认知归属后发布"""
    user_id: str = ""
    message_id: str = ""
    conv_id: str = ""
    topic_node_ids: list[str] = field(default_factory=list)
    atom_node_ids: list[str] = field(default_factory=list)
    mode: str = "confirm"

    @property
    def event_type(self) -> str:
        return "MessageClassified"


@dataclass(frozen=True)
class PracticeSubmitted(DomainEvent):
    """练习提交事件 — 驱动掌握度更新"""
    user_id: str = ""
    atom_node_ids: list[str] = field(default_factory=list)
    correctness: float = 0.0
    latency_ms: float = 0.0

    @property
    def event_type(self) -> str:
        return "PracticeSubmitted"


@dataclass(frozen=True)
class NodeCreated(DomainEvent):
    """知识点创建事件 — 触发秘书波纹扩展"""
    user_id: str = ""
    node_id: str = ""
    parent_id: str = ""
    level: str = "atom"
    created_by: str = "user"

    @property
    def event_type(self) -> str:
        return "NodeCreated"


@dataclass(frozen=True)
class ProposalAccepted(DomainEvent):
    """秘书提案采纳事件 — 执行图谱操作"""
    user_id: str = ""
    proposal_id: str = ""
    action_type: str = ""
    target_node_id: str = ""

    @property
    def event_type(self) -> str:
        return "ProposalAccepted"


@dataclass(frozen=True)
class PendingCrossTopic(DomainEvent):
    """跨主题探索建议事件 — 深度沉浸中被抑制的候选

    由 classifier_service 在会话结束时通过 EventBus 发布，
    PersistentEventBus 持久化到 events 表，handler 消费并生成关联提案。
    """
    user_id: str = ""
    candidates: list[dict] = field(default_factory=list)
    suppressed_at_depth: int = 0

    @property
    def event_type(self) -> str:
        return "PendingCrossTopic"


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
# MoodStress 域事件 (Task #87)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class MoodStressRecorded(DomainEvent):
    """用户主动记录心情/压力/能量 — 手动优先"""
    user_id: str = ""
    id: str = ""
    emotion_tags: list[str] = field(default_factory=list)
    pressure_score: int = 0
    energy_score: int = 0
    text_note: str = ""
    related_event_ids: list[str] = field(default_factory=list)

    @property
    def event_type(self) -> str:
        return "MoodStressRecorded"


@dataclass(frozen=True)
class MoodStressInterventionTriggered(DomainEvent):
    """干预工具被使用 — 不修改学习数据"""
    user_id: str = ""
    id: str = ""
    intervention_type: str = ""
    duration_seconds: int = 0
    trigger_event: str = ""
    notes: str = ""

    @property
    def event_type(self) -> str:
        return "MoodStressInterventionTriggered"


@dataclass(frozen=True)
class MoodStressBehaviorSignalDetected(DomainEvent):
    """行为信号被检测 — 仅提示，不自动修改"""
    user_id: str = ""
    id: str = ""
    signal_type: str = ""
    signal_data: dict = field(default_factory=dict)
    severity: int = 1

    @property
    def event_type(self) -> str:
        return "MoodStressBehaviorSignalDetected"


@dataclass(frozen=True)
class MoodStressPrefsUpdated(DomainEvent):
    """心情压力偏好更新 — 增量覆盖"""
    user_id: str = ""
    changed_fields: list[str] = field(default_factory=list)

    @property
    def event_type(self) -> str:
        return "MoodStressPrefsUpdated"


# ──────────────────────────────────────────────
# 事件类型注册表（用于 event_bus 订阅路由）
# ──────────────────────────────────────────────

EVENT_TYPES: dict[str, type[DomainEvent]] = {
    cls().event_type: cls  # type: ignore[misc]
    for cls in [
        AnswerSubmitted,
        ErrorRecorded,
        SessionCompleted,
        AssistantReplied,
        CognitiveNodeUpdated,
        MessageClassified,
        PracticeSubmitted,
        NodeCreated,
        ProposalAccepted,
        PendingCrossTopic,
        MoodStressRecorded,
        MoodStressInterventionTriggered,
        MoodStressBehaviorSignalDetected,
        MoodStressPrefsUpdated,
    ]
}
