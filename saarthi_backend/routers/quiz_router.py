"""Quizzes and attempts (under /api/quizzes)."""

from typing import Annotated

import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import Course, Enrollment, Quiz, QuizAttempt, QuizQuestion, User
from saarthi_backend.schema.common_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.schema.quiz_schemas import (
    AdaptiveQuizRequest,
    AdaptiveQuizResponse,
    PeerComparisonResponse,
    QuizAttemptResponse,
    QuizAttemptSubmitRequest,
    QuizCreate,
    QuizDetailResponse,
    QuizQuestionCreate,
    QuizQuestionResponse,
    QuizQuestionUpdate,
    QuizResponse,
)
from saarthi_backend.service import course_service, quiz_service
from saarthi_backend.utils.exceptions import ForbiddenError, NotFoundError, ValidationError

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def _question_to_response(q, include_answer: bool = True):
    return QuizQuestionResponse(
        id=str(q.id),
        questionText=q.question_text,
        optionsJson=q.options_json,
        correctIndex=q.correct_index if include_answer else None,
        sortOrder=q.sort_order,
        topic=q.topic,
        difficulty=q.difficulty or "recall",
        explanation=q.explanation if include_answer else None,
    )


def _quiz_to_response(q, question_count: int, attempt_count: int = 0, best_score=None) -> QuizResponse:
    return QuizResponse(
        id=str(q.id),
        courseId=str(q.course_id) if q.course_id else None,
        title=q.title,
        description=q.description,
        durationMinutes=q.duration_minutes,
        passingScore=q.passing_score,
        questionCount=question_count,
        topic=q.topic,
        attemptCount=attempt_count,
        bestScore=best_score,
    )


async def _visible_course_ids(db: AsyncSession, user: User) -> list[int] | None:
    """Courses whose quizzes the user may see; None means all (admin)."""
    if user.role == "admin":
        return None
    if user.role == "teacher":
        rows = await db.execute(select(Course.id).where(Course.owner_id == user.id))
    else:
        rows = await db.execute(select(Enrollment.course_id).where(Enrollment.user_id == user.id))
    return [r[0] for r in rows.all()]


async def _check_quiz_access(db: AsyncSession, user: User, quiz) -> None:
    """Only members of the quiz's course (or its teacher, or an admin) may open it."""
    if quiz.course_id is None or user.role == "admin":
        return
    course = await course_service.get_course(db, quiz.course_id)
    if course and course.owner_id == user.id:
        return
    if user.role == "student" and await course_service.get_enrollment(db, user.id, quiz.course_id):
        return
    raise ForbiddenError("Join this course to take its quizzes.", details=None)


async def _check_quiz_owner(db: AsyncSession, user: User, quiz) -> None:
    """Only the course teacher (or an admin) may change a quiz."""
    if user.role == "admin":
        return
    if user.role != "teacher":
        raise ForbiddenError("Only the course teacher can change this quiz.", details=None)
    if quiz.course_id is not None:
        course = await course_service.get_course(db, quiz.course_id)
        if not course or course.owner_id != user.id:
            raise ForbiddenError("Only the course teacher can change this quiz.", details=None)


async def _get_quiz_or_404(db: AsyncSession, quiz_id: int):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    return quiz


def _attempt_to_response(a, results=None):
    return QuizAttemptResponse(
        id=str(a.id),
        quizId=str(a.quiz_id),
        score=a.score,
        startedAt=a.started_at.isoformat() if a.started_at else "",
        submittedAt=a.submitted_at.isoformat() if a.submitted_at else None,
        correctCount=sum(1 for r in results if r.isCorrect) if results is not None else None,
        totalQuestions=len(results) if results is not None else None,
        results=results,
    )


