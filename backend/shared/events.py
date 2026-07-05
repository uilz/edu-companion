"""
Phase 4: 领域事件定义

所有领域事件是不可变数据类，只定义数据不包含行为。
事件由 use_case 层发布，由 domain 层的异步 handler 消费。

依赖规则:
- 零外部依赖（只依赖 Python 标准库 + dataclasses）
- 不被任何业务模块反向依赖

时间字段命名约定：
- at: datetime            → 动作时刻（如 created_at, completed_at, scheduled_for）
- date: date              → 日历日（如 plan_date, deadline, period_start）
- duration_seconds: float → 时长（如 session duration, time spent）
混用必须显式区分语义
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
# 跨模块目标枚举（统一 7 模块 target_module 字段）
# ──────────────────────────────────────────────


class CrossModuleTarget(str, Enum):
    """跨模块导入/导出的目标模块枚举

    任何事件 schema 中 target_module / source_module 字段涉及跨模块场景时，
    必须使用本枚举的字符串值（不在枚举内的值视为非法的跨模块目标）。
    """
    FLASHCARD = "flashcard"
    PROJECT = "project"
    READING = "reading"
    LANGUAGE_ROOM = "language_room"
    MATERIAL = "material"
    COGNITIVE_NODE = "cognitive_node"
    PLAN = "plan"
    CONVERSATION = "conversation"
    PRACTICE = "practice"           # 计划项 target_module: 指向练习目标
    INTEREST_EXPLORER = "interest_explorer"  # 计划项 target_module: 指向兴趣探索
    MOOD_STRESS = "mood_stress"     # 计划项 target_module: 指向心情压力调节


# ──────────────────────────────────────────────
# Planning 计划项 source_module 枚举 (ADR 0006)
#
# 与 CrossModuleTarget 区分:
#   - CrossModuleTarget:  描述"目标模块"(target_module), 即 plan item 指向的实体域
#   - PlanningSourceModule: 描述"来源模块"(source_module), 即 plan item 由哪个域发起
#
# 例如: 计划项 source_module='reading' + target_module='flashcard'
#       表示"由阅读发起的、把内容导入到卡片的计划"。
#
# source_module 与 target_module 字段语义不同, 必须使用独立枚举。
# ──────────────────────────────────────────────


class PlanningSourceModule(str, Enum):
    """Planning 计划项 source_module 字段枚举 (SSOT)

    任何 plan_items.source_module / 事件 schema 的 source_module 字段
    必须使用本枚举的字符串值。新增模块时, 仅需在此处追加,
    planning schemas / completion_writer 路由表 / 服务硬编码字面量
    均通过本枚举引用, 保证单一来源 (DRY)。
    """
    FLASHCARD = "flashcard"
    PRACTICE = "practice"
    PROJECT = "project"
    READING = "reading"
    LANGUAGE_ROOM = "language_room"
    MANUAL = "manual"
    INTEREST = "interest"           # 顶层兴趣活动（非探索式）
    INTEREST_EXPLORER = "interest_explorer"
    MOOD_STRESS = "mood_stress"
    SECRETARY = "secretary"         # 秘书系统发起的计划
    SYSTEM = "system"               # 系统自动生成的计划


# ──────────────────────────────────────────────
# 练习域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class AnswerSubmitted(DomainEvent):
    """答题提交事件 — submit_answer 核心路径发布

    替代之前的 PracticeAnswerSubmitted 引用，统称为 AnswerSubmitted。
    """
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
    submitted_at: datetime = field(default_factory=_now)

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
# 错题本域事件
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ErrorBookEntryReviewed(DomainEvent):
    """错题复习自评事件

    当用户对错题本中的错题做自评时发布（关联 self_assessment）。
    由 FlashCard 复习 + ErrorBook 复习路径统一触发。
    """
    user_id: str = ""
    error_entry_id: str = ""
    self_assessment: Literal["difficult", "good", "easy"] = "good"
    review_count: int = 0
    is_resolved: bool = False
    reviewed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ErrorBookEntryReviewed"


@dataclass(frozen=True)
class ErrorBookEntryResolved(DomainEvent):
    """错题标记为已掌握事件

    当错题本中的错题被任意途径（手动 / 复习后自动 / 从外部导入）标记为已掌握时发布。
    """
    user_id: str = ""
    error_entry_id: str = ""
    resolution_method: Literal["manual", "auto_after_review", "import"] = "manual"
    resolved_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ErrorBookEntryResolved"


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
#
# 旧 CognitiveNodeUpdated 已拆分：
#   - CognitiveNodeLinked          : 节点与其他实体的链接变化
#   - CognitiveNodeMetadataChanged : 节点元数据（描述/标签/层级等）变化
# 掌握度（Belief）变化由 cognitive engine 通过 CognitiveEventRecord 内部处理，
# 不再走 DomainEvent 总线，避免与上述元事件语义混淆。
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class CognitiveNodeLinked(DomainEvent):
    """节点与其他实体的链接变化（创建/删除/更新）"""
    user_id: str = ""
    node_id: str = ""
    link_type: str = ""  # 链接类型（如 "prerequisite" / "related" / "imported_from"）
    target_ref_type: str = ""  # 目标实体类型（如 "material" / "flashcard" / "project_node"）
    target_ref_id: str = ""
    action: Literal["created", "deleted", "updated"] = "created"
    linked_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "CognitiveNodeLinked"


@dataclass(frozen=True)
class CognitiveNodeMetadataChanged(DomainEvent):
    """节点元数据变化（描述/标签/层级等非 Belief 字段）"""
    user_id: str = ""
    node_id: str = ""
    changed_fields: list[str] = field(default_factory=list)  # 变更的字段名列表
    changed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "CognitiveNodeMetadataChanged"


# ──────────────────────────────────────────────
# FlashCard 域事件 (Phase FlashCard)
#
# 依据: docs/modules/flashcard/events.md
# 关键设计:
#   - FlashCardReviewed 携带 linked_node_ids + node_link_roles
#     知识图谱消费者按 (primary=1.0 / secondary=0.3) 权重对 Belief 做 0.1 小贡献
#   - FlashCardStatusChanged 监听 status 字段变化 (later/processing/completed)
#   - FlashCardCreated 的 source/cross_module_source 严格遵循 events.md
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class FlashCardCreated(DomainEvent):
    """卡片创建（任何来源）— 详见 docs/modules/flashcard/events.md §2.1"""
    user_id: str = ""
    card_id: str = ""
    type: int = 1
    # 本模块内部来源
    source: Literal["manual", "system"] = "manual"
    # 跨模块引用来源（与 source 互斥，二选一）
    #  - practice_error / reading_note / conversation / project / language_room / interest_explorer
    #    : 来自其他模块的具体子类型 (子级)
    #  - reading / practice / project_module : 来自其他模块 (顶级模块名) — 简写
    # 完整 SSOT 见 docs/modules/flashcard/events.md §2.1 + ADR 0002
    cross_module_source: str | None = None
    linked_node_ids: list[str] = field(default_factory=list)
    source_ref: dict | None = None
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardCreated"


@dataclass(frozen=True)
class FlashCardUpdated(DomainEvent):
    """卡片内容更新 — 详见 docs/modules/flashcard/events.md §2.1"""
    user_id: str = ""
    card_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    reset_scheduling: bool = False
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardUpdated"


@dataclass(frozen=True)
class FlashCardSuspended(DomainEvent):
    """用户暂停卡片"""
    user_id: str = ""
    card_id: str = ""
    suspended_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardSuspended"


@dataclass(frozen=True)
class FlashCardResumed(DomainEvent):
    """用户恢复卡片"""
    user_id: str = ""
    card_id: str = ""
    resumed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardResumed"


@dataclass(frozen=True)
class FlashCardReset(DomainEvent):
    """用户重置调度"""
    user_id: str = ""
    card_id: str = ""
    reset_at: datetime = field(default_factory=_now)
    previous_review_count: int = 0

    @property
    def event_type(self) -> str:
        return "FlashCardReset"


@dataclass(frozen=True)
class FlashCardArchived(DomainEvent):
    """用户归档卡片"""
    user_id: str = ""
    card_id: str = ""
    archived_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardArchived"


@dataclass(frozen=True)
class FlashCardDeleted(DomainEvent):
    """用户删除卡片（软删除时发出）"""
    user_id: str = ""
    card_id: str = ""
    deleted_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardDeleted"


@dataclass(frozen=True)
class FlashCardReviewed(DomainEvent):
    """单次复习自评完成 — 核心事件（驱动 Belief 回写 + FSRS 状态更新）

    详见 docs/modules/flashcard/events.md §2.2 / §3.2 / §3.4
    """
    user_id: str = ""
    card_id: str = ""
    session_id: str = ""
    self_assessment: Literal["difficult", "good", "easy"] = "good"
    stability_before: float = 0.0
    stability_after: float = 0.0
    difficulty_before: float = 0.0
    difficulty_after: float = 0.0
    interval_before: int = 0  # 天
    interval_after: int = 0
    elapsed_days: int = 0
    # 关联知识点（用于 Belief 回写）
    linked_node_ids: list[str] = field(default_factory=list)
    # {"node_id": "primary" / "secondary"}
    node_link_roles: dict[str, str] = field(default_factory=dict)
    next_review_at: datetime = field(default_factory=_now)
    reviewed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardReviewed"


@dataclass(frozen=True)
class FlashCardSessionStarted(DomainEvent):
    """复习会话开始 — 详见 docs/modules/flashcard/events.md §2.2"""
    user_id: str = ""
    session_id: str = ""
    source_module: str = "manual"  # manual / plan_item
    initial_card_count: int = 0
    started_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardSessionStarted"


@dataclass(frozen=True)
class FlashCardSessionEnded(DomainEvent):
    """复习会话结束 — 详见 docs/modules/flashcard/events.md §2.2"""
    user_id: str = ""
    session_id: str = ""
    total_cards: int = 0
    difficult_count: int = 0
    good_count: int = 0
    easy_count: int = 0
    duration_seconds: int = 0
    ended_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardSessionEnded"


@dataclass(frozen=True)
class FlashCardStatusChanged(DomainEvent):
    """卡片 status 字段变化 (later/processing/completed) — 详见 events.md §2.3"""
    user_id: str = ""
    card_id: str = ""
    old_status: str = ""
    new_status: str = ""
    changed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardStatusChanged"


@dataclass(frozen=True)
class FlashCardImportedToModule(DomainEvent):
    """卡片内容导出到其他模块（与 Project 对称）

    target_module 必须为 CrossModuleTarget 枚举的合法值
    """
    user_id: str = ""
    card_id: str = ""
    target_module: CrossModuleTarget = CrossModuleTarget.READING
    target_ref_id: str = ""
    imported_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "FlashCardImportedToModule"


# ──────────────────────────────────────────────
# MoodStress 模块事件 (ADR 0005)
#
# 设计原则：
# - 这些事件不触发 CognitiveNode.Belief 更新
# - 心情压力是主观状态，Belief 的合法来源仅限主动学习行为
# - 干预工具不修改 FSRS / Belief / Scheduling
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class MoodStressRecorded(DomainEvent):
    """用户主动记录心情/压力/能量（手动优先，自动检测不覆盖）

    source: 本事件内部来源
        - manual: 用户主动记录（手动优先）
        - system: 系统自动捕获
    cross_module_source: 跨模块来源（与 source 互斥）
        - assistant_dialog: 来自对话系统
        - language_room:   来自语言房间语音特征
    """
    user_id: str = ""
    record_id: str = ""
    source: Literal["manual", "system"] = "manual"
    cross_module_source: Literal["assistant_dialog", "language_room"] | None = None
    emotion_tags: list[str] = field(default_factory=list)   # 11 类标签
    pressure_score: int | None = None                       # 1-10
    energy_score: int | None = None                         # 1-10
    text_note: str | None = None
    related_event_ids: list[str] = field(default_factory=list)
    recorded_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "MoodStressRecorded"


@dataclass(frozen=True)
class MoodStressInterventionTriggered(DomainEvent):
    """干预工具被使用（4 种：breathing / knowledge_breathing / cognitive_reappraisal / environment）

    入事件流（让其他模块知道用户在调节），
    但不触发 Belief/FSRS 更新。
    """
    user_id: str = ""
    intervention_type: Literal[
        "breathing", "knowledge_breathing",
        "cognitive_reappraisal", "environment",
    ] = "breathing"
    duration_seconds: int = 0
    triggered_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "MoodStressInterventionTriggered"


@dataclass(frozen=True)
class MoodStressRuleTriggered(DomainEvent):
    """规则被触发（通知规划/对话模块，仅标记，不自动修改）

    规划模块根据 action 标记受影响待办项；
    对话模块根据此事件调整回复语气。
    """
    user_id: str = ""
    rule_id: str = ""
    trigger_metric: str = ""       # pressure_score / energy_score / emotion_tag
    trigger_value: float | str = 0
    action: str = ""               # postpone_high_intensity / only_flashcard / suggest_break
    triggered_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "MoodStressRuleTriggered"


@dataclass(frozen=True)
class MoodStressBehaviorSignalDetected(DomainEvent):
    """行为信号被检测（仅提示用户，不自动修改学习数据）

    signal_type: 7 种行为信号
        - task_switch:       短时间内频繁切换学习任务
        - stay_duration:     同一知识点停留时间异常
        - error_rate:        练习错误率突增
        - undo:              连续撤销/修改同一内容
        - session_anomaly:   学习会话提前中断或明显延长
        - flashcard_failure: 卡片复习"困难"比例显著上升
        - voice_features:    语言房间的语音特征
    """
    user_id: str = ""
    signal_type: str = ""
    signal_data: dict = field(default_factory=dict)
    severity: int = 1            # 1-3
    detected_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "MoodStressBehaviorSignalDetected"


@dataclass(frozen=True)
class MoodStressPrefsUpdated(DomainEvent):
    """用户更新偏好"""
    user_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "MoodStressPrefsUpdated"


# ──────────────────────────────────────────────
# Project 域事件 (Phase: 项目式探索构建)
#
# 严格遵循 docs/modules/project-based-exploration/events.md:
#  - 节点事件全部带 project_id, user_id
#  - 字段级版本（changed_fields 是字段列表）
#  - ProjectNodeCompleted 由 PlanItemCompleted 消费后**不重发**
#    → 避免与 Planning 形成事件循环
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ProjectCreated(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    name: str = ""
    template_id: str = ""
    template_version: int = 0
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectCreated"


@dataclass(frozen=True)
class ProjectArchived(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    archived_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectArchived"


@dataclass(frozen=True)
class ProjectCompleted(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    total_nodes: int = 0
    completed_nodes: int = 0
    duration_days: int = 0
    completed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectCompleted"


@dataclass(frozen=True)
class ProjectMilestoneMarked(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    milestone_id: str = ""
    milestone_name: str = ""
    snapshot_data: dict = field(default_factory=dict)
    is_user_marked: bool = True
    marked_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectMilestoneMarked"


@dataclass(frozen=True)
class ProjectNodeCreated(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    parent_id: str = ""
    type: int = 0  # 1-7
    title: str = ""
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectNodeCreated"


@dataclass(frozen=True)
class ProjectNodeUpdated(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    version: int = 0
    changed_fields: list[str] = field(default_factory=list)  # 字段级粒度
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectNodeUpdated"


@dataclass(frozen=True)
class ProjectNodeVersionCreated(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    version_number: int = 0
    is_rollback: bool = False
    rolled_back_from_version: int = 0
    change_source: Literal["user_edit", "api", "rollback", "system"] = "user_edit"
    changed_fields: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectNodeVersionCreated"


@dataclass(frozen=True)
class ProjectNodeRolledBack(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    from_version: int = 0
    to_version: int = 0
    rolled_back_fields: list[str] = field(default_factory=list)
    rolled_back_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectNodeRolledBack"


@dataclass(frozen=True)
class ProjectNodeCompleted(DomainEvent):
    """节点标记完成事件。

    关键约束（events.md 3.1.1）:
      - 由 PlanItemCompleted 消费后触发 → **不重发** 此事件以避免循环
      - 通过 plan_item_id 幂等键丢弃重复触发
    """
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    completion_method: Literal["manual", "auto", "imported"] = "manual"
    linked_node_ids: list[str] = field(default_factory=list)
    completed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectNodeCompleted"


@dataclass(frozen=True)
class ProjectNodeArchived(DomainEvent):
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    archived_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectNodeArchived"


@dataclass(frozen=True)
class ProjectNodeExported(DomainEvent):
    """节点内容导出到其他模块。

    target_module 强制使用 CrossModuleTarget 枚举的合法值。
    """
    project_id: str = ""
    user_id: str = ""
    node_id: str = ""
    target_module: CrossModuleTarget = CrossModuleTarget.FLASHCARD
    target_ref_id: str = ""
    export_data: dict = field(default_factory=dict)
    exported_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ProjectNodeExported"


# ──────────────────────────────────────────────
# Planning 域事件 (ADR 0006)
#
# 设计原则：
# - 计划项是"用户决定"而非"学习行为"：不触发 CognitiveNode.Belief 更新
# - PlanItemCompleted 完成后**不重发源事件**（防循环）
# - source_module 必须是 PlanningSourceModule 合法值之一 (SSOT in 本文件)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class PlanItemCreated(DomainEvent):
    """计划项创建事件"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""   # PlanningSourceModule 字符串值 (SSOT)
    target_type: str = ""
    target_ref_id: str = ""
    title: str = ""
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanItemCreated"


