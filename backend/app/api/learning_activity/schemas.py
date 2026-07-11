"""Learning Activity API schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LearningActivityResponse(BaseModel):
    """学习活动记录响应模型"""

    id: str
    user_id: str
    activity_type: str
    module: str
    source_event_id: str | None = None
    source_event_type: str | None = None
    idempotency_key: str | None = None
    title: str
    description: str = ""
    status: str = "completed"
    timestamp: datetime
    deep_link: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LearningActivityListResponse(BaseModel):
    """学习活动列表响应模型"""

    items: list[LearningActivityResponse]
    total: int
    limit: int
    offset: int


class LearningActivityStatsResponse(BaseModel):
    """学习活动统计响应模型"""

    user_id: str
    total: int
    by_module: dict[str, int] = Field(default_factory=dict)
    by_activity_type: dict[str, int] = Field(default_factory=dict)
