"""Courses, enrollments, assignments, materials, stream (under /api/courses)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import (
    AssignmentDAO,
    AssignmentSubmissionDAO,
    CourseDAO,
    EnrollmentDAO,
    MaterialDAO,
    StreamItemDAO,
)
from saarthi_backend.dao.course_dao import count_course_people, list_course_people
from saarthi_backend.dao.notification_dao import NotificationDAO
from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.course_schemas import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentSubmitRequest,
    AssignmentUpdate,
    CourseCreate,
    CoursePersonResponse,
    CourseResponse,
    EnrollmentResponse,
    EnrollmentWithCourseResponse,
    MaterialCreate,
    MaterialResponse,
    MaterialUpdate,
    StreamItemCreate,
    StreamItemResponse,
    StreamItemUpdate,
)
from saarthi_backend.schema.pagination_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.utils.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/courses", tags=["courses"])


def _course_to_response(c):
    return CourseResponse(
        id=str(c.id),
        title=c.title,
        code=c.code,
        instructor=c.instructor,
        description=c.description,
        thumbnailEmoji=c.thumbnail_emoji,
        color=c.color,
    )


def _assignment_to_response(a):
    return AssignmentResponse(
        id=str(a.id),
        courseId=str(a.course_id),
        title=a.title,
        description=a.description,
        dueDate=a.due_date,
        points=a.points,
        topic=a.topic,
        attachments=a.attachments,
        createdAt=a.created_at.isoformat() if a.created_at else "",
    )


def _material_to_response(m):
    return MaterialResponse(
        id=str(m.id),
        courseId=str(m.course_id),
        title=m.title,
        description=m.description,
        type=m.type,
        url=m.url,
        topic=m.topic,
        createdAt=m.created_at.isoformat() if m.created_at else "",
    )


def _stream_to_response(s):
    return StreamItemResponse(
        id=str(s.id),
        courseId=str(s.course_id),
        type=s.type,
        title=s.title,
        description=s.description,
        author=s.author,
        createdAt=s.created_at.isoformat() if s.created_at else "",
    )


# ----- Courses -----
@router.get("", response_model=PaginatedResponse[CourseResponse])
async def list_courses(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List all courses (paginated)."""
    courses = await CourseDAO.list_all(db, limit=pagination.limit, offset=pagination.offset)
    total = await CourseDAO.count_all(db)
    return PaginatedResponse(
        items=[_course_to_response(c) for c in courses],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/my/enrollments", response_model=PaginatedResponse[EnrollmentWithCourseResponse])
async def my_enrollments(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List current user's enrollments with course details (paginated)."""
    enrollments = await EnrollmentDAO.list_by_user(
        db, user.id, limit=pagination.limit, offset=pagination.offset
    )
    total = await EnrollmentDAO.count_by_user(db, user.id)
    out = []
    for e in enrollments:
        course = await CourseDAO.get_by_id(db, e.course_id)
        if not course:
            continue
        out.append(
            EnrollmentWithCourseResponse(
                id=str(e.id),
                courseId=str(e.course_id),
                progressPercent=e.progress_percent,
                lastAccessedAt=e.last_accessed_at.isoformat() if e.last_accessed_at else None,
                course=_course_to_response(course),
            )
        )
    return PaginatedResponse(
        items=out,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get course by id."""
    course = await CourseDAO.get_by_id(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    return _course_to_response(course)


@router.get("/{course_id}/people", response_model=PaginatedResponse[CoursePersonResponse])
async def list_course_people_route(
    course_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List people enrolled in the course (paginated)."""
    course = await CourseDAO.get_by_id(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    pairs = await list_course_people(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
    total = await count_course_people(db, course_id)
    return PaginatedResponse(
        items=[
            CoursePersonResponse(
                userId=str(u.id),
                fullName=u.full_name or "",
                progressPercent=e.progress_percent,
            )
            for e, u in pairs
        ],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create course (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    course = await CourseDAO.create(
        db,
        title=body.title,
        code=body.code,
        instructor=body.instructor,
        description=body.description,
        thumbnail_emoji=body.thumbnailEmoji,
        color=body.color,
    )
    await db.commit()
    return _course_to_response(course)


# ----- Enrollments -----
@router.post("/{course_id}/enroll", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll(
    course_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Enroll current user in course."""
    course = await CourseDAO.get_by_id(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    existing = await EnrollmentDAO.get(db, user.id, course_id)
    if existing:
        return EnrollmentResponse(
            id=str(existing.id),
            courseId=str(existing.course_id),
            progressPercent=existing.progress_percent,
            lastAccessedAt=existing.last_accessed_at.isoformat() if existing.last_accessed_at else None,
        )
    enrollment = await EnrollmentDAO.create(db, user.id, course_id)
    await db.commit()
    return EnrollmentResponse(
        id=str(enrollment.id),
        courseId=str(enrollment.course_id),
        progressPercent=enrollment.progress_percent,
        lastAccessedAt=enrollment.last_accessed_at.isoformat() if enrollment.last_accessed_at else None,
    )


# ----- Assignments -----
@router.get("/{course_id}/assignments", response_model=PaginatedResponse[AssignmentResponse])
async def list_assignments(
    course_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List assignments for a course (paginated)."""
    assignments = await AssignmentDAO.list_by_course(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
    total = await AssignmentDAO.count_by_course(db, course_id)
    return PaginatedResponse(
        items=[_assignment_to_response(a) for a in assignments],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("/{course_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    course_id: int,
    body: AssignmentCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create assignment (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    course = await CourseDAO.get_by_id(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    a = await AssignmentDAO.create(
        db,
        course_id=course_id,
        title=body.title,
        due_date=body.dueDate,
        description=body.description,
        points=body.points,
        topic=body.topic,
        attachments=body.attachments,
    )
    enrollments = await EnrollmentDAO.list_by_course(db, course_id, limit=10_000, offset=0)
    for e in enrollments:
        await NotificationDAO.create(
            db,
            user_id=e.user_id,
            type="assignment",
            title="New assignment",
            body=f"{a.title} (due {a.due_date})",
            link=f"/courses/{course_id}/assignments/{a.id}",
        )
    await db.commit()
    return _assignment_to_response(a)


@router.patch("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    course_id: int,
    assignment_id: int,
    body: AssignmentUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update assignment (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    assignment = await AssignmentDAO.get_by_id(db, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise NotFoundError("Assignment not found.", details=None)
    updated = await AssignmentDAO.update(
        db,
        assignment_id,
        title=body.title,
        description=body.description,
        due_date=body.dueDate,
        points=body.points,
        topic=body.topic,
        attachments=body.attachments,
    )
    await db.commit()
    return _assignment_to_response(updated)


@router.delete("/{course_id}/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    course_id: int,
    assignment_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete assignment (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    assignment = await AssignmentDAO.get_by_id(db, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise NotFoundError("Assignment not found.", details=None)
    await AssignmentDAO.delete(db, assignment_id)
    await db.commit()


@router.post("/{course_id}/assignments/{assignment_id}/submit", response_model=dict)
async def submit_assignment(
    course_id: int,
    assignment_id: int,
    body: AssignmentSubmitRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit assignment for current user."""
    assignment = await AssignmentDAO.get_by_id(db, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise NotFoundError("Assignment not found.", details=None)
    sub = await AssignmentSubmissionDAO.create_or_update(
        db,
        user.id,
        assignment_id,
        status="submitted",
        attachment_url=body.attachmentUrl,
    )
    await db.commit()
    return {"success": True, "submissionId": str(sub.id)}


# ----- Materials -----
@router.get("/{course_id}/materials", response_model=PaginatedResponse[MaterialResponse])
async def list_materials(
    course_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List materials for a course (paginated)."""
    materials = await MaterialDAO.list_by_course(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
    total = await MaterialDAO.count_by_course(db, course_id)
    return PaginatedResponse(
        items=[_material_to_response(m) for m in materials],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("/{course_id}/materials", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    course_id: int,
    body: MaterialCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create material (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    course = await CourseDAO.get_by_id(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    m = await MaterialDAO.create(
        db,
        course_id=course_id,
        title=body.title,
        type=body.type,
        url=body.url,
        description=body.description,
        topic=body.topic,
    )
    await db.commit()
    return _material_to_response(m)


@router.patch("/{course_id}/materials/{material_id}", response_model=MaterialResponse)
async def update_material(
    course_id: int,
    material_id: int,
    body: MaterialUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update material (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    material = await MaterialDAO.get_by_id(db, material_id)
    if not material or material.course_id != course_id:
        raise NotFoundError("Material not found.", details=None)
    updated = await MaterialDAO.update(
        db,
        material_id,
        title=body.title,
        description=body.description,
        type=body.type,
        url=body.url,
        topic=body.topic,
    )
    await db.commit()
    return _material_to_response(updated)


@router.delete("/{course_id}/materials/{material_id}", status_code=204)
async def delete_material(
    course_id: int,
    material_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete material (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    material = await MaterialDAO.get_by_id(db, material_id)
    if not material or material.course_id != course_id:
        raise NotFoundError("Material not found.", details=None)
    await MaterialDAO.delete(db, material_id)
    await db.commit()


# ----- Stream -----
@router.get("/{course_id}/stream", response_model=PaginatedResponse[StreamItemResponse])
async def list_stream(
    course_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List stream/announcements for a course (paginated)."""
    items = await StreamItemDAO.list_by_course(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
    total = await StreamItemDAO.count_by_course(db, course_id)
    return PaginatedResponse(
        items=[_stream_to_response(s) for s in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("/{course_id}/stream", response_model=StreamItemResponse, status_code=status.HTTP_201_CREATED)
async def create_stream_item(
    course_id: int,
    body: StreamItemCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create announcement (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    course = await CourseDAO.get_by_id(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    s = await StreamItemDAO.create(
        db,
        course_id=course_id,
        description=body.description,
        author=user.full_name,
        type=body.type,
        title=body.title,
    )
    await db.commit()
    return _stream_to_response(s)


@router.patch("/{course_id}/stream/{item_id}", response_model=StreamItemResponse)
async def update_stream_item(
    course_id: int,
    item_id: int,
    body: StreamItemUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update stream item (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    item = await StreamItemDAO.get_by_id(db, item_id)
    if not item or item.course_id != course_id:
        raise NotFoundError("Stream item not found.", details=None)
    updated = await StreamItemDAO.update(
        db,
        item_id,
        title=body.title,
        description=body.description,
        type=body.type,
    )
    await db.commit()
    return _stream_to_response(updated)


@router.delete("/{course_id}/stream/{item_id}", status_code=204)
async def delete_stream_item(
    course_id: int,
    item_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete stream item (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    item = await StreamItemDAO.get_by_id(db, item_id)
    if not item or item.course_id != course_id:
        raise NotFoundError("Stream item not found.", details=None)
    await StreamItemDAO.delete(db, item_id)
    await db.commit()
