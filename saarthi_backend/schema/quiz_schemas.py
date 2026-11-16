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
    topic: Optional[str] = None
    difficulty: str = "recall"
    # Like correctIndex: hidden from students until they submit.
    explanation: Optional[str] = None

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
    topic: Optional[str] = None
    # The signed-in student's attempts on this quiz.
    attemptCount: int = 0
    bestScore: Optional[float] = None

    class Config:
        populate_by_name = True


class QuizDetailResponse(QuizResponse):
    questions: List[QuizQuestionResponse]


class QuizAnswerResult(BaseModel):
    questionId: str
    selectedIndex: Optional[int] = None
    correctIndex: int
    isCorrect: bool
    explanation: Optional[str] = None


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


_DIFFICULTY = "^(recall|application|analysis)$"


class QuizQuestionCreate(BaseModel):
    questionText: str = Field(..., min_length=1)
    optionsJson: str = "[]"
    correctIndex: int = Field(..., ge=0)
    sortOrder: int = 0
    topic: Optional[str] = Field(None, max_length=128)
    difficulty: str = Field("recall", pattern=_DIFFICULTY)
    explanation: Optional[str] = None


class QuizQuestionUpdate(BaseModel):
    questionText: Optional[str] = None
    optionsJson: Optional[str] = None
    correctIndex: Optional[int] = Field(None, ge=0)
    sortOrder: Optional[int] = None
    topic: Optional[str] = Field(None, max_length=128)
    difficulty: Optional[str] = Field(None, pattern=_DIFFICULTY)
    explanation: Optional[str] = None


class QuizCreate(BaseModel):
    """A teacher's quiz with all its questions, created in one request."""

    courseId: int
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    durationMinutes: int = Field(15, ge=1, le=300)
    passingScore: float = Field(60.0, ge=0, le=100)
    topic: Optional[str] = Field(None, max_length=128)
    questions: List[QuizQuestionCreate] = Field(..., min_length=1, max_length=100)


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
