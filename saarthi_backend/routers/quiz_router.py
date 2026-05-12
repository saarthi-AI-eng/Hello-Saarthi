"""Quizzes and attempts (under /api/quizzes)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.common_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.schema.quiz_schemas import (
    AdaptiveQuizRequest,
    AdaptiveQuizResponse,
    PeerComparisonResponse,
    QuizAttemptResponse,
    QuizAttemptSubmitRequest,
    QuizDetailResponse,
    QuizQuestionCreate,
    QuizQuestionResponse,
    QuizQuestionUpdate,
    QuizResponse,
)
from saarthi_backend.service import quiz_service
from saarthi_backend.utils.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def _question_to_response(q):
    return QuizQuestionResponse(
        id=str(q.id),
        questionText=q.question_text,
        optionsJson=q.options_json,
        correctIndex=q.correct_index,
        sortOrder=q.sort_order,
    )


@router.get("", response_model=PaginatedResponse[QuizResponse])
async def list_quizzes(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    course_id: int | None = None,
):
    """List quizzes, optionally by course (paginated)."""
    quizzes, total = await quiz_service.list_quizzes(
        db, course_id=course_id, limit=pagination.limit, offset=pagination.offset
    )
    out = []
    for q in quizzes:
        _, questions = await quiz_service.get_quiz_with_questions(db, q.id)
        out.append(
            QuizResponse(
                id=str(q.id),
                courseId=str(q.course_id) if q.course_id else None,
                title=q.title,
                description=q.description,
                durationMinutes=q.duration_minutes,
                passingScore=q.passing_score,
                questionCount=len(questions),
            )
        )
    return PaginatedResponse(
        items=out,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get quiz with questions (for taking quiz)."""
    quiz, questions = await quiz_service.get_quiz_with_questions(db, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    return QuizDetailResponse(
        id=str(quiz.id),
        courseId=str(quiz.course_id) if quiz.course_id else None,
        title=quiz.title,
        description=quiz.description,
        durationMinutes=quiz.duration_minutes,
        passingScore=quiz.passing_score,
        questionCount=len(questions),
        questions=[_question_to_response(q) for q in questions],
    )


@router.post("/{quiz_id}/attempts", response_model=QuizAttemptResponse, status_code=201)
async def start_attempt(
    quiz_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Start a quiz attempt."""
    a = await quiz_service.start_attempt(db, user.id, quiz_id)
    if not a:
        raise NotFoundError("Quiz not found.", details=None)
    await db.commit()
    return QuizAttemptResponse(
        id=str(a.id),
        quizId=str(a.quiz_id),
        score=a.score,
        startedAt=a.started_at.isoformat() if a.started_at else "",
        submittedAt=a.submitted_at.isoformat() if a.submitted_at else None,
    )


@router.post("/{quiz_id}/attempts/{attempt_id}/submit", response_model=QuizAttemptResponse)
async def submit_attempt(
    quiz_id: int,
    attempt_id: int,
    body: QuizAttemptSubmitRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit attempt with score and answers."""
    attempt = await quiz_service.submit_attempt(
        db, attempt_id, user.id, score=body.score, answers_json=body.answersJson
    )
    if not attempt:
        raise NotFoundError("Attempt not found.", details=None)
    await db.commit()
    return QuizAttemptResponse(
        id=str(attempt.id),
        quizId=str(attempt.quiz_id),
        score=attempt.score,
        startedAt=attempt.started_at.isoformat() if attempt.started_at else "",
        submittedAt=attempt.submitted_at.isoformat() if attempt.submitted_at else None,
    )


@router.post("/{quiz_id}/questions", response_model=QuizQuestionResponse, status_code=201)
async def create_question(
    quiz_id: int,
    body: QuizQuestionCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a quiz question (admin/teacher only)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    q = await quiz_service.create_question(
        db,
        quiz_id=quiz_id,
        question_text=body.questionText,
        options_json=body.optionsJson,
        correct_index=body.correctIndex,
        sort_order=body.sortOrder,
    )
    if not q:
        raise NotFoundError("Quiz not found.", details=None)
    await db.commit()
    return _question_to_response(q)


@router.patch("/{quiz_id}/questions/{question_id}", response_model=QuizQuestionResponse)
async def update_question(
    quiz_id: int,
    question_id: int,
    body: QuizQuestionUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a quiz question (admin/teacher only)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    updated = await quiz_service.update_question(
        db,
        quiz_id=quiz_id,
        question_id=question_id,
        question_text=body.questionText,
        options_json=body.optionsJson,
        correct_index=body.correctIndex,
        sort_order=body.sortOrder,
    )
    if not updated:
        raise NotFoundError("Question not found.", details=None)
    await db.commit()
    return _question_to_response(updated)


@router.delete("/{quiz_id}/questions/{question_id}", status_code=204)
async def delete_question(
    quiz_id: int,
    question_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a quiz question (admin/teacher only)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    deleted = await quiz_service.delete_question(db, quiz_id, question_id)
    if not deleted:
        raise NotFoundError("Quiz or question not found.", details=None)
    await db.commit()


@router.get("/{quiz_id}/attempts", response_model=PaginatedResponse[QuizAttemptResponse])
async def list_my_attempts(
    quiz_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List current user's attempts for quiz (paginated)."""
    attempts, total = await quiz_service.list_attempts(
        db, user.id, quiz_id, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse(
        items=[
            QuizAttemptResponse(
                id=str(a.id),
                quizId=str(a.quiz_id),
                score=a.score,
                startedAt=a.started_at.isoformat() if a.started_at else "",
                submittedAt=a.submitted_at.isoformat() if a.submitted_at else None,
            )
            for a in attempts
        ],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


# ─── Adaptive Quiz Generation ─────────────────────────────────────────────────

@router.post("/generate", response_model=AdaptiveQuizResponse)
async def generate_adaptive_quiz(
    body: AdaptiveQuizRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    AI-generate a quiz adapted to the student's past performance.
    Analyzes weak topics from attempt history and targets the right difficulty.
    """
    result = await quiz_service.generate_adaptive_quiz(db, user.id, body)
    return result


# ─── Peer Comparison ──────────────────────────────────────────────────────────

@router.get("/peer-comparison", response_model=PeerComparisonResponse)
async def peer_comparison(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the current user's score percentile against all peers."""
    return await quiz_service.get_peer_comparison(db, user.id)
