"""Conversation API — schemas."""
from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    title: str = ""


class TurnRecordRequest(BaseModel):
    user_message: str
    ai_response: str
    reading_page: int = 0
    reading_scroll: float = 0.0
    memory_tier: str = ""
    knowledge_concepts: str = ""


class OrchestrationRequest(BaseModel):
    turn_id: str
    decision: str           # silence | suggest | generate | open_artifact
    artifact_type: str = ""
    artifact_id: str = ""


class TurnResponse(BaseModel):
    id: str
    seq: int
    user_message: str = ""
    ai_response: str = ""
    orchestration: str = ""
    created_at: str = ""


class ConversationItem(BaseModel):
    id: str
    session_id: str
    state: str
    title: str = ""
    created_at: str = ""


class LifecycleResponse(BaseModel):
    conversation_id: str
    state: str
    title: str = ""
