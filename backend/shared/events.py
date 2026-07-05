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
from enum import Enum
from typing import Any, Literal
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
    record_id: str = ""
    source: str = "manual"
    emotion_tags: list[str] = field(default_factory=list)
    pressure_score: int = 0
    energy_score: int = 0
    text_note: str = ""
    related_event_ids: list[str] = field(default_factory=list)
    recorded_at: datetime | None = None

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


@dataclass(frozen=True)
class MoodStressRuleTriggered(DomainEvent):
    """心情压力规则被触发 — 由规则引擎发布, planning/cockpit 订阅"""
    user_id: str = ""
    rule_id: str = ""
    trigger_metric: str = ""
    trigger_value: float = 0.0
    action: str = ""
    triggered_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "MoodStressRuleTriggered"


# ──────────────────────────────────────────────
# 跨模块路由枚举 (CrossModuleTarget)
# ──────────────────────────────────────────────


class CrossModuleTarget(str, Enum):
    """跨模块跳转 / 联动目标模块。

    供 reading/interest/secretary 等模块用统一字符串路由
    到 reading/project/flashcard/cognitive_node/languageroom。
    """
    READING = "reading"
    PROJECT = "project"
    FLASHCARD = "flashcard"
    COGNITIVE_NODE = "cognitive_node"
    LANGUAGE_ROOM = "language_room"
    PLAN = "plan"
    MATERIAL = "material"
    CONVERSATION = "conversation"


# ──────────────────────────────────────────────
# FlashCard / 错题本 域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class FlashCardReviewed(DomainEvent):
    """闪卡复习自评结果 — 驱动 Belief 回写 + 错题本同步"""
    user_id: str = ""
    card_id: str = ""
    session_id: str = ""
    self_assessment: str = "good"  # difficult | good | easy
    stability_before: float = 0.0
    stability_after: float = 0.0
    difficulty_before: float = 0.0
    difficulty_after: float = 0.0
    interval_before: int = 0
    interval_after: int = 0
    elapsed_days: int = 0
    next_review_at: datetime | None = None
    linked_node_ids: list[str] = field(default_factory=list)
    node_link_roles: dict[str, str] = field(default_factory=dict)
    source: str = ""
    error_book_entry_id: str = ""
    reviewed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardReviewed"


@dataclass(frozen=True)
class ErrorBookEntryReviewed(DomainEvent):
    """错题本条目被复习 (review_count 增量)"""
    user_id: str = ""
    error_entry_id: str = ""
    self_assessment: str = "good"
    review_count: int = 0
    is_resolved: bool = False

    @property
    def event_type(self) -> str:
        return "ErrorBookEntryReviewed"


@dataclass(frozen=True)
class ErrorBookEntryResolved(DomainEvent):
    """错题本条目被标记为已解决 (is_resolved = true)"""
    user_id: str = ""
    error_entry_id: str = ""
    resolution_method: str = "auto_after_review"

    @property
    def event_type(self) -> str:
        return "ErrorBookEntryResolved"


@dataclass(frozen=True)
class CognitiveNodeLinked(DomainEvent):
    """认知节点被关联 / 引用变化 — FlashCard 复习后经此通知知识图谱"""
    user_id: str = ""
    node_id: str = ""
    link_type: str = "flashcard_review"
    target_ref_type: str = "flashcard"
    target_ref_id: str = ""
    action: str = "updated"

    @property
    def event_type(self) -> str:
        return "CognitiveNodeLinked"


@dataclass(frozen=True)
class CognitiveNodeMetadataChanged(DomainEvent):
    """认知节点的元数据 (label/brief/description) 变更 — 不影响 Belief"""
    user_id: str = ""
    node_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    changed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "CognitiveNodeMetadataChanged"


# ──────────────────────────────────────────────
# Reading 域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ReadingSessionStarted(DomainEvent):
    """阅读会话开始"""
    user_id: str = ""
    session_id: str = ""
    material_id: str = ""
    mode: str = "intensive"
    started_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingSessionStarted"


