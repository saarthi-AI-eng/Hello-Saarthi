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


# ─── Socratic Challenge Mode ───────────────────────────────────────────────────

class SocraticChallengeRequest(BaseModel):
    """POST /api/chat/socratic — AI debates the student to force active recall."""
    claim: str = Field(..., min_length=1, description="Student's statement/answer to be challenged.")
    topic: str
    courseTitle: Optional[str] = None
    difficulty: Literal["gentle", "moderate", "rigorous"] = "moderate"


class SocraticChallengeResponse(BaseModel):
    challenge: str          # AI's counter-argument / probing question
    hints: List[str]        # if student is stuck
    verdict: Optional[str]  # "correct" | "partially_correct" | "incorrect" after full exchange
    explanation: str


# ─── Concept Graph ─────────────────────────────────────────────────────────────

class ConceptNode(BaseModel):
    id: str
    label: str
    topic: str
    mastery: float        # 0.0–1.0 derived from quiz scores
    prereqs: List[str]    # ids of prerequisite nodes


class ConceptGraphResponse(BaseModel):
    nodes: List[ConceptNode]
    generatedAt: str


# ─── Exam Prediction ───────────────────────────────────────────────────────────

class ExamPredictionTopic(BaseModel):
    topic: str
    probability: float   # 0–100
    readiness: float     # 0–100 (how prepared the student is)
    action: str          # "review", "practice", "ready"


class ExamPredictionRequest(BaseModel):
    courseTitle: str
    recentQuizScores: List[StudyPlanQuizScore] = Field(default_factory=list)
    notesTopics: List[str] = Field(default_factory=list)
    hoursUntilExam: int = Field(default=72)


class ExamPredictionResponse(BaseModel):
    predictions: List[ExamPredictionTopic]
    topPriority: str      # single sentence action item
    generatedAt: str


# ─── Flashcard Generation ──────────────────────────────────────────────────────

class Flashcard(BaseModel):
    id: str
    front: str
    back: str
    topic: str
    difficulty: Literal["easy", "medium", "hard"]
    nextReviewAt: Optional[str] = None   # ISO date for spaced repetition
    interval: int = 1                    # days until next review (SM-2)
    easeFactor: float = 2.5              # SM-2 ease factor


class FlashcardDeckRequest(BaseModel):
    sourceText: str = Field(..., min_length=10, description="Note or transcript text to extract cards from.")
    topic: str
    courseTitle: Optional[str] = None
    maxCards: int = Field(default=15, ge=3, le=40)


class FlashcardReviewRequest(BaseModel):
    cardId: str
    quality: int = Field(..., ge=0, le=5, description="SM-2 quality rating 0-5.")
    currentInterval: int = Field(default=1)
    currentEaseFactor: float = Field(default=2.5)


class FlashcardReviewResponse(BaseModel):
    nextInterval: int
    nextEaseFactor: float
    nextReviewAt: str


class FlashcardDeckResponse(BaseModel):
    topic: str
    cards: List[Flashcard]
    generatedAt: str
