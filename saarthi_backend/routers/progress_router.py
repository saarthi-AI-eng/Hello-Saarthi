"""Learning analytics (under /api/progress). See saarthi_backend/service/progress_service.py."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db
from saarthi_backend.model import User
from saarthi_backend.service import progress_service
from saarthi_backend.utils.exceptions import ForbiddenError, NotFoundError

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/me")
async def my_analytics(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """The student's own learning trackers: topics, trend, weak topics, coverage, class median, badges."""
    return await progress_service.student_analytics(db, user)


async def _teacher_course(db: AsyncSession, user: User, course_id: Optional[int]):
    if user.role not in ("teacher", "admin"):
        raise ForbiddenError("Only teachers can view class performance.", details=None)
    courses = await progress_service.teacher_courses(db, user)
    if not courses:
        return courses, None
    if course_id is None:
        return courses, courses[0]
    course = next((c for c in courses if c.id == course_id), None)
    if course is None:
        raise NotFoundError("Course not found.", details=None)
    return courses, course


@router.get("/class")
async def class_performance(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    courseId: Optional[int] = Query(None),
    threshold: Optional[float] = Query(None, ge=0, le=100),
):
    """Score histogram, at-risk students, topic accuracy and most-missed questions for one of the teacher's courses."""
    courses, course = await _teacher_course(db, user, courseId)
    listing = [{"id": str(c.id), "title": c.title, "code": c.code} for c in courses]
    if course is None:
        return {"courses": listing, "performance": None}
    t = threshold if threshold is not None else progress_service.at_risk_threshold()
    return {"courses": listing, "performance": await progress_service.class_performance(db, course, t)}


@router.get("/class/export")
async def export_class(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    courseId: Optional[int] = Query(None),
    threshold: Optional[float] = Query(None, ge=0, le=100),
):
    """Class report as CSV: one row per enrolled student."""
    _, course = await _teacher_course(db, user, courseId)
    if course is None:
        raise NotFoundError("Course not found.", details=None)
    t = threshold if threshold is not None else progress_service.at_risk_threshold()
    perf = await progress_service.class_performance(db, course, t)
    name = "".join(ch if ch.isalnum() else "_" for ch in (course.code or course.title))
    return Response(
        content=progress_service.class_csv(perf),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="class_report_{name}.csv"'},
    )
