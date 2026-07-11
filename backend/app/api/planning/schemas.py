"""Planning API Schemas (Pydantic) — request/response models for the planning workbench."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from shared.events import CrossModuleTarget, PlanningSourceModule

# ──────────────────────────────────────────────
# 计划项 (plan_items)
# ──────────────────────────────────────────────


class PlanItemCreate(BaseModel):
    source_module: PlanningSourceModule
    target_type: str
    target_ref_id: str
    title: str
    description: str = ""
    estimated_minutes: int = 0
    linked_node_ids: list[str] = Field(default_factory=list)
    priority: int = 0
    scheduled_for: Optional[datetime] = None
    plan_date: Optional[date] = None


class PlanItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None
    priority: Optional[int] = None
    scheduled_for: Optional[datetime] = None
    plan_date: Optional[date] = None
    status: Optional[Literal["pending", "scheduled", "in_progress", "completed", "skipped", "extended"]] = None


class PlanItemComplete(BaseModel):
    actual_minutes: int = 0


class PlanItemResponse(BaseModel):
    id: str
    user_id: str
    source_module: str
    target_type: str
    target_ref_id: str
    title: str
    description: str = ""
    estimated_minutes: int = 0
    actual_minutes: Optional[int] = None
    linked_node_ids: list[str] = Field(default_factory=list)
    priority: int = 0
    is_mood_rule_affected: bool = False
    status: str = "pending"
    scheduled_for: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    skipped_at: Optional[datetime] = None
    plan_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# 视图方案 (plan_view_layouts)
# ──────────────────────────────────────────────


class ViewLayoutCreate(BaseModel):
    name: str
    view_type: Literal["day", "week", "knowledge", "custom"]
    filters: dict[str, Any] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ViewLayoutResponse(BaseModel):
    id: str
    user_id: str
    name: str
    view_type: str
    filters: dict[str, Any] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    created_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# 目标 (plan_goals)
# ──────────────────────────────────────────────


class PlanGoalCreate(BaseModel):
    title: str
    description: str = ""
    target_module: CrossModuleTarget
    target_metric: Literal["node_count", "card_count", "practice_count", "duration_minutes"]
    target_value: int
    deadline: Optional[date] = None


class PlanGoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[int] = None
    current_value: Optional[int] = None
    deadline: Optional[date] = None
    status: Optional[Literal["active", "completed", "abandoned"]] = None


class PlanGoalResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str = ""
    target_module: str
    target_metric: str
    target_value: int
    current_value: int = 0
    deadline: Optional[date] = None
    status: str = "active"
    progress_pct: float = 0.0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# 周期回顾 (plan_periodic_reviews)
# ──────────────────────────────────────────────


class PeriodicReviewCreate(BaseModel):
    period_type: Literal["weekly", "monthly"]
    period_start: date
    period_end: date
    summary_data: dict[str, Any] = Field(default_factory=dict)
    user_note: str = ""


class PeriodicReviewResponse(BaseModel):
    id: str
    user_id: str
    period_type: str
    period_start: date
    period_end: date
    summary_data: dict[str, Any] = Field(default_factory=dict)
    user_note: str = ""
    created_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# 计划项确认请求 (plan_item_confirmations)
# ──────────────────────────────────────────────


class PlanItemConfirmationResponse(BaseModel):
    id: str
    user_id: str
    request_id: str
    suggestion_id: Optional[str] = None
    source_module: str = "secretary"
    target_type: str
    target_ref_id: str
    title: str
    description: str = ""
    priority: int = 0
    estimated_minutes: int = 10
    linked_node_ids: list[str] = Field(default_factory=list)
    proposed_scheduled_for: Optional[datetime] = None
    status: str = "pending"
    expires_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# 视图聚合（daily / weekly / knowledge）
# ──────────────────────────────────────────────


class StatusBarResponse(BaseModel):
    """顶部状态条（来自消费后端引擎）"""
    fatigue_risk: str = "low"          # low/medium/high
    pressure_score: Optional[int] = None
    energy_score: Optional[int] = None
    habit_level: str = "beginner"      # beginner/regular/intensive
    pomodoro_work_minutes: int = 25
    pomodoro_break_minutes: int = 5
    pomodoro_message: str = ""


class DailyViewResponse(BaseModel):
    """日视图：顶部状态 + 时间轴项 + 待安排池 + 简报"""
    date: date
    status_bar: StatusBarResponse
    timeline_items: list[PlanItemResponse] = Field(default_factory=list)
    pending_pool: list[dict[str, Any]] = Field(default_factory=list)
    adaptive_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    brief_summary: dict[str, Any] = Field(default_factory=dict)


class WeeklyViewResponse(BaseModel):
    """周视图：7 天并列"""
    week_start: date
    week_end: date
    days: list[dict[str, Any]] = Field(default_factory=list)  # [{date, item_count, total_minutes, completed_count}]
    totals: dict[str, int] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class KnowledgeViewResponse(BaseModel):
    """知识视图：知识点维度 + 待办密度"""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    selected_node_id: Optional[str] = None
    selected_node_todos: list[PlanItemResponse] = Field(default_factory=list)