@dataclass(frozen=True)
class ReadingSessionEnded(DomainEvent):
    """阅读会话结束 — 触发回看 / 知识沉淀"""
    user_id: str = ""
    session_id: str = ""
    material_id: str = ""
    duration_seconds: float = 0.0
    annotations_count: int = 0
    notes_count: int = 0
    cards_generated: int = 0
    linked_node_ids: list[str] = field(default_factory=list)
    ended_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingSessionEnded"


@dataclass(frozen=True)
class ReadingModeChanged(DomainEvent):
    """阅读模式切换 (精读/略读/回顾)"""
    user_id: str = ""
    session_id: str = ""
    old_mode: str = "intensive"
    new_mode: str = "intensive"
    changed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingModeChanged"


@dataclass(frozen=True)
class ReadingSessionResumed(DomainEvent):
    """阅读会话从中断恢复"""
    user_id: str = ""
    session_id: str = ""
    last_chunk_id: str = ""
    resumed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingSessionResumed"


@dataclass(frozen=True)
class ReadingAnnotationCreated(DomainEvent):
    """阅读标注被创建"""
    user_id: str = ""
    annotation_id: str = ""
    material_id: str = ""
    chunk_id: str = ""
    color: str = "yellow"
    intent: str = "highlight"
    linked_node_id: str = ""
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationCreated"


@dataclass(frozen=True)
class ReadingAnnotationUpdated(DomainEvent):
    """阅读标注被更新"""
    user_id: str = ""
    annotation_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    updated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationUpdated"


@dataclass(frozen=True)
class ReadingAnnotationDeleted(DomainEvent):
    """阅读标注被删除"""
    user_id: str = ""
    annotation_id: str = ""
    deleted_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationDeleted"


@dataclass(frozen=True)
class ReadingAnnotationProcessed(DomainEvent):
    """阅读标注被处理 (联动到目标模块)"""
    user_id: str = ""
    annotation_id: str = ""
    target_module: str = ""
    target_ref_id: str = ""
    processed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationProcessed"


@dataclass(frozen=True)
class ReadingNoteCreated(DomainEvent):
    """阅读笔记被创建 (含卡生成)"""
    user_id: str = ""
    material_id: str = ""
    card_id: str = ""
    source: str = "reading_note"
    cross_module_source: str = "reading"
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ReadingNoteCreated"


@dataclass(frozen=True)
class ReadingReviewReminderScheduled(DomainEvent):
    """阅读回顾提醒已调度 (业务审计事件, 7/30/90 天后)"""
    user_id: str = ""
    material_id: str = ""
    reminder_days: int = 7
    scheduled_for: datetime | None = None
    plan_item_id: str = ""

    @property
    def event_type(self) -> str:
        return "ReadingReviewReminderScheduled"


