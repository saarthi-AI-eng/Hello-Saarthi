"""Request/response schemas for quizzes and attempts."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class QuizQuestionResponse(BaseModel):
    id: str
    questionText: str
    optionsJson: str
    correctIndex: int
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


class QuizAttemptResponse(BaseModel):
    id: str
    quizId: str
    score: Optional[float] = None
    startedAt: str
    submittedAt: Optional[str] = None

    class Config:
        populate_by_name = True


class QuizAttemptSubmitRequest(BaseModel):
    score: float = Field(..., ge=0, le=100)
    answersJson: str = "[]"


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
