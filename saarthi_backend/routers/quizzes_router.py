"""Quizzes and attempts (under /api/quizzes)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import QuizAttemptDAO, QuizDAO, QuizQuestionDAO
from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.pagination_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.schema.quiz_schemas import (
    QuizAttemptResponse,
    QuizAttemptSubmitRequest,
    QuizDetailResponse,
    QuizQuestionCreate,
    QuizQuestionResponse,
    QuizQuestionUpdate,
    QuizResponse,
)
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
    quizzes = await QuizDAO.list_all(
        db,
        course_id=course_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    total = await QuizDAO.count_all(db, course_id=course_id)
    out = []
    for q in quizzes:
        questions = await QuizQuestionDAO.list_by_quiz(db, q.id)
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
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    questions = await QuizQuestionDAO.list_by_quiz(db, quiz_id)
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
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    a = await QuizAttemptDAO.create(db, user.id, quiz_id)
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
    attempt = await QuizAttemptDAO.submit(
        db,
        attempt_id,
        user.id,
        score=body.score,
        answers_json=body.answersJson,
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
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    q = await QuizQuestionDAO.create(
        db,
        quiz_id=quiz_id,
        question_text=body.questionText,
        options_json=body.optionsJson,
        correct_index=body.correctIndex,
        sort_order=body.sortOrder,
    )
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
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    q = await QuizQuestionDAO.get_by_id(db, question_id)
    if not q or q.quiz_id != quiz_id:
        raise NotFoundError("Question not found.", details=None)
    updated = await QuizQuestionDAO.update(
        db,
        question_id,
        question_text=body.questionText,
        options_json=body.optionsJson,
        correct_index=body.correctIndex,
        sort_order=body.sortOrder,
    )
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
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    q = await QuizQuestionDAO.get_by_id(db, question_id)
    if not q or q.quiz_id != quiz_id:
        raise NotFoundError("Question not found.", details=None)
    await QuizQuestionDAO.delete(db, question_id)
    await db.commit()


@router.get("/{quiz_id}/attempts", response_model=PaginatedResponse[QuizAttemptResponse])
async def list_my_attempts(
    quiz_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List current user's attempts for quiz (paginated)."""
    attempts = await QuizAttemptDAO.list_by_user_quiz(
        db, user.id, quiz_id, limit=pagination.limit, offset=pagination.offset
    )
    total = await QuizAttemptDAO.count_by_user_quiz(db, user.id, quiz_id)
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