@dataclass(frozen=True)
class PlanItemScheduled(DomainEvent):
    """用户安排项（含 source_module: PlanningSourceModule）"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""   # PlanningSourceModule 字符串值 (SSOT)
    scheduled_for: datetime = field(default_factory=_now)
    plan_date: str = ""       # ISO date 字符串
    is_mood_rule_affected: bool = False
    scheduled_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanItemScheduled"


@dataclass(frozen=True)
class PlanItemActivated(DomainEvent):
    """到达安排时间（系统触发）"""
    user_id: str = ""
    plan_item_id: str = ""
    activated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanItemActivated"


@dataclass(frozen=True)
class PlanItemStarted(DomainEvent):
    """用户标记开始"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""   # PlanningSourceModule 字符串值
    started_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanItemStarted"


@dataclass(frozen=True)
class PlanItemCompleted(DomainEvent):
    """计划项完成 — 触发完成回写

    关键约束：
      - 由 PlanItemCompleted 路由到的回写**不重发**源模块事件
        （例如不再发布 ProjectNodeCompleted / FlashCardReviewed 等）
      - 通过 plan_item_id 做幂等去重，防止循环
      - source_module 必须是 PlanningSourceModule 合法值之一 (SSOT)
    """
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""   # PlanningSourceModule 字符串值 (SSOT)
    target_type: str = ""
    target_ref_id: str = ""
    actual_minutes: int = 0
    linked_node_ids: list[str] = field(default_factory=list)
    completed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanItemCompleted"