@router.get("", response_model=PaginatedResponse[QuizResponse])
async def list_quizzes(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    course_id: int | None = None,
):
    """Quizzes of the courses the user belongs to (paginated), with the user's attempts."""
    stmt = select(Quiz)
    allowed = await _visible_course_ids(db, user)
    if course_id is not None:
        if allowed is not None and course_id not in allowed:
            raise ForbiddenError("Join this course to see its quizzes.", details=None)
        stmt = stmt.where(Quiz.course_id == course_id)
    elif allowed is not None:
        stmt = stmt.where(Quiz.course_id.in_(allowed or [-1]))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    quizzes = (await db.execute(
        stmt.order_by(Quiz.created_at.desc(), Quiz.id.desc()).limit(pagination.limit).offset(pagination.offset)
    )).scalars().all()

    ids = [q.id for q in quizzes] or [-1]
    counts = dict((await db.execute(
        select(QuizQuestion.quiz_id, func.count()).where(QuizQuestion.quiz_id.in_(ids)).group_by(QuizQuestion.quiz_id)
    )).all())
    mine = {
        row[0]: (row[1], row[2])
        for row in (await db.execute(
            select(QuizAttempt.quiz_id, func.count(), func.max(QuizAttempt.score))
            .where(QuizAttempt.quiz_id.in_(ids), QuizAttempt.user_id == user.id, QuizAttempt.submitted_at.is_not(None))
            .group_by(QuizAttempt.quiz_id)
        )).all()
    }
    return PaginatedResponse(
        items=[_quiz_to_response(q, counts.get(q.id, 0), *mine.get(q.id, (0, None))) for q in quizzes],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=QuizDetailResponse, status_code=201)
