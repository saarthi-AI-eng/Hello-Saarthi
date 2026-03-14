"""User profile and progress: GET /me, GET /me/progress, PATCH /me (under /api/users)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import EnrollmentDAO, UserDAO
from saarthi_backend.dao.course_dao import count_pending_assignments_for_user
from saarthi_backend.dao.quiz_dao import QuizAttemptDAO
from saarthi_backend.deps import get_current_user, get_db
from saarthi_backend.model import User
from saarthi_backend.schema.progress_schemas import ProgressResponse
from saarthi_backend.schema.user_schemas import UserProfileResponse, UserProfileUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _user_to_profile_response(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        fullName=user.full_name,
        name=user.full_name,
        role=user.role,
        institute=user.institute,
        bio=user.bio,
        avatar=user.avatar_url,
    )


@router.get("/me/progress", response_model=ProgressResponse)
async def get_my_progress(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dashboard stats: courses enrolled, pending assignments, avg quiz score, study time, streak."""
    enrollments = await EnrollmentDAO.list_by_user(db, user.id)
    pending = await count_pending_assignments_for_user(db, user.id)
    attempts = await QuizAttemptDAO.list_by_user(db, user.id, submitted_only=True)
    avg_score = 0.0
    if attempts:
        total = sum(a.score for a in attempts if a.score is not None)
        count = sum(1 for a in attempts if a.score is not None)
        avg_score = round(total / count, 1) if count else 0.0
    return ProgressResponse(
        coursesEnrolled=len(enrollments),
        pendingAssignments=pending,
        avgQuizScorePercent=avg_score,
        studyTimeHours=0.0,
        streakDays=0,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return current user profile (full)."""
    return _user_to_profile_response(user)


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    body: UserProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update current user profile."""
    updated = await UserDAO.update_profile(
        db,
        user.id,
        full_name=body.fullName,
        institute=body.institute,
        bio=body.bio,
        avatar_url=body.avatarUrl,
    )
    await db.commit()
    return _user_to_profile_response(updated)
