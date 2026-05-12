"""Chat message request/response schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessageItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatMessageRequest(BaseModel):
    """POST /api/chat/message (stateless)."""
    message: str = Field(..., min_length=1)
    conversationHistory: list[ChatMessageItem] = Field(default_factory=list)
    contextMaterialTitle: Optional[str] = None


class ChatMessageResponse(BaseModel):
    response: str


# ─── SSE Streaming ────────────────────────────────────────────────────────────

class StreamMessageRequest(BaseModel):
    """POST /api/chat/stream — streams response via SSE."""
    message: str = Field(..., min_length=1)
    conversationHistory: list[ChatMessageItem] = Field(default_factory=list)
    conversationId: Optional[str] = Field(None, description="If provided, exchange is persisted.")
    contextMaterialTitle: Optional[str] = None


# ─── Study Plan ───────────────────────────────────────────────────────────────

class StudyPlanCourse(BaseModel):
    title: str
    code: str
    progressPercent: int


class StudyPlanDeadline(BaseModel):
    title: str
    course: str
    dueDate: str
    type: str  # "assignment" | "quiz"


class StudyPlanQuizScore(BaseModel):
    quizTitle: str
    score: float
    weakTopics: List[str] = Field(default_factory=list)


class StudyPlanRequest(BaseModel):
    """POST /api/chat/study-plan"""
    courses: List[StudyPlanCourse] = Field(default_factory=list)
    deadlines: List[StudyPlanDeadline] = Field(default_factory=list)
    recentQuizScores: List[StudyPlanQuizScore] = Field(default_factory=list)
    hoursPerDay: int = Field(default=3, ge=1, le=12)
    focusArea: Optional[str] = None


class StudyPlanDayBlock(BaseModel):
    day: str          # "Monday", "Tuesday", etc.
    sessions: List[str]  # e.g. ["09:00–10:30 · DSP: Review FFT (weak area)", ...]
    totalHours: float


class StudyPlanResponse(BaseModel):
    weekPlan: List[StudyPlanDayBlock]
    summary: str
    priorityTopics: List[str]
    generatedAt: str


# ─── Conversations ────────────────────────────────────────────────────────────

class ConversationResponse(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str


class ChatMessageResponseItem(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: str


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messages: list[ChatMessageResponseItem] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=255)


class UpdateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    contextMaterialTitle: Optional[str] = None


class SendMessageResponse(BaseModel):
    userMessage: ChatMessageResponseItem
    assistantMessage: ChatMessageResponseItem