async def create_quiz(
    body: QuizCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a quiz with its questions (course teacher only). Students are notified."""
    course = await course_service.get_course(db, body.courseId)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    if user.role != "admin" and not (user.role == "teacher" and course.owner_id == user.id):
        raise ForbiddenError("Only the course teacher can add quizzes.", details=None)
    for i, q in enumerate(body.questions, start=1):
        try:
            options = json.loads(q.optionsJson)
        except json.JSONDecodeError:
            options = None
        if not isinstance(options, list) or len(options) < 2 or not all(isinstance(o, str) and o.strip() for o in options):
            raise ValidationError(f"Question {i}: give at least two non-empty options.", details=None)
        if q.correctIndex >= len(options):
            raise ValidationError(f"Question {i}: pick which option is correct.", details=None)

    quiz = Quiz(
        course_id=body.courseId,
        title=body.title.strip(),
        description=body.description,
        duration_minutes=body.durationMinutes,
        passing_score=body.passingScore,
        topic=body.topic or None,
    )
    db.add(quiz)
    await db.flush()
    questions = []
    for i, q in enumerate(body.questions):
        row = QuizQuestion(
            quiz_id=quiz.id,
            question_text=q.questionText.strip(),
            options_json=q.optionsJson,
            correct_index=q.correctIndex,
            sort_order=i,
            topic=q.topic or None,
            difficulty=q.difficulty,
            explanation=q.explanation or None,
        )
        db.add(row)
        questions.append(row)
    await db.flush()
    author = user.full_name or "Instructor"
    await course_service.create_stream_item(
        db, course_id=body.courseId, description=quiz.title, author=author,
        type="quiz", title=f"{author} posted a new quiz:",
    )
    await course_service.notify_course_students(
        db, body.courseId, "quiz", "New quiz", f"{quiz.title} ({len(questions)} questions)"
    )
    await db.commit()
    return QuizDetailResponse(
        **_quiz_to_response(quiz, len(questions)).model_dump(),
        questions=[_question_to_response(q) for q in questions],
    )


@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(
    quiz_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a quiz with its questions and attempts (course teacher only)."""
    quiz = await _get_quiz_or_404(db, quiz_id)
    await _check_quiz_owner(db, user, quiz)
    await db.delete(quiz)
    await db.commit()


# Declared before /{quiz_id}: FastAPI matches routes in order, and /{quiz_id} would
# otherwise capture "peer-comparison" and reject it as a non-integer (422).
@router.get("/peer-comparison", response_model=PeerComparisonResponse)
async def peer_comparison(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the current user's score percentile against all peers."""
    return await quiz_service.get_peer_comparison(db, user.id)


@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get quiz with questions. Correct answers are included only for teachers and admins."""
    quiz, questions = await quiz_service.get_quiz_with_questions(db, quiz_id)
    if not quiz:
        raise NotFoundError("Quiz not found.", details=None)
    await _check_quiz_access(db, user, quiz)
    return QuizDetailResponse(
        **_quiz_to_response(quiz, len(questions)).model_dump(),
        questions=[_question_to_response(q, include_answer=user.role in ("admin", "teacher")) for q in questions],
    )


@router.post("/{quiz_id}/attempts", response_model=QuizAttemptResponse, status_code=201)
async def start_attempt(
    quiz_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Start a quiz attempt."""
    await _check_quiz_access(db, user, await _get_quiz_or_404(db, quiz_id))
    a = await quiz_service.start_attempt(db, user.id, quiz_id)
    if not a:
        raise NotFoundError("Quiz not found.", details=None)
    await db.commit()
    return _attempt_to_response(a)


@router.post("/{quiz_id}/attempts/{attempt_id}/submit", response_model=QuizAttemptResponse)
async def submit_attempt(
    quiz_id: int,
    attempt_id: int,
    body: QuizAttemptSubmitRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit answers. The server grades them and returns the score with per-question results."""
    attempt, results = await quiz_service.submit_attempt(
        db, quiz_id, attempt_id, user.id, answers=body.answers
    )
    await db.commit()
    # Tell the course teacher when this attempt drops the student below the at-risk threshold.
    from saarthi_backend.service import progress_service
    if await progress_service.alert_if_at_risk(db, user, await _get_quiz_or_404(db, quiz_id)):
        await db.commit()
    return _attempt_to_response(attempt, results)


@router.post("/{quiz_id}/questions", response_model=QuizQuestionResponse, status_code=201)
async def create_question(
    quiz_id: int,
    body: QuizQuestionCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a quiz question (course teacher only)."""
    await _check_quiz_owner(db, user, await _get_quiz_or_404(db, quiz_id))
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
    q.topic, q.difficulty, q.explanation = body.topic or None, body.difficulty, body.explanation or None
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
    """Update a quiz question (course teacher only)."""
    await _check_quiz_owner(db, user, await _get_quiz_or_404(db, quiz_id))
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
    if body.topic is not None:
        updated.topic = body.topic or None
    if body.difficulty is not None:
        updated.difficulty = body.difficulty
    if body.explanation is not None:
        updated.explanation = body.explanation or None
    await db.commit()
    return _question_to_response(updated)


@router.delete("/{quiz_id}/questions/{question_id}", status_code=204)
async def delete_question(
    quiz_id: int,
    question_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a quiz question (course teacher only)."""
    await _check_quiz_owner(db, user, await _get_quiz_or_404(db, quiz_id))
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
        items=[_attempt_to_response(a) for a in attempts],
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


# ─── Grounded MCQ generation (AI WBS 3.5.1) ──────────────────────────────────

from pydantic import BaseModel, Field  # noqa: E402


class GroundedMCQRequest(BaseModel):
    courseId: int
    topic: str = Field(..., min_length=2, max_length=200)
    numQuestions: int = Field(5, ge=1, le=10)
    level: str = Field("L1", pattern="^L[123]$", description="L1 recall · L2 application · L3 analysis")
    materialTitle: str | None = None


@router.post("/generate-grounded")
async def generate_grounded_mcqs(
    body: GroundedMCQRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """MCQs written only from this course's indexed materials; every question cites its
    source excerpt. Returned with reviewed=false — instructors approve before use (spec 7.3)."""
    from fastapi.concurrency import run_in_threadpool
    from src.experts.mcq import generate_mcqs

    return await run_in_threadpool(
        lambda: generate_mcqs(
            body.topic, course_id=body.courseId, n=body.numQuestions, level=body.level,
            material_title=body.materialTitle,
        )
    )
