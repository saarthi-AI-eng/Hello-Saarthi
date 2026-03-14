"""User feature service: profile and progress."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import EnrollmentDAO, UserDAO
from saarthi_backend.dao.course_dao import count_pending_assignments_for_user
from saarthi_backend.dao.quiz_dao import QuizAttemptDAO
from saarthi_backend.model import User


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await UserDAO.get_by_id(db, user_id)


async def update_profile(
    db: AsyncSession,
    user_id: int,
    full_name: str | None = None,
    institute: str | None = None,
    bio: str | None = None,
    avatar_url: str | None = None,
) -> User | None:
    return await UserDAO.update_profile(
        db,
        user_id,
        full_name=full_name,
        institute=institute,
        bio=bio,
        avatar_url=avatar_url,
    )


async def get_progress(db: AsyncSession, user_id: int) -> tuple[int, int, float]:
    """Returns (courses_enrolled, pending_assignments, avg_quiz_score_percent)."""
    enrollments = await EnrollmentDAO.list_by_user(db, user_id, limit=10_000, offset=0)
    pending = await count_pending_assignments_for_user(db, user_id)
    attempts = await QuizAttemptDAO.list_by_user(db, user_id, submitted_only=True)
    avg_score = 0.0
    if attempts:
        total = sum(a.score for a in attempts if a.score is not None)
        count = sum(1 for a in attempts if a.score is not None)
        avg_score = round(total / count, 1) if count else 0.0
    return len(enrollments), pending, avg_score