@dataclass(frozen=True)
class PlanItemSkipped(DomainEvent):
    """用户跳过项"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""   # PlanningSourceModule 字符串值
    skipped_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanItemSkipped"


@dataclass(frozen=True)
class PlanItemExtended(DomainEvent):
    """用户延长项"""
    user_id: str = ""
    plan_item_id: str = ""
    source_module: str = ""   # PlanningSourceModule 字符串值
    extended_minutes: int = 0
    extended_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanItemExtended"


@dataclass(frozen=True)
class PlanGoalCreated(DomainEvent):
    user_id: str = ""
    goal_id: str = ""
    title: str = ""
    target_module: str = ""
    target_metric: str = ""
    target_value: int = 0
    deadline: str = ""
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanGoalCreated"


@dataclass(frozen=True)
class PlanGoalProgressUpdated(DomainEvent):
    user_id: str = ""
    goal_id: str = ""
    old_value: int = 0
    new_value: int = 0
    target_value: int = 0
    progress_pct: float = 0.0
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanGoalProgressUpdated"


@dataclass(frozen=True)
class PlanGoalCompleted(DomainEvent):
    user_id: str = ""
    goal_id: str = ""
    final_value: int = 0
    completed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanGoalCompleted"


@dataclass(frozen=True)
class PlanPeriodicReviewGenerated(DomainEvent):
    user_id: str = ""
    review_id: str = ""
    period_type: Literal["weekly", "monthly"] = "weekly"
    period_start: str = ""
    period_end: str = ""
    summary_data: dict = field(default_factory=dict)
    generated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanPeriodicReviewGenerated"


@dataclass(frozen=True)
class PlanDeviationRecorded(DomainEvent):
    user_id: str = ""
    plan_item_id: str = ""
    deviation_type: Literal["timeout", "skip", "early_complete", "extra_insert"] = "timeout"
    planned_minutes: int = 0
    actual_minutes: int = 0
    deviation_minutes: int = 0
    recorded_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "PlanDeviationRecorded"


# ──────────────────────────────────────────────
# Reading 域事件 (ADR 0003)
#
# 设计原则：
# - 阅读事件**不**更新 CognitiveNode.Belief（避免被动阅读影响认知状态）
# - 笔记 = 复用 FlashCard 反思型（card_type=7, cross_module_source=reading_note）
# - 回顾提醒 = 复用 PlanItemScheduled（source_module='reading'）
# - target_module 强制使用 CrossModuleTarget 枚举
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ReadingSessionStarted(DomainEvent):
    """阅读会话开始"""
    user_id: str = ""
    session_id: str = ""
    material_id: str = ""
    mode: Literal["intensive", "skim", "review"] = "intensive"
    started_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingSessionStarted"


@dataclass(frozen=True)
class ReadingSessionEnded(DomainEvent):
    """阅读会话结束（关键事件：触发秘书与规划模块联动）

    字段命名遵循 events.md 统一为 `linked_node_ids`（原 nodes_linked）
    """
    user_id: str = ""
    session_id: str = ""
    material_id: str = ""
    duration_seconds: float = 0.0
    annotations_count: int = 0
    notes_count: int = 0  # 创建的 FlashCard 反思型数量
    cards_generated: int = 0
    linked_node_ids: list[str] = field(default_factory=list)
    ended_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingSessionEnded"


@dataclass(frozen=True)
class ReadingSessionResumed(DomainEvent):
    """中断后恢复阅读会话"""
    user_id: str = ""
    session_id: str = ""
    last_chunk_id: str = ""
    resumed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingSessionResumed"


@dataclass(frozen=True)
class ReadingAnnotationCreated(DomainEvent):
    """创建标注（5 颜色多意图分类）"""
    user_id: str = ""
    annotation_id: str = ""
    material_id: str = ""
    chunk_id: str = ""
    color: Literal["yellow", "blue", "green", "purple", "orange"] = "yellow"
    intent: Literal[
        "important_concept", "data_fact", "quotable", "doubt", "conflict"
    ] = "important_concept"
    linked_node_id: str = ""
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationCreated"


@dataclass(frozen=True)
class ReadingAnnotationUpdated(DomainEvent):
    """更新标注"""
    user_id: str = ""
    annotation_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationUpdated"


@dataclass(frozen=True)
class ReadingAnnotationDeleted(DomainEvent):
    """删除标注"""
    user_id: str = ""
    annotation_id: str = ""
    deleted_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationDeleted"


@dataclass(frozen=True)
class ReadingAnnotationProcessed(DomainEvent):
    """标注被处理（提取为 FlashCard / 发起对话 / 转知识点）

    target_module 强制使用 CrossModuleTarget 枚举
    """
    user_id: str = ""
    annotation_id: str = ""
    target_module: CrossModuleTarget = CrossModuleTarget.FLASHCARD
    target_ref_id: str = ""
    processed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingAnnotationProcessed"


@dataclass(frozen=True)
class ReadingModeChanged(DomainEvent):
    """阅读模式切换（精读/略读/回顾）"""
    user_id: str = ""
    session_id: str = ""
    old_mode: Literal["intensive", "skim", "review"] = "intensive"
    new_mode: Literal["intensive", "skim", "review"] = "intensive"
    changed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingModeChanged"


@dataclass(frozen=True)
class ReadingNoteCreated(DomainEvent):
    """阅读笔记创建（实际是创建 FlashCard 反思型）"""
    user_id: str = ""
    material_id: str = ""
    card_id: str = ""  # FlashCard.id
    source: Literal["reading_note"] = "reading_note"
    cross_module_source: Literal["reading"] | None = "reading"
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "ReadingNoteCreated"


@dataclass(frozen=True)
class ReadingReviewReminderScheduled(DomainEvent):
    """阅读回顾提醒已排入 Planning（复用 PlanItemScheduled）"""
    user_id: str = ""
    material_id: str = ""
    reminder_days: int = 7  # 7 / 30 / 90
    scheduled_for: datetime = field(default_factory=_now)
    plan_item_id: str = ""  # PlanItem.id

    @property
    def event_type(self) -> str:
        return "ReadingReviewReminderScheduled"


# ──────────────────────────────────────────────
# LanguageRoom 域事件 (ADR 0004)
#
# 设计原则：
#   - 数据归属 = 参与者各自存 (决策 1)
#   - 房间可见性 = 邀请制 (决策 2)
#   - 事件模型 = 房间事件聚合后分发 (决策 3)
#   - AI 纠错倾向 = 用户主动选择 (决策 6, 非 AI 评判)
#   - 错误标记 = 用户主动行为 = Belief 合法来源 (决策 7)
#   - 转写数据 = 各自分开 (决策 11)
#   - 词汇便签复用 FlashCard (source='language_room')
#   - 错误标记复用 ErrorBookEntry
#   - 文字辅助复用 ExplainCard
#   - source_module 严格使用 CrossModuleTarget 枚举值
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class LanguageRoomCreated(DomainEvent):
    """房间创建事件"""
    user_id: str = ""
    room_id: str = ""
    scenario_id: str = ""
    max_participants: int = 2
    is_recording_enabled: bool = False
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomCreated"


@dataclass(frozen=True)
class LanguageRoomStarted(DomainEvent):
    """房间开始（第一个用户加入触发）"""
    user_id: str = ""
    room_id: str = ""
    started_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomStarted"


@dataclass(frozen=True)
class LanguageRoomEnded(DomainEvent):
    """房间结束事件"""
    user_id: str = ""
    room_id: str = ""
    ended_at: datetime = field(default_factory=_now)
    duration_seconds: float = 0.0

    @property
    def event_type(self) -> str:
        return "LanguageRoomEnded"


@dataclass(frozen=True)
class LanguageRoomCompleted(DomainEvent):
    """房间完成 — 核心聚合事件（按参与者维度分别构造）

    关键约束（events.md §2.1）:
      - 房间结束触发单一聚合事件
      - 按参与者维度分别构造（每个参与者各收一份）
      - 每个版本只包含该用户相关的转写、错误标记、生成的卡片等
    """
    user_id: str = ""
    room_id: str = ""
    session_id: str = ""           # 该用户在该房间的 session
    scenario_id: str = ""
    duration_seconds: float = 0.0
    transcript_segments: list[dict] = field(default_factory=list)  # 用户的转写
    errors_marked: int = 0         # 用户标记的错误数
    cards_generated: int = 0       # 生成的 FlashCard 数
    linked_node_ids: list[str] = field(default_factory=list)  # 关联的 CognitiveNode
    ai_help_requests: int = 0
    completed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomCompleted"


@dataclass(frozen=True)
class LanguageRoomParticipantJoined(DomainEvent):
    """参与者加入房间事件"""
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    participant_type: str = "human"  # human / ai_companion / ai_assistant
    ai_role_id: str = ""
    joined_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomParticipantJoined"


@dataclass(frozen=True)
class LanguageRoomParticipantLeft(DomainEvent):
    """参与者离开房间事件"""
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    speaking_time_seconds: int = 0
    left_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomParticipantLeft"


@dataclass(frozen=True)
class LanguageRoomScenarioChanged(DomainEvent):
    """房间场景切换事件（房主权限）"""
    user_id: str = ""
    room_id: str = ""
    old_scenario_id: str = ""
    new_scenario_id: str = ""
    changed_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomScenarioChanged"


@dataclass(frozen=True)
class LanguageRoomTranscriptSegmentAdded(DomainEvent):
    """转写片段新增 — 高频事件 (events.md §2.3)

    按参与者各自存储 (决策 11)。
    """
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    participant_id: str = ""
    speaker_id: str = ""
    text: str = ""
    language: str = ""
    confidence: float = 0.0
    started_at: datetime = field(default_factory=_now)
    ended_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomTranscriptSegmentAdded"


@dataclass(frozen=True)
class LanguageRoomRecordingStarted(DomainEvent):
    """录音开始事件"""
    user_id: str = ""
    room_id: str = ""
    recording_id: str = ""
    started_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomRecordingStarted"


@dataclass(frozen=True)
class LanguageRoomRecordingStopped(DomainEvent):
    """录音停止事件"""
    user_id: str = ""
    room_id: str = ""
    recording_id: str = ""
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    ended_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomRecordingStopped"


@dataclass(frozen=True)
class LanguageRoomAIPersonaJoined(DomainEvent):
    """AI 角色加入房间事件"""
    user_id: str = ""  # 房主/邀请者
    room_id: str = ""
    participant_id: str = ""
    persona_id: str = ""
    role_label: str = ""
    joined_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomAIPersonaJoined"


@dataclass(frozen=True)
class LanguageRoomAIPersonaLeft(DomainEvent):
    """AI 角色离开房间事件"""
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    persona_id: str = ""
    left_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomAIPersonaLeft"


@dataclass(frozen=True)
class LanguageRoomAIHelperInvoked(DomainEvent):
    """AI 辅助者被用户召唤事件

    关键设计 (决策 6):
      - 用户主动召唤 = 主动行为
      - 不代表 AI 主动评判
      - 输出仅在用户个人侧边区
    """
    user_id: str = ""
    room_id: str = ""
    helper_type: str = "grammar"  # grammar/vocabulary/sentence_pattern
    query: str = ""
    response: str = ""
    invoked_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomAIHelperInvoked"


@dataclass(frozen=True)
class LanguageRoomVocabularyCaptured(DomainEvent):
    """词汇便签事件 — 复用 FlashCard 数据卡片 (cross_module_source='language_room')"""
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    card_id: str = ""              # FlashCard.id
    word: str = ""
    translation: str = ""
    captured_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomVocabularyCaptured"


@dataclass(frozen=True)
class LanguageRoomErrorMarked(DomainEvent):
    """用户标记错误 — 复用 ErrorBookEntry

    关键设计 (决策 7):
      - 用户主动行为 = Belief 合法来源
      - 不直接更新 Belief，通过 ErrorBookEntry 流程回写
    """
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    error_entry_id: str = ""       # ErrorBookEntry.id
    error_type: str = "grammar"    # grammar/vocabulary/pronunciation/coherence
    linked_node_ids: list[str] = field(default_factory=list)
    marked_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomErrorMarked"


@dataclass(frozen=True)
class LanguageRoomMessagePosted(DomainEvent):
    """文字辅助区消息 — 复用 ExplainCard 浮卡

    用于链接、拼写、补充说明
    """
    user_id: str = ""
    room_id: str = ""
    message_id: str = ""
    text: str = ""
    message_type: str = "text"     # text/link/spelling/note
    explain_card_id: str = ""      # ExplainCard.id
    posted_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "LanguageRoomMessagePosted"


# ──────────────────────────────────────────────
# InterestExplorer 域事件 (ADR 0007)
#
# 设计原则（events.md §2 + ADR 0007 决策 3/10）:
#   - **不**调用 LLM：内容搬运而非生成
#   - 链接级别去重（不是 title 级别）
#   - 本地权重 InterestLocalWeightAdjusted **不**发送到服务端
#   - 跨模块导入 InterestContentImported 强制使用 CrossModuleTarget
#   - InterestPushGenerated 字段为 generated_at（不是 pushed_at）
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class InterestTagCreated(DomainEvent):
    """兴趣标签创建"""
    user_id: str = ""
    tag_id: str = ""
    name: str = ""
    level: int = 0
    parent_id: str | None = None
    weight: int = 1  # 1=主要, 2=次要
    # source: 本模块内部来源
    #   - manual : 用户手动添加
    #   - system : 系统推荐 / 自动归类
    # cross_module_source: 跨模块引用来源（与 source 互斥，二选一）
    #   - from_knowledge : 来自知识图谱已有点的标签同步
    #   - from_reading   : 来自阅读标注
    source: Literal["manual", "system"] = "manual"
    cross_module_source: Literal["from_knowledge", "from_reading"] | None = None
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestTagCreated"


@dataclass(frozen=True)
class InterestTagUpdated(DomainEvent):
    """兴趣标签更新（重命名 / 调整权重 / 调整层级）"""
    user_id: str = ""
    tag_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestTagUpdated"


@dataclass(frozen=True)
class InterestTagDeleted(DomainEvent):
    """兴趣标签删除"""
    user_id: str = ""
    tag_id: str = ""
    deleted_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestTagDeleted"


@dataclass(frozen=True)
class InterestTagFromKnowledgeCreated(DomainEvent):
    """从知识图谱创建兴趣标签（跨模块引用）

    关键约束（events.md §2.4）:
      - source_ref_id 指向 CognitiveNode.id
      - 不创建新 CognitiveNode，仅建立引用
    """
    user_id: str = ""
    tag_id: str = ""
    knowledge_node_id: str = ""
    tag_name: str = ""
    level: int = 0
    created_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestTagFromKnowledgeCreated"


@dataclass(frozen=True)
class InterestSourceEnabled(DomainEvent):
    """信息源启用"""
    user_id: str = ""
    source_id: str = ""
    name: str = ""
    type: str = ""  # arxiv/biorxiv/rss/atom/opml/internal
    enabled_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestSourceEnabled"


@dataclass(frozen=True)
class InterestSourceDisabled(DomainEvent):
    """信息源禁用"""
    user_id: str = ""
    source_id: str = ""
    name: str = ""
    disabled_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestSourceDisabled"


@dataclass(frozen=True)
class InterestSourceFetched(DomainEvent):
    """信息源抓取完成（由抓取调度器发出）

    关键约束（events.md §5）:
      - 抓取是定期调度（不通过事件总线触发）
      - InterestSourceFetched 仅记录抓取结果
    """
    user_id: str | None = None  # NULL 表示系统内置源
    source_id: str = ""
    source_name: str = ""
    new_items_count: int = 0
    total_items: int = 0
    duration_ms: int = 0
    error_message: str | None = None
    fetched_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestSourceFetched"


@dataclass(frozen=True)
class InterestPushGenerated(DomainEvent):
    """推送内容已生成

    关键约束（events.md §2.1）:
      - generated_at 字段（不是 pushed_at）: 内容生成时刻
      - push_type: research_object / research_method / hot_news
      - matched_tags 记录匹配的标签 ID 列表
      - 由秘书系统消费后生成 InterestPushProposal（站内通知）
    """
    user_id: str = ""
    push_id: str = ""
    push_type: Literal["research_object", "research_method", "hot_news"] = "research_object"
    title: str = ""
    url: str = ""
    source_id: str | None = None
    source_name: str = ""
    matched_tags: list[str] = field(default_factory=list)
    summary_preview: str = ""
    generated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestPushGenerated"


@dataclass(frozen=True)
class InterestPushFeedbackRecorded(DomainEvent):
    """用户对推送的反馈已记录

    feedback:
      - read : 用户标记为已读
      - later : 用户标记为稍后读（→ FlashCard 临时状态）
      - dislike : 用户标记为不感兴趣（→ 本地权重调整）
    """
    user_id: str = ""
    push_id: str = ""
    feedback: Literal["read", "later", "dislike"] = "read"
    feedback_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestPushFeedbackRecorded"


@dataclass(frozen=True)
class InterestContentImported(DomainEvent):
    """用户将推送内容导入其他模块（5 个目标模块）

    关键约束（events.md §2.2）:
      - target_module 必须为 CrossModuleTarget 枚举的合法值
      - 5 个目标: reading / project / flashcard / cognitive_node / language_room
      - target_ref_id 记录目标模块的引用 ID
    """
    user_id: str = ""
    push_id: str = ""
    target_module: CrossModuleTarget = CrossModuleTarget.READING
    target_ref_id: str = ""
    imported_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestContentImported"


@dataclass(frozen=True)
class InterestLocalWeightAdjusted(DomainEvent):
    """本地权重调整 - 不发送到服务端

    关键约束（ADR 0007 决策 10）:
      - dislike_score 累计 0.0-1.0
      - **不**通过 event_bus 跨用户/跨设备传播
      - 仅本地采样概率调整
    """
    user_id: str = ""
    tag_id: str = ""
    tag_name: str = ""
    old_score: float = 0.0
    new_score: float = 0.0
    adjustment_count: int = 0
    adjusted_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestLocalWeightAdjusted"


@dataclass(frozen=True)
class InterestPrefsUpdated(DomainEvent):
    """用户更新推送偏好"""
    user_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "InterestPrefsUpdated"


# ──────────────────────────────────────────────
# 用户域事件 (Task #84: Settings 模块统一)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class UserPreferencesUpdated(DomainEvent):
    """用户偏好统一更新事件

    Task #84: 用户级偏好统一存储 (user_settings JSONB) + 跨模块联动。
    覆盖以下场景：
      - LLM 自定义配置 (api_base / api_key / model_name / system_prompt / temperature / max_tokens)
      - 学习偏好 (socratic_mode / socratic_follow_up / auto_scroll_on_load)
      - 主题 / 设计风格 (theme / style)
      - 布局偏好（暂留 localStorage, 不发事件）

    changed_keys: 顶层 key 列表, 例如 ["llm_config", "ui", "learning"]
    """
    user_id: str = ""
    changed_keys: list[str] = field(default_factory=list)
    source: Literal["api", "frontend_sync", "migration"] = "api"
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "UserPreferencesUpdated"


@dataclass(frozen=True)
class UserProfileUpdated(DomainEvent):
    """用户资料更新事件 (Task #84)

    触发场景: PATCH /api/auth/me, POST /api/auth/change-password,
              POST /api/auth/deactivate, POST /api/auth/me/logout-other-devices
    """
    user_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    # password: 密码已修改; deactivate: 账号已注销; profile: 资料已更新
    # logout_others: 踢出其他设备
    change_type: Literal["profile", "password", "deactivate", "logout_others", "avatar"] = "profile"
    updated_at: datetime = field(default_factory=_now)

    @property
    def event_type(self) -> str:
        return "UserProfileUpdated"


# ──────────────────────────────────────────────
# 事件类型注册表（用于 event_bus 订阅路由）
# ──────────────────────────────────────────────

EVENT_TYPES: dict[str, type[DomainEvent]] = {
    cls().event_type: cls  # type: ignore[misc]
    for cls in [
        # 用户域事件 (Task #84)
        UserPreferencesUpdated,
        UserProfileUpdated,
        # 练习域事件
        AnswerSubmitted,
        ErrorRecorded,
        SessionCompleted,
        ErrorBookEntryReviewed,
        ErrorBookEntryResolved,
        AssistantReplied,
        CognitiveNodeLinked,
        CognitiveNodeMetadataChanged,
        MessageClassified,
        PracticeSubmitted,
        NodeCreated,
        ProposalAccepted,
        PendingCrossTopic,
        MoodStressRecorded,
        MoodStressInterventionTriggered,
        MoodStressRuleTriggered,
        MoodStressBehaviorSignalDetected,
        MoodStressPrefsUpdated,
        # Project 域事件
        ProjectCreated,
        ProjectArchived,
        ProjectCompleted,
        ProjectMilestoneMarked,
        ProjectNodeCreated,
        ProjectNodeUpdated,
        ProjectNodeVersionCreated,
        ProjectNodeRolledBack,
        ProjectNodeCompleted,
        ProjectNodeArchived,
        ProjectNodeExported,
        # Planning 域事件
        PlanItemCreated,
        PlanItemScheduled,
        PlanItemActivated,
        PlanItemStarted,
        PlanItemCompleted,
        PlanItemSkipped,
        PlanItemExtended,
        PlanGoalCreated,
        PlanGoalProgressUpdated,
        PlanGoalCompleted,
        PlanPeriodicReviewGenerated,
        PlanDeviationRecorded,
        # FlashCard 域事件 (docs/modules/flashcard/events.md)
        FlashCardCreated,
        FlashCardUpdated,
        FlashCardSuspended,
        FlashCardResumed,
        FlashCardReset,
        FlashCardArchived,
        FlashCardDeleted,
        FlashCardReviewed,
        FlashCardSessionStarted,
        FlashCardSessionEnded,
        FlashCardStatusChanged,
        FlashCardImportedToModule,
        # Reading 域事件 (ADR 0003)
        ReadingSessionStarted,
        ReadingSessionEnded,
        ReadingSessionResumed,
        ReadingAnnotationCreated,
        ReadingAnnotationUpdated,
        ReadingAnnotationDeleted,
        ReadingAnnotationProcessed,
        ReadingModeChanged,
        ReadingNoteCreated,
        ReadingReviewReminderScheduled,
        # LanguageRoom 域事件 (ADR 0004)
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
        LanguageRoomAIPersonaJoined,
        LanguageRoomAIPersonaLeft,
        LanguageRoomAIHelperInvoked,
        LanguageRoomVocabularyCaptured,
        LanguageRoomErrorMarked,
        LanguageRoomMessagePosted,
        # InterestExplorer 域事件 (ADR 0007)
        InterestTagCreated,
        InterestTagUpdated,
        InterestTagDeleted,
        InterestTagFromKnowledgeCreated,
        InterestSourceEnabled,
        InterestSourceDisabled,
        InterestSourceFetched,
        InterestPushGenerated,
        InterestPushFeedbackRecorded,
        InterestContentImported,
        InterestLocalWeightAdjusted,
        InterestPrefsUpdated,
    ]
}
