"""
FlashCard API - Pydantic Schemas

依据 docs/modules/flashcard/data-model.md + events.md
字段名严格遵循 data-model.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── 枚举别名 ──

# 卡片类型 (data-model.md §5.1)
CardType = Literal[1, 2, 3, 4, 5, 6, 7]
# 1: 基础问答, 2: 填空, 3: 对比, 4: 流程, 5: 应用场景, 6: 错题溯源, 7: 反思

# 来源 (data-model.md §5.2)
CardSource = Literal[
    "manual", "practice_error", "reading_note", "conversation",
    "project", "language_room", "interest_explorer"
]

# 状态 (data-model.md §5.3)
CardStatus = Literal[
    "pending", "later", "processing", "completed", "suspended", "archived"
]

# 自评 (events.md)
SelfAssessment = Literal["difficult", "good", "easy"]

# 关联角色 (data-model.md §5.4)
NodeLinkRole = Literal["primary", "secondary"]


# ── 基础模型 ──


class SourceRef(BaseModel):
    """卡片来源追溯 (data-model.md §1 source_ref)"""
    module: str = ""
    id: str = ""
    sub_id: str = ""
    offset: int = 0
    length: int = 0
    url: str = ""
    title: str = ""


class FlashCardBase(BaseModel):
    """卡片基础字段 (创建/更新共用)"""
    type: CardType = 1
    source: CardSource = "manual"
    front_text: str = Field(..., min_length=1)
    back_text: str = ""
    back_context: str = ""
    language: str = ""
    source_ref: SourceRef | dict = Field(default_factory=dict)
    status: CardStatus = "pending"
    target_retention: float = Field(0.85, ge=0.5, le=0.99)
    linked_node_ids: list[str] = Field(default_factory=list)
    node_link_roles: dict[str, NodeLinkRole] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    error_book_entry_id: str = ""


class FlashCardCreate(FlashCardBase):
    """POST /api/flashcards/ 请求体"""
    cross_module_source: Optional[Literal[
        "practice_error", "reading_note", "conversation",
        "project", "language_room", "interest_explorer"
    ]] = None  # events.md §2.1: 与 source 互斥


class FlashCardUpdate(BaseModel):
    """PATCH /api/flashcards/{id} 请求体 — 部分更新"""
    type: CardType | None = None
    front_text: str | None = None
    back_text: str | None = None
    back_context: str | None = None
    language: str | None = None
    source_ref: SourceRef | dict | None = None
    status: CardStatus | None = None
    target_retention: float | None = None
    linked_node_ids: list[str] | None = None
    node_link_roles: dict[str, NodeLinkRole] | None = None
    tags: list[str] | None = None
    reset_scheduling: bool = False  # 修改内容时是否重置 FSRS


class ReviewSubmitRequest(BaseModel):
    """POST /api/flashcards/{id}/review 请求体"""
    self_assessment: SelfAssessment
    session_id: str = ""


# ── 响应模型 ──


class FSRSStateResponse(BaseModel):
    """FSRS 调度状态 (供 UI 展示)"""
    stability: float
    difficulty: float
    forgetting_rate: float
    last_review_at: Optional[datetime]
    next_review_at: Optional[datetime]
    review_count: int
    lapse_count: int
    target_retention: float


class FlashCardResponse(BaseModel):
    """GET /api/flashcards/{id} 响应"""
    id: str
    user_id: str
    type: CardType
    source: CardSource
    front_text: str
    back_text: str
    back_context: str
    language: str
    source_ref: dict
    status: CardStatus
    suspended_at: Optional[datetime]
    is_resolved: bool
    # FSRS
    stability: Optional[float]
    difficulty: Optional[float]
    forgetting_rate: Optional[float]
    last_review_at: Optional[datetime]
    next_review_at: Optional[datetime]
    review_count: int
    lapse_count: int
    target_retention: float
    # 关联
    linked_node_ids: list[str]
    node_link_roles: dict
    tags: list[str]
    error_book_entry_id: Optional[str] = None
    response_history: list
    field_versions: dict
    # 时间
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewResultResponse(BaseModel):
    """POST /api/flashcards/{id}/review 响应 — 完整可观测"""
    card_id: str
    self_assessment: SelfAssessment
    # FSRS 变化
    stability_before: float
    stability_after: float
    difficulty_before: float
    difficulty_after: float
    forgetting_rate_after: float
    interval_before: int
    interval_after: int
    elapsed_days: int
    retrievability_before: float
    # 累计指标
    review_count: int = 0
    lapse_count: int = 0
    # 后续
    next_review_at: datetime
    reviewed_at: datetime
    # 可读
    explanation: str
    # Belief 回写摘要
    belief_deltas: list[dict] = Field(default_factory=list)


class DueCardItem(BaseModel):
    """GET /api/flashcards/due 列表项"""
    id: str
    type: CardType
    source: CardSource
    front_text: str
    back_text: str
    tags: list[str]
    next_review_at: datetime
    review_count: int
    stability: Optional[float]
    difficulty: Optional[float]
    linked_node_ids: list[str]


class DueCardsResponse(BaseModel):
    """GET /api/flashcards/due 响应"""
    total: int
    cards: list[DueCardItem]


class ImportFromTextRequest(BaseModel):
    """POST /api/flashcards/import-from-text 请求体"""
    text: str = Field(..., min_length=1)
    type: CardType = 1
    default_linked_node_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    language: str = ""


class ImportFromTextItem(BaseModel):
    """导入预览项"""
    suggested_front: str
    suggested_back: str
    confidence: float
    suggested_node_ids: list[str]


class ImportFromTextResponse(BaseModel):
    """导入预览响应"""
    items: list[ImportFromTextItem]
    total: int


class ImportFromErrorBookResponse(BaseModel):
    """GET /api/flashcards/import-from-errorbook/{error_id} 响应"""
    error_entry_id: str
    suggested_front: str
    suggested_back: str
    question_id: str
    skill_id: str
    suggested_linked_node_ids: list[str]
    already_imported: bool  # 是否已存在对应 FlashCard


class StatsResponse(BaseModel):
    """GET /api/flashcards/stats 响应"""
    total: int
    by_type: dict[str, int]
    by_source: dict[str, int]
    by_status: dict[str, int]
    due_today: int
    due_7d: int
    average_stability: float
    average_difficulty: float
    average_forgetting_rate: float


class ErrorResponse(BaseModel):
    """统一错误响应 (中文消息)"""
    error: str
    detail: str
    status_code: int