# ──────────────────────────────────────────────
# Planning 域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class PlanItemScheduled(DomainEvent):
    """计划项已调度 (跨模块复用, source_module 标识来源)"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""
    scheduled_for: datetime | None = None
    plan_date: str = ""
    is_mood_rule_affected: bool = False
    scheduled_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanItemScheduled"


# ──────────────────────────────────────────────
# Interest 域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class InterestSourceFetched(DomainEvent):
    """兴趣源拉取完成 (arXiv / RSS / bioRxiv)"""
    user_id: str = ""
    source_id: str = ""
    source_type: str = ""
    fetched_count: int = 0
    new_count: int = 0
    fetched_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestSourceFetched"


@dataclass(frozen=True)
class InterestPushGenerated(DomainEvent):
    """兴趣推送生成 (research_object / research_method / hot_news)"""
    user_id: str = ""
    push_id: str = ""
    push_type: str = ""
    title: str = ""
    url: str = ""
    source_id: str = ""
    source_name: str = ""
    matched_tags: list[str] = field(default_factory=list)
    summary_preview: str = ""

    @property
    def event_type(self) -> str:
        return "InterestPushGenerated"


@dataclass(frozen=True)
class InterestPrefsUpdated(DomainEvent):
    """兴趣偏好更新 (用户改了订阅/标签)"""
    user_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    is_enabled: bool = True

    @property
    def event_type(self) -> str:
        return "InterestPrefsUpdated"


@dataclass(frozen=True)
class InterestContentImported(DomainEvent):
    """兴趣内容被导入到目标模块 (reading/project/flashcard/cognitive_node/languageroom)"""
    user_id: str = ""
    push_id: str = ""
    target_module: str = ""
    target_ref_id: str = ""

    @property
    def event_type(self) -> str:
        return "InterestContentImported"


# ──────────────────────────────────────────────
# FlashCard API 层事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class FlashCardCreated(DomainEvent):
    """闪卡被创建"""
    user_id: str = ""
    card_id: str = ""
    type: int = 1
    source: str = "manual"
    cross_module_source: str = ""
    linked_node_ids: list[str] = field(default_factory=list)
    source_ref: str = ""
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardCreated"


@dataclass(frozen=True)
class FlashCardUpdated(DomainEvent):
    """闪卡内容被更新"""
    user_id: str = ""
    card_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    reset_scheduling: bool = False
    updated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardUpdated"


@dataclass(frozen=True)
class FlashCardStatusChanged(DomainEvent):
    """闪卡状态切换 (active/suspended/archived/deleted)"""
    user_id: str = ""
    card_id: str = ""
    old_status: str = ""
    new_status: str = ""
    changed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardStatusChanged"


@dataclass(frozen=True)
class FlashCardSuspended(DomainEvent):
    """闪卡被暂停"""
    user_id: str = ""
    card_id: str = ""
    suspended_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardSuspended"


@dataclass(frozen=True)
class FlashCardResumed(DomainEvent):
    """闪卡被恢复"""
    user_id: str = ""
    card_id: str = ""
    resumed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardResumed"


@dataclass(frozen=True)
class FlashCardReset(DomainEvent):
    """闪卡复习计划被重置"""
    user_id: str = ""
    card_id: str = ""
    reset_at: datetime | None = None
    previous_review_count: int = 0

    @property
    def event_type(self) -> str:
        return "FlashCardReset"


@dataclass(frozen=True)
class FlashCardArchived(DomainEvent):
    """闪卡被归档"""
    user_id: str = ""
    card_id: str = ""
    archived_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardArchived"


@dataclass(frozen=True)
class FlashCardDeleted(DomainEvent):
    """闪卡被删除"""
    user_id: str = ""
    card_id: str = ""
    deleted_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardDeleted"


@dataclass(frozen=True)
class FlashCardSessionStarted(DomainEvent):
    """闪卡复习会话开始"""
    user_id: str = ""
    session_id: str = ""
    source_module: str = ""
    initial_card_count: int = 0
    started_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardSessionStarted"


@dataclass(frozen=True)
class FlashCardSessionEnded(DomainEvent):
    """闪卡复习会话结束"""
    user_id: str = ""
    session_id: str = ""
    total_cards: int = 0
    difficult_count: int = 0
    good_count: int = 0
    easy_count: int = 0
    duration_seconds: int = 0
    ended_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "FlashCardSessionEnded"


# ──────────────────────────────────────────────
# Interest API 层事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class InterestTagCreated(DomainEvent):
    """兴趣标签被创建"""
    user_id: str = ""
    tag_id: str = ""
    name: str = ""
    level: int = 0
    parent_id: str = ""
    weight: float = 1.0
    source: str = "manual"
    cross_module_source: str = ""
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestTagCreated"


@dataclass(frozen=True)
class InterestTagUpdated(DomainEvent):
    """兴趣标签被更新"""
    user_id: str = ""
    tag_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    updated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestTagUpdated"


@dataclass(frozen=True)
class InterestTagDeleted(DomainEvent):
    """兴趣标签被删除"""
    user_id: str = ""
    tag_id: str = ""
    deleted_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestTagDeleted"


@dataclass(frozen=True)
class InterestTagFromKnowledgeCreated(DomainEvent):
    """从知识点派生的兴趣标签被创建"""
    user_id: str = ""
    tag_id: str = ""
    knowledge_node_id: str = ""
    tag_name: str = ""
    level: int = 0
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestTagFromKnowledgeCreated"


@dataclass(frozen=True)
class InterestSourceEnabled(DomainEvent):
    """兴趣源被启用"""
    user_id: str = ""
    source_id: str = ""
    name: str = ""
    type: str = ""
    enabled_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestSourceEnabled"


@dataclass(frozen=True)
class InterestSourceDisabled(DomainEvent):
    """兴趣源被禁用"""
    user_id: str = ""
    source_id: str = ""
    name: str = ""
    disabled_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestSourceDisabled"


@dataclass(frozen=True)
class InterestPushFeedbackRecorded(DomainEvent):
    """用户对兴趣推送的反馈 (like/dislike/hide)"""
    user_id: str = ""
    push_id: str = ""
    feedback: str = ""

    @property
    def event_type(self) -> str:
        return "InterestPushFeedbackRecorded"


@dataclass(frozen=True)
class InterestLocalWeightAdjusted(DomainEvent):
    """用户对某标签的本地权重做了手动调整"""
    user_id: str = ""
    tag_id: str = ""
    old_weight: float = 1.0
    new_weight: float = 1.0
    adjusted_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "InterestLocalWeightAdjusted"


# ──────────────────────────────────────────────
# Planning API 层事件
# ──────────────────────────────────────────────


class PlanningSourceModule(str, Enum):
    """计划项的来源模块 (与 CrossModuleTarget 部分重叠, 但语义面向 Planning)"""
    MANUAL = "manual"
    PRACTICE = "practice"
    FLASHCARD = "flashcard"
    READING = "reading"
    PROJECT = "project"
    INTEREST = "interest"
    INTEREST_EXPLORER = "interest_explorer"
    LANGUAGE_ROOM = "language_room"
    MOOD_STRESS = "mood_stress"
    SECRETARY = "secretary"
    SYSTEM = "system"


@dataclass(frozen=True)
class PlanItemCreated(DomainEvent):
    """计划项被创建"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""
    target_type: str = ""
    target_ref_id: str = ""
    title: str = ""
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanItemCreated"


