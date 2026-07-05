"""LanguageRoom API — Pydantic Schemas

依据 docs/modules/language-room/data-model.md + events.md + ADR 0004
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── 枚举 ──

RoomType = Literal["1v1", "small", "medium", "large"]
RoomStatus = Literal["active", "ended"]
ParticipantType = Literal["human", "ai_companion", "ai_assistant"]
InvasivenessLevel = Literal["low", "medium", "high"]
CorrectionTendency = Literal["none", "occasional", "proactive"]
HelperType = Literal["grammar", "vocabulary", "sentence_pattern"]
ProficiencyLevel = Literal["beginner", "intermediate", "advanced", "native"]
SpeechRate = Literal["slow", "normal", "fast"]
Behavior = Literal["talkative", "balanced", "concise"]
ScenarioCategory = Literal["daily", "academic", "business"]


# ── 房间 ──


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    scenario_id: str = ""
    room_type: RoomType = "1v1"
    max_participants: int = Field(default=2, ge=2, le=20)
    is_recording_enabled: bool = False
    is_transcript_enabled: bool = True
    ai_intrusion_level: InvasivenessLevel = "low"
    settings: dict[str, Any] = Field(default_factory=dict)


class RoomResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    scenario_id: str = ""
    room_type: str
    max_participants: int
    is_recording_enabled: bool
    is_transcript_enabled: bool
    ai_intrusion_level: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    settings: dict[str, Any] = Field(default_factory=dict)
    participant_count: int = 0
    created_at: Optional[datetime] = None


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    scenario_id: Optional[str] = None
    max_participants: Optional[int] = None
    is_recording_enabled: Optional[bool] = None
    is_transcript_enabled: Optional[bool] = None
    ai_intrusion_level: Optional[InvasivenessLevel] = None


# ── 参与者 ──


class ParticipantJoinRequest(BaseModel):
    invitation_token: str = ""
    role_label: str = ""
    language: str = ""


class ParticipantResponse(BaseModel):
    id: str
    room_id: str
    user_id: str
    participant_type: str
    ai_role_id: str = ""
    role_label: str = ""
    language: str = ""
    joined_at: Optional[datetime] = None
    left_at: Optional[datetime] = None
    speaking_time_seconds: int = 0
    is_muted: bool = False
    is_owner: bool = False


# ── 转写 ──


class TranscriptCreateRequest(BaseModel):
    """转写片段新增请求（通常由 LiveKit webhook 触发）"""
    participant_id: str
    text: str
    language: str = "en"
    confidence: float = 0.0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    speaker_id: str = ""
    speaker_name: str = ""


class TranscriptResponse(BaseModel):
    id: str
    room_id: str
    participant_id: str
    user_id: str
    segment_index: int
    text: str
    language: str = ""
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    confidence: float = 0.0
    speaker_id: str = ""
    speaker_name: str = ""
    is_user_marked: bool = False
    is_error: bool = False
    error_entry_id: str = ""
    created_at: Optional[datetime] = None


# ── 词汇便签（复用 FlashCard 数据卡）──


class VocabularyCaptureRequest(BaseModel):
    """词汇便签请求 — 复用 FlashCard 数据卡"""
    transcript_id: str = ""
    word: str = Field(..., min_length=1)
    translation: str = ""
    context_sentence: str = ""
    language: str = ""
    linked_node_ids: list[str] = Field(default_factory=list)


class VocabularyCaptureResponse(BaseModel):
    id: str
    user_id: str
    room_id: str
    transcript_id: str = ""
    card_id: str = ""  # FlashCard.id
    word: str
    translation: str = ""
    context_sentence: str = ""
    language: str = ""
    captured_at: Optional[datetime] = None


# ── 错误标记（复用 ErrorBookEntry）──


class ErrorMarkRequest(BaseModel):
    """错误标记 — 复用 ErrorBookEntry"""
    transcript_id: str
    error_type: Literal["grammar", "vocabulary", "pronunciation", "coherence"] = "grammar"
    linked_node_ids: list[str] = Field(default_factory=list)
    user_note: str = ""


class ErrorMarkResponse(BaseModel):
    id: str
    user_id: str
    room_id: str
    transcript_id: str
    error_entry_id: str
    error_type: str
    linked_node_ids: list[str]
    marked_at: Optional[datetime] = None


# ── 文字辅助区消息（复用 ExplainCard）──


class MessagePostRequest(BaseModel):
    text: str
    message_type: Literal["text", "link", "spelling", "note"] = "text"
    reference_url: str = ""


class MessageResponse(BaseModel):
    id: str
    user_id: str
    room_id: str
    text: str
    message_type: str
    explain_card_id: str = ""
    posted_at: Optional[datetime] = None


# ── 录音 ──


class RecordingStartRequest(BaseModel):
    format: str = "opus"


class RecordingStopRequest(BaseModel):
    recording_id: str


class RecordingResponse(BaseModel):
    id: str
    room_id: str
    user_id: str
    storage_path: str
    file_size_bytes: int = 0
    duration_seconds: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    format: str = "opus"


# ── LiveKit Token ──


class TokenRequest(BaseModel):
    display_name: str = ""


class TokenResponse(BaseModel):
    token: str
    url: str
    identity: str
    room_name: str
    expires_at: float


# ── 场景 ──


class ScenarioCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    category: ScenarioCategory = "daily"
    roles: list[dict[str, Any]] = Field(default_factory=list)
    target_goals: list[str] = Field(default_factory=list)
    prompt_text: str = ""
    linked_node_ids: list[str] = Field(default_factory=list)
    cross_disciplinary: bool = False


class ScenarioResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    description: str = ""
    category: str = ""
    roles: list[dict[str, Any]] = Field(default_factory=list)
    target_goals: list[str] = Field(default_factory=list)
    prompt_text: str = ""
    linked_node_ids: list[str] = Field(default_factory=list)
    cross_disciplinary: bool = False
    is_system: bool = False
    created_at: Optional[datetime] = None


# ── AI 角色 ──


class PersonaCreate(BaseModel):
    name: str = Field(..., min_length=1)
    gender_voice: str = ""
    personality: str = ""
    target_language: str = "en"
    proficiency: ProficiencyLevel = "intermediate"
    speech_rate: SpeechRate = "normal"
    accent: str = ""
    behavior: Behavior = "balanced"
    correction_tendency: CorrectionTendency = "none"
    is_topic_lead: bool = False
    background: str = ""


class PersonaResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    gender_voice: str = ""
    personality: str = ""
    target_language: str
    proficiency: str
    speech_rate: str
    accent: str = ""
    behavior: str
    correction_tendency: str
    is_topic_lead: bool
    is_system: bool
    background: str = ""
    created_at: Optional[datetime] = None


# ── AI 辅助者配置 ──


class InvasivenessUpdateRequest(BaseModel):
    invasiveness_level: InvasivenessLevel = "low"
    helper_types: list[HelperType] = Field(
        default_factory=lambda: ["grammar", "vocabulary", "sentence_pattern"]
    )
    correction_tendency: CorrectionTendency = "none"
    response_style: Literal["concise", "balanced", "detailed"] = "concise"


class InvasivenessResponse(BaseModel):
    user_id: str
    room_id: str
    invasiveness_level: str
    helper_types: list[str]
    correction_tendency: str
    response_style: str


# ── AI 辅助者召唤 ──


class AIHelperInvokeRequest(BaseModel):
    helper_type: HelperType = "grammar"
    query: str
    context_text: str = ""


class AIHelperInvokeResponse(BaseModel):
    helper_type: str
    response: str
    invoked_at: Optional[datetime] = None


# ── 场景切换 ──


class ScenarioChangeRequest(BaseModel):
    scenario_id: str


# ── 会话回顾 ──


class SessionReviewResponse(BaseModel):
    session_id: str
    room_id: str
    user_id: str
    scenario: Optional[ScenarioResponse] = None
    duration_seconds: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    transcript_count: int = 0
    errors_marked: int = 0
    cards_generated: int = 0
    ai_help_requests: int = 0
    vocabulary_captured: int = 0
    messages_posted: int = 0
    transcripts: list[TranscriptResponse] = Field(default_factory=list)
    errors: list[ErrorMarkResponse] = Field(default_factory=list)
    vocabularies: list[VocabularyCaptureResponse] = Field(default_factory=list)
    messages: list[MessageResponse] = Field(default_factory=list)


# ── 邀请 ──


class InvitationCreate(BaseModel):
    invitee_id: str = ""  # 空 = 邀请链接
    expires_hours: int = 24


class InvitationResponse(BaseModel):
    id: str
    room_id: str
    inviter_id: str
    invitee_id: str = ""
    invitation_token: str
    is_used: bool
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
