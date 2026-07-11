"""Reading API — Pydantic schemas

依据 docs/modules/reading/data-model.md + ADR 0003
字段命名严格遵循 data-model.md
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── 枚举别名（与 shared/events.py 保持一致） ──

AnnotationColor = Literal["yellow", "blue", "green", "purple", "orange"]
AnnotationIntent = Literal[
    "important_concept", "data_fact", "quotable", "doubt", "conflict",
]
ReadingMode = Literal["intensive", "skim", "review"]


# ── 标注 (reading_annotations) ──


class AnnotationCreate(BaseModel):
    """POST /api/reading/annotations 请求体"""
    material_id: str = Field(..., min_length=1)
    color: AnnotationColor
    intent: Optional[AnnotationIntent] = None  # 不填则从 color 推断
    chunk_id: str = ""
    start_offset: int = 0
    end_offset: int = 0
    text: str = ""
    note: str = ""
    linked_node_id: str = ""


class AnnotationUpdate(BaseModel):
    """PATCH /api/reading/annotations/{id} 请求体"""
    color: Optional[AnnotationColor] = None
    intent: Optional[AnnotationIntent] = None
    text: Optional[str] = None
    note: Optional[str] = None
    linked_node_id: Optional[str] = None
    is_processed: Optional[bool] = None


class AnnotationResponse(BaseModel):
    """GET /api/reading/annotations 响应"""
    id: str
    user_id: str
    material_id: str
    chunk_id: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    color: AnnotationColor
    intent: AnnotationIntent
    text: Optional[str] = None
    note: Optional[str] = None
    linked_node_id: Optional[str] = None
    is_processed: bool = False
    followup: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AnnotationProcessRequest(BaseModel):
    """POST /api/reading/annotations/{id}/process 请求体"""
    target_module: Literal["flashcard", "conversation", "cognitive_node", "project"] = "flashcard"
    target_ref_id: str = Field(..., min_length=1)


# ── 会话 (reading_sessions) ──


class SessionStartRequest(BaseModel):
    """POST /api/reading/sessions 请求体"""
    material_id: str = Field(..., min_length=1)
    mode: ReadingMode = "intensive"


class SessionEndRequest(BaseModel):
    """POST /api/reading/sessions/{id}/end 请求体"""
    duration_seconds: Optional[float] = None  # 不传则自动计算


class SessionModeChangeRequest(BaseModel):
    """POST /api/reading/sessions/{id}/mode 请求体"""
    mode: ReadingMode


class SessionActivityRequest(BaseModel):
    """POST /api/reading/sessions/{id}/activity 请求体（增量）"""
    chapter_visited: Optional[str] = None
    state_snapshot: Optional[dict] = None
    progress_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    annotations_delta: int = 0
    notes_delta: int = 0
    cards_delta: int = 0
    node_linked: Optional[str] = None


class SessionResponse(BaseModel):
    """GET /api/reading/sessions 响应"""
    id: str
    user_id: str
    material_id: str
    mode: ReadingMode
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    chapters_visited: list[str] = Field(default_factory=list)
    annotations_created: int = 0
    notes_created: int = 0
    cards_generated: int = 0
    linked_node_ids: list[str] = Field(default_factory=list)
    state_snapshot: dict = Field(default_factory=dict)
    last_active_at: Optional[datetime] = None


# ── 笔记 (复用 FlashCard 反思型) ──


class NoteCreateRequest(BaseModel):
    """POST /api/reading/notes 请求体"""
    material_id: str = Field(..., min_length=1)
    # 笔记三段式
    front_text: str = Field(..., min_length=1, description="我的问题")
    back_text: str = Field(default="", description="我的回应")
    back_context: str = Field(default="", description="关键论述")
    # 关联
    linked_node_ids: list[str] = Field(..., min_length=1)
    chunk_id: str = ""
    chunk_id_range: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    language: str = ""
    session_id: str = ""


# ── 回顾提醒 (复用 PlanItem) ──


class ReviewReminderRequest(BaseModel):
    """POST /api/reading/review-reminder 请求体"""
    material_id: str = Field(..., min_length=1)
    review_after_days: int = 7
    title: str = ""
    description: str = ""
    estimated_minutes: int = 30


class ReviewReminderResponse(BaseModel):
    plan_item_id: str
    material_id: str
    review_after_days: int
    scheduled_for: datetime
    plan_item: dict = Field(default_factory=dict)


# ── 偏好 (reading_prefs) ──


class PrefsUpdateRequest(BaseModel):
    """PATCH /api/reading/prefs 请求体"""
    default_mode: Optional[ReadingMode] = None
    highlight_mastered: Optional[bool] = None
    highlight_weak: Optional[bool] = None
    auto_open_sidebar: Optional[bool] = None
    sync_scroll_default: Optional[bool] = None
    review_reminder_days: Optional[list[int]] = None


class PrefsResponse(BaseModel):
    user_id: str
    default_mode: ReadingMode = "intensive"
    highlight_mastered: bool = True
    highlight_weak: bool = True
    auto_open_sidebar: bool = True
    sync_scroll_default: bool = False
    review_reminder_days: list[int] = Field(default_factory=lambda: [7, 30, 90])


# ── 对比阅读 (reading_comparisons) ──


class CompareCreateRequest(BaseModel):
    material_id_left: str = Field(..., min_length=1)
    material_id_right: str = Field(..., min_length=1)
    sync_scroll: bool = False


class ComparePayloadResponse(BaseModel):
    material_id_left: str
    material_id_right: str
    sync_scroll: bool = False
    left: dict = Field(default_factory=dict)
    right: dict = Field(default_factory=dict)


# ── 模式切换 (ReadingModeChanged) ──
# 复用 SessionModeChangeRequest