@dataclass(frozen=True)
class PlanItemCompleted(DomainEvent):
    """计划项被标记为完成"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""
    target_type: str = ""
    target_ref_id: str = ""
    actual_minutes: int = 0
    linked_node_ids: list[str] = field(default_factory=list)
    completed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanItemCompleted"


@dataclass(frozen=True)
class PlanItemActivated(DomainEvent):
    """计划项被激活 (从 scheduled 进入可执行状态)"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""
    target_type: str = ""
    target_ref_id: str = ""
    activated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanItemActivated"


@dataclass(frozen=True)
class PlanDeviationRecorded(DomainEvent):
    """计划偏差被记录 (timeout/skip/early_complete/extra_insert)"""
    user_id: str = ""
    plan_item_id: str = ""
    deviation_type: Literal["timeout", "skip", "early_complete", "extra_insert"] = "skip"
    planned_minutes: int = 0
    actual_minutes: int = 0
    deviation_minutes: int = 0
    recorded_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanDeviationRecorded"


@dataclass(frozen=True)
class PlanGoalCreated(DomainEvent):
    """计划目标被创建"""
    user_id: str = ""
    goal_id: str = ""
    title: str = ""
    target_module: str = ""
    target_metric: str = ""
    target_value: int = 0
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanGoalCreated"


