"""Expert request/response schemas (unified contract)."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """One message in conversation_history."""

    role: Literal["user", "assistant"]
    content: str


# Optional expert-specific options (backend may ignore unknown)
ExpertOptions = dict[str, Any]


class UnifiedExpertRequest(BaseModel):
    """Unified request body for all expert endpoints."""

    query: str = Field(..., min_length=1)
    intent: str = Field(
        ...,
        description="One of THEORY, PROBLEM_SOLVING, VIDEO_REFERENCE, CODE_REQUEST, DIAGRAM_EXPLAIN, EXAM_PREP, FOLLOWUP",
    )
    conversation_id: Optional[str] = None
    conversation_history: Optional[list[ConversationMessage]] = None
    options: Optional[ExpertOptions] = None


# --- Response: Citation ---
class Citation(BaseModel):
    """One citation in expert response."""

    source_type: Literal["notes", "video", "code", "exercise"]
    source_id: str
    title: str
    excerpt: str
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    url: Optional[str] = None


# --- Response: Expert-specific extensions ---
class VideoTimestamp(BaseModel):
    """Video expert: one timestamp entry."""

    video_id: str
    title: str
    start_sec: float
    end_sec: float
    summary: str


class CodeSnippet(BaseModel):
    """Code expert: one snippet."""

    language: str
    code: str
    explanation: str
    source: str


class StepItem(BaseModel):
    """Problem-solving: one step."""

    step_number: int
    description: str
    content: str


class PrerequisiteItem(BaseModel):
    """Theory: one prerequisite (when KG available)."""

    topic: str
    reason: str


class UnifiedExpertResponse(BaseModel):
    """Unified response for all experts (04-backend-to-orchestrator-responses)."""

    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: Optional[float] = Field(None, ge=0, le=1)
    suggested_followups: list[str] = Field(default_factory=list)
    expert_used: str = Field(
        ...,
        description="theory | problem_solving | video | code | multimodal | exam_prep | followup",
    )
    # Expert-specific (optional)
    prerequisites: Optional[list[PrerequisiteItem]] = None
    video_timestamps: Optional[list[VideoTimestamp]] = None
    code_snippets: Optional[list[CodeSnippet]] = None
    execution_output: Optional[str] = None
    steps: Optional[list[StepItem]] = None
    diagram_explanation: Optional[str] = None
    related_concepts: Optional[list[str]] = None
    question: Optional[str] = None
    options: Optional[list[str]] = None
    correct_index: Optional[int] = None
    explanation: Optional[str] = None

    model_config = {"extra": "allow"}
