"""
InterestExplorer API — Pydantic Schemas

依据: docs/modules/interest-explorer/data-model.md + events.md
严格遵循 CrossModuleTarget 枚举
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from shared.events import CrossModuleTarget


# ═══════════════════════════════════════════
# 枚举别名
# ═══════════════════════════════════════════

TagLevel = Literal[0, 1, 2]
TagWeight = Literal[1, 2]  # 1=主要, 2=次要
TagSource = Literal["manual", "from_knowledge", "from_reading"]

SourceType = Literal["arxiv", "biorxiv", "rss", "atom", "opml", "internal"]

PushType = Literal["research_object", "research_method", "hot_news"]
PushFeedback = Literal["read", "later", "dislike", "imported"]

PushFrequency = Literal["daily", "weekly", "manual"]


# ═══════════════════════════════════════════
# 1. 兴趣标签 Schemas
# ═══════════════════════════════════════════


class InterestTagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    level: TagLevel = 0
    parent_id: Optional[str] = None
    weight: TagWeight = 1
    color: Optional[str] = None
    source: TagSource = "manual"
    source_ref_id: Optional[str] = None  # 关联的 CognitiveNode / Material

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()


class InterestTagUpdate(BaseModel):
    name: Optional[str] = None
    weight: Optional[TagWeight] = None
    color: Optional[str] = None
    parent_id: Optional[str] = None


class InterestTagResponse(BaseModel):
    id: str
    user_id: str
    name: str
    level: int
    parent_id: Optional[str] = None
    weight: int
    source: str
    source_ref_id: Optional[str] = None
    color: Optional[str] = None
    created_at: Optional[str] = None
    dislike_score: float = 0.0
    children: list["InterestTagResponse"] = Field(default_factory=list)


# ═══════════════════════════════════════════
# 2. 推送偏好 Schemas
# ═══════════════════════════════════════════


class InterestPushPrefsUpdate(BaseModel):
    frequency: Optional[PushFrequency] = None
    push_time: Optional[str] = None  # HH:MM:SS
    timezone: Optional[str] = None
    daily_limit: Optional[int] = Field(None, ge=1, le=50)
    research_object_pct: Optional[int] = Field(None, ge=0, le=100)
    research_method_pct: Optional[int] = Field(None, ge=0, le=100)
    hot_news_pct: Optional[int] = Field(None, ge=0, le=100)
    cross_disciplinary: Optional[bool] = None
    retention_days: Optional[int] = Field(None, ge=1, le=3650)
    is_enabled: Optional[bool] = None


class InterestPushPrefsResponse(BaseModel):
    user_id: str
    frequency: str
    push_time: str
    timezone: str
    daily_limit: int
    research_object_pct: int
    research_method_pct: int
    hot_news_pct: int
    cross_disciplinary: bool
    retention_days: int
    is_enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ═══════════════════════════════════════════
# 3. 信息源 Schemas
# ═══════════════════════════════════════════


class InterestSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: SourceType
    category: Optional[str] = None
    config: dict = Field(default_factory=dict)
    enabled: bool = True


class InterestSourceResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    type: str
    category: Optional[str] = None
    config: dict
    enabled: bool
    is_system: bool
    user_enabled: bool = False
    last_fetched_at: Optional[str] = None
    last_fetch_status: Optional[str] = None
    last_fetch_error: Optional[str] = None
    created_at: Optional[str] = None


class InterestSourceEnableUpdate(BaseModel):
    enabled: bool


class InterestOPMLImportRequest(BaseModel):
    opml_xml: str = Field(..., min_length=1)


class InterestOPMLImportResponse(BaseModel):
    imported: int
    skipped: int
    items: list[InterestSourceResponse] = Field(default_factory=list)


# ═══════════════════════════════════════════
# 4. 推送 Schemas
# ═══════════════════════════════════════════


class InterestPushResponse(BaseModel):
    id: str
    user_id: str
    source_id: Optional[str] = None
    push_type: str
    title: str
    summary: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None
    matched_tags: list[str] = Field(default_factory=list)
    generated_at: Optional[str] = None
    feedback: Optional[str] = None  # read/later/dislike/imported


class InterestPushFeedbackRequest(BaseModel):
    feedback: PushFeedback
    target_module: Optional[CrossModuleTarget] = None
    target_ref_id: Optional[str] = None


class InterestPushImportRequest(BaseModel):
    """跨模块导入请求 — 严格使用 CrossModuleTarget"""
    target_module: CrossModuleTarget
    target_ref_id: Optional[str] = None  # 可选覆盖


class InterestTodayPushResponse(BaseModel):
    user_id: str
    date: str
    items: list[InterestPushResponse]
    total: int


class InterestPushHistoryResponse(BaseModel):
    items: list[InterestPushResponse]
    total: int
    limit: int
    offset: int


# ═══════════════════════════════════════════
# 5. 反馈 / 权重 Schemas
# ═══════════════════════════════════════════


class InterestWeightAdjustmentResponse(BaseModel):
    id: str
    user_id: str
    tag_id: str
    tag_name: Optional[str] = None
    tag_level: Optional[int] = None
    dislike_score: float
    adjustment_count: int
    updated_at: Optional[str] = None


class InterestWeightResetResponse(BaseModel):
    reset: bool
    cleared_count: int = 0


# ═══════════════════════════════════════════
# 6. 知识图谱引用 Schemas
# ═══════════════════════════════════════════


class InterestTagFromKnowledgeRequest(BaseModel):
    weight: TagWeight = 1
    level: TagLevel = 0
    color: Optional[str] = None


class InterestTagFromKnowledgeResponse(BaseModel):
    tag: InterestTagResponse
    knowledge_node_id: str


# 更新递归模型引用
InterestTagResponse.model_rebuild()
