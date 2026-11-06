"""Request/response schemas for quizzes and attempts."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class QuizQuestionResponse(BaseModel):
    id: str
    questionText: str
    optionsJson: str
    # None when sent to a student taking the quiz; the answer is revealed only after submit.
    correctIndex: Optional[int] = None
    sortOrder: int

    class Config:
        populate_by_name = True


class QuizResponse(BaseModel):
    id: str
    courseId: Optional[str] = None
    title: str
    description: Optional[str] = None
    durationMinutes: int
    passingScore: float
    questionCount: int = 0

    class Config:
        populate_by_name = True


class QuizDetailResponse(QuizResponse):
    questions: List[QuizQuestionResponse]


class QuizAnswerResult(BaseModel):
    questionId: str
    selectedIndex: Optional[int] = None
    correctIndex: int
    isCorrect: bool


class QuizAttemptResponse(BaseModel):
    id: str
    quizId: str
    score: Optional[float] = None
    startedAt: str
    submittedAt: Optional[str] = None
    # Filled only in the submit response, so the student can review their answers.
    correctCount: Optional[int] = None
    totalQuestions: Optional[int] = None
    results: Optional[List[QuizAnswerResult]] = None

    class Config:
        populate_by_name = True


class QuizAnswer(BaseModel):
    questionId: str
    selectedIndex: Optional[int] = Field(None, ge=0)


class QuizAttemptSubmitRequest(BaseModel):
    """The server grades the attempt; any client-sent score is ignored."""

    answers: List[QuizAnswer] = Field(default_factory=list)


class QuizQuestionCreate(BaseModel):
    questionText: str
    optionsJson: str = "[]"
    correctIndex: int = Field(..., ge=0)
    sortOrder: int = 0


class QuizQuestionUpdate(BaseModel):
    questionText: Optional[str] = None
    optionsJson: Optional[str] = None
    correctIndex: Optional[int] = Field(None, ge=0)
    sortOrder: Optional[int] = None


# ─── Adaptive Quiz Generation ─────────────────────────────────────────────────

class PastAttemptSummary(BaseModel):
    quizTitle: str
    score: float
    answersJson: str = "[]"
    questionsJson: str = "[]"


class AdaptiveQuizRequest(BaseModel):
    topic: str = Field(..., description="Subject/topic to generate quiz on, e.g. 'Z-transform'")
    courseTitle: Optional[str] = None
    difficulty: Optional[str] = Field(None, description="easy | medium | hard | auto")
    numQuestions: int = Field(default=10, ge=3, le=20)
    pastAttempts: List[PastAttemptSummary] = Field(default_factory=list)


class GeneratedQuizQuestion(BaseModel):
    questionText: str
    options: List[str]
    correctIndex: int
    explanation: str
    difficulty: str  # "easy" | "medium" | "hard"
    topic: str


class AdaptiveQuizResponse(BaseModel):
    title: str
    topic: str
    difficulty: str
    questions: List[GeneratedQuizQuestion]
    weakAreasDetected: List[str]
    generatedAt: str


# ─── Peer Comparison ──────────────────────────────────────────────────────────

class ScoreBucket(BaseModel):
    range: str        # e.g. "80-90"
    count: int        # number of peers in this bucket
    isUser: bool      # True for the bucket containing the current user


class PeerComparisonResponse(BaseModel):
    userAvgScore: float
    percentile: float          # 0-100: what % of peers the user outperforms
    peerCount: int             # total peers who have taken at least one quiz
    distribution: List[ScoreBucket]
    topicBreakdown: List[dict]  # [{topic, userAvg, peerAvg}]
    generatedAt: str
