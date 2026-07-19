"""Practice API — schemas."""
from pydantic import BaseModel, Field


class QuestionInput(BaseModel):
    text: str
    concept_ids: str = ""
    context_source: str = ""
    correct_answer: str = ""


class CreatePracticeRequest(BaseModel):
    workspace_id: str
    title: str = ""
    questions: list[QuestionInput] = Field(default_factory=list)


class SubmitAttemptRequest(BaseModel):
    question_id: str
    answer: str
    is_correct: bool = False
    confidence: int = 0
    response_time_s: float = 0.0


class ReviewAttemptRequest(BaseModel):
    attempt_id: str
    comment: str


class PracticeResponse(BaseModel):
    id: str
    workspace_id: str
    state: str
    title: str = ""
    total_questions: int = 0
    correct_count: int = 0
    created_at: str = ""


class QuestionResponse(BaseModel):
    id: str
    seq: int
    text: str = ""
    concept_ids: str = ""
    context_source: str = ""
    created_at: str = ""


class AttemptResponse(BaseModel):
    id: str
    question_id: str
    is_correct: bool = False
    reviewed: bool = False
    review_comment: str = ""
    created_at: str = ""