@dataclass(frozen=True)
class PlanGoalProgressUpdated(DomainEvent):
    """计划目标进度更新"""
    user_id: str = ""
    goal_id: str = ""
    current_value: int = 0
    target_value: int = 0
    progress_pct: float = 0.0
    updated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanGoalProgressUpdated"


@dataclass(frozen=True)
class PlanGoalCompleted(DomainEvent):
    """计划目标完成"""
    user_id: str = ""
    goal_id: str = ""
    completed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanGoalCompleted"


@dataclass(frozen=True)
class PlanPeriodicReviewGenerated(DomainEvent):
    """周期回顾生成 (weekly/monthly)"""
    user_id: str = ""
    review_id: str = ""
    period_type: str = "weekly"
    period_start: datetime | None = None
    period_end: datetime | None = None
    generated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanPeriodicReviewGenerated"


@dataclass(frozen=True)
class PlanItemStarted(DomainEvent):
    """计划项被开始 (用户进入任务)"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""
    started_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanItemStarted"


@dataclass(frozen=True)
class PlanItemSkipped(DomainEvent):
    """计划项被跳过"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""
    skipped_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanItemSkipped"


@dataclass(frozen=True)
class PlanItemExtended(DomainEvent):
    """计划项预计时长被延长"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""
    extended_minutes: int = 0
    extended_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanItemExtended"


@dataclass(frozen=True)
class PlanGoalCreated(DomainEvent):
    """学习目标被创建"""
    user_id: str = ""
    goal_id: str = ""
    title: str = ""
    target_module: str = ""
    target_metric: str = ""
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanGoalCreated"


@dataclass(frozen=True)
class PlanPeriodicReviewGenerated(DomainEvent):
    """周期性复习 (周/月) 已生成"""
    user_id: str = ""
    review_id: str = ""
    period_type: str = "weekly"
    period_start: str = ""
    period_end: str = ""
    generated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "PlanPeriodicReviewGenerated"


# ──────────────────────────────────────────────
# Project API 层事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ProjectCreated(DomainEvent):
    """项目被创建"""
    project_id: str = ""
    user_id: str = ""
    name: str = ""
    template_id: str = ""
    template_version: int = 0
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectCreated"


@dataclass(frozen=True)
class ProjectNodeCreated(DomainEvent):
    """项目节点被创建"""
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    parent_id: str = ""
    type: str = ""
    title: str = ""
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectNodeCreated"


@dataclass(frozen=True)
class ProjectNodeUpdated(DomainEvent):
    """项目节点被更新"""
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    version: int = 1
    changed_fields: list[str] = field(default_factory=list)
    updated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectNodeUpdated"


@dataclass(frozen=True)
class ProjectNodeVersionCreated(DomainEvent):
    """项目节点新版本被创建 (可作为回滚点)"""
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    version_number: int = 0
    is_rollback: bool = False
    rolled_back_from_version: int = 0
    change_source: str = "manual"
    changed_fields: list[str] = field(default_factory=list)
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectNodeVersionCreated"


@dataclass(frozen=True)
class ProjectNodeRolledBack(DomainEvent):
    """项目节点被回滚到旧版本"""
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    from_version: int = 0
    to_version: int = 0
    rolled_back_fields: list[str] = field(default_factory=list)
    rolled_back_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectNodeRolledBack"


@dataclass(frozen=True)
class ProjectNodeCompleted(DomainEvent):
    """项目节点被标记为完成"""
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    completion_method: str = "manual"
    linked_node_ids: list[str] = field(default_factory=list)
    completed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectNodeCompleted"


@dataclass(frozen=True)
class ProjectNodeExported(DomainEvent):
    """项目节点被导出 (到 reading/flashcard/cognitive 等)"""
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    target_module: str = ""
    target_ref_id: str = ""
    export_data: dict[str, Any] = field(default_factory=dict)
    exported_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectNodeExported"


@dataclass(frozen=True)
class ProjectMilestoneMarked(DomainEvent):
    """项目里程碑被标记"""
    project_id: str = ""
    user_id: str = ""
    milestone_id: str = ""
    milestone_name: str = ""
    title: str = ""
    snapshot_data: dict[str, Any] = field(default_factory=dict)
    is_user_marked: bool = False
    marked_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "ProjectMilestoneMarked"


# ──────────────────────────────────────────────
# LiveRoom (LanguageRoom) API 层事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class LanguageRoomCreated(DomainEvent):
    """语言房间被创建"""
    user_id: str = ""
    room_id: str = ""
    scenario_id: str = ""
    max_participants: int = 2
    is_recording_enabled: bool = False
    created_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomCreated"


@dataclass(frozen=True)
class LanguageRoomStarted(DomainEvent):
    """语言房间已开始 (第一位参与者进入)"""
    user_id: str = ""
    room_id: str = ""
    started_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomStarted"


@dataclass(frozen=True)
class LanguageRoomEnded(DomainEvent):
    """语言房间已结束"""
    user_id: str = ""
    room_id: str = ""
    duration_seconds: float = 0.0
    ended_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomEnded"


@dataclass(frozen=True)
class LanguageRoomCompleted(DomainEvent):
    """参与者维度: 用户的房间体验完成 (用于生成回看/笔记)"""
    user_id: str = ""
    room_id: str = ""
    session_id: str = ""
    scenario_id: str = ""
    duration_seconds: float = 0.0
    transcript_segments: list[dict] = field(default_factory=list)
    completed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomCompleted"


@dataclass(frozen=True)
class LanguageRoomParticipantJoined(DomainEvent):
    """参与者加入房间"""
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    participant_type: str = "human"
    joined_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomParticipantJoined"


@dataclass(frozen=True)
class LanguageRoomParticipantLeft(DomainEvent):
    """参与者离开房间"""
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    speaking_time_seconds: float = 0.0
    left_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomParticipantLeft"


@dataclass(frozen=True)
class LanguageRoomScenarioChanged(DomainEvent):
    """房间情景被切换"""
    user_id: str = ""
    room_id: str = ""
    old_scenario_id: str = ""
    new_scenario_id: str = ""
    changed_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomScenarioChanged"


@dataclass(frozen=True)
class LanguageRoomTranscriptSegmentAdded(DomainEvent):
    """实时转写片段被添加"""
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    segment_index: int = 0
    speaker_id: str = ""
    text: str = ""
    language: str = "zh"
    confidence: float = 0.0
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomTranscriptSegmentAdded"


@dataclass(frozen=True)
class LanguageRoomRecordingStarted(DomainEvent):
    """房间录音开始"""
    user_id: str = ""
    room_id: str = ""
    recording_id: str = ""
    started_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomRecordingStarted"


@dataclass(frozen=True)
class LanguageRoomRecordingStopped(DomainEvent):
    """房间录音停止"""
    user_id: str = ""
    room_id: str = ""
    recording_id: str = ""
    duration_seconds: float = 0.0
    stopped_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomRecordingStopped"


@dataclass(frozen=True)
class LanguageRoomAIPersonaJoined(DomainEvent):
    """AI 角色加入房间"""
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    persona_id: str = ""
    role_label: str = ""
    joined_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomAIPersonaJoined"


@dataclass(frozen=True)
class LanguageRoomAIPersonaLeft(DomainEvent):
    """AI 角色离开房间"""
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    left_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomAIPersonaLeft"


@dataclass(frozen=True)
class LanguageRoomAIHelperInvoked(DomainEvent):
    """AI 辅助被调用 (grammar / vocabulary / sentence_pattern)"""
    user_id: str = ""
    room_id: str = ""
    helper_type: str = ""
    query: str = ""
    response: str = ""
    invoked_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomAIHelperInvoked"


@dataclass(frozen=True)
class LanguageRoomVocabularyCaptured(DomainEvent):
    """用户捕获生词 (写入 FlashCard, source=language_room)"""
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    card_id: str = ""
    word: str = ""
    translation: str = ""
    captured_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomVocabularyCaptured"


@dataclass(frozen=True)
class LanguageRoomErrorMarked(DomainEvent):
    """用户在转写片段上标记错误 (写入 ErrorBookEntry)"""
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    error_entry_id: str = ""
    error_type: str = "grammar"
    linked_node_ids: list[str] = field(default_factory=list)
    marked_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomErrorMarked"


@dataclass(frozen=True)
class LanguageRoomMessagePosted(DomainEvent):
    """AI 辅助消息发出 (ExplainCard 浮卡)"""
    user_id: str = ""
    room_id: str = ""
    message_id: str = ""
    text: str = ""
    message_type: str = "text"
    posted_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "LanguageRoomMessagePosted"


# ──────────────────────────────────────────────
# System / Secretary 域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class UserPreferencesUpdated(DomainEvent):
    """用户偏好设置被更新 (秘书 agent / 路由等)"""
    user_id: str = ""
    changed_keys: list[str] = field(default_factory=list)
    changed_fields: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def event_type(self) -> str:
        return "UserPreferencesUpdated"


@dataclass(frozen=True)
class UserProfileUpdated(DomainEvent):
    """用户资料 (display_name/email/password) 变更 — 鉴权域"""
    user_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    change_type: str = "profile_update"  # profile_update | password_change | logout_others | deactivate
    updated_at: datetime | None = None

    @property
    def event_type(self) -> str:
        return "UserProfileUpdated"


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
        # Reading
        ReadingSessionStarted,
        ReadingSessionEnded,
        ReadingModeChanged,
        ReadingSessionResumed,
        ReadingAnnotationCreated,
        ReadingAnnotationUpdated,
        ReadingAnnotationDeleted,
        ReadingAnnotationProcessed,
        ReadingNoteCreated,
        ReadingReviewReminderScheduled,
        # FlashCard / 错题本 / 认知
        FlashCardReviewed,
        ErrorBookEntryReviewed,
        ErrorBookEntryResolved,
        CognitiveNodeLinked,
        # Planning
        PlanItemScheduled,
        # Interest
        InterestSourceFetched,
        InterestPushGenerated,
        InterestPrefsUpdated,
        InterestContentImported,
        # FlashCard API
        FlashCardCreated,
        FlashCardUpdated,
        FlashCardStatusChanged,
        FlashCardSuspended,
        FlashCardResumed,
        FlashCardReset,
        FlashCardArchived,
        FlashCardDeleted,
        FlashCardSessionStarted,
        FlashCardSessionEnded,
        # Interest API
        InterestTagCreated,
        InterestTagUpdated,
        InterestTagDeleted,
        InterestTagFromKnowledgeCreated,
        InterestSourceEnabled,
        InterestSourceDisabled,
        InterestPushFeedbackRecorded,
        InterestLocalWeightAdjusted,
        # Planning API
        PlanItemCreated,
        PlanItemCompleted,
        PlanItemStarted,
        PlanItemSkipped,
        PlanItemExtended,
        PlanGoalCreated,
        PlanPeriodicReviewGenerated,
        # Project API
        ProjectCreated,
        ProjectNodeCreated,
        ProjectNodeUpdated,
        ProjectNodeVersionCreated,
        ProjectNodeRolledBack,
        ProjectNodeCompleted,
        ProjectNodeExported,
        ProjectMilestoneMarked,
        # LiveRoom (LanguageRoom) API
        LanguageRoomCreated,
        LanguageRoomStarted,
        LanguageRoomEnded,
        LanguageRoomCompleted,
        LanguageRoomParticipantJoined,
        LanguageRoomParticipantLeft,
        LanguageRoomScenarioChanged,
        LanguageRoomTranscriptSegmentAdded,
        LanguageRoomRecordingStarted,
        LanguageRoomRecordingStopped,
        # System / Secretary
        UserPreferencesUpdated,
    ]
}
