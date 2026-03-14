"""Courses, enrollments, assignments, materials, stream, file upload (under /api/courses)."""

import logging
import uuid
from pathlib import Path

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
    SearchItem,
    SearchResponse,
    StreamItemCreate,
    StreamItemResponse,
    StreamItemUpdate,
)
from saarthi_backend.schema.common_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.service import course_service
from saarthi_backend.utils.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/courses", tags=["courses"])
logger = logging.getLogger(__name__)

# File upload for assignment attachments (no separate upload router; one router per DAO)
_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_MAX_UPLOAD_MB = 10


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
    # For local /uploads files, expose the authenticated file route so access control isn't bypassed.
    if _uploads_filename_from_url(m.url or ""):
        download_url = f"/courses/{m.course_id}/materials/{m.id}/file"
    else:
        download_url = m.url or ""
    return MaterialResponse(
        id=str(m.id),
        courseId=str(m.course_id),
        title=m.title,
        description=m.description,
        type=m.type,
        url=download_url,
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


# ----- Search (no dedicated search_router; under course domain) -----
@router.get("/search", response_model=SearchResponse)
async def search(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    q: str = "",
):
    """Search courses, materials, videos. GET /api/courses/search?q=..."""
    courses, materials, videos, total_courses, total_materials, total_videos = await course_service.search(
        db, q, limit_per_type=pagination.limit, offset_per_type=pagination.offset
    )
    return SearchResponse(
        limit=pagination.limit,
        offset=pagination.offset,
        courses=[
            SearchItem(type="course", id=str(c.id), title=c.title, subtitle=c.code, link=f"/courses/{c.id}")
            for c in courses
        ],
        materials=[
            SearchItem(
                type="material",
                id=str(m.id),
                title=m.title,
                subtitle=m.type or "",
                link=(
                    f"/courses/{m.course_id}/materials/{m.id}/file"
                    if _uploads_filename_from_url(m.url or "")
                    else (m.url or "")
                ),
            )
            for m in materials
        ],
        videos=[
            SearchItem(type="video", id=str(v.id), title=v.title, subtitle=f"{v.duration_seconds}s", link=f"/videos/{v.id}")
            for v in videos
        ],
        totalCourses=total_courses,
        totalMaterials=total_materials,
        totalVideos=total_videos,
    )


# ----- Courses -----
@router.get("", response_model=PaginatedResponse[CourseResponse])
async def list_courses(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List all courses (paginated)."""
    courses, total = await course_service.list_courses(db, limit=pagination.limit, offset=pagination.offset)
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
    enrollments, total = await course_service.list_my_enrollments(
        db, user.id, limit=pagination.limit, offset=pagination.offset
    )
    out = []
    for e in enrollments:
        course = await course_service.get_course(db, e.course_id)
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
    course = await course_service.get_course(db, course_id)
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
    course = await course_service.get_course(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    pairs, total = await course_service.list_course_people_paginated(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
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
    course = await course_service.create_course(
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
    course = await course_service.get_course(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    existing = await course_service.get_enrollment(db, user.id, course_id)
    if existing:
        return EnrollmentResponse(
            id=str(existing.id),
            courseId=str(existing.course_id),
            progressPercent=existing.progress_percent,
            lastAccessedAt=existing.last_accessed_at.isoformat() if existing.last_accessed_at else None,
        )
    enrollment = await course_service.enroll(db, user.id, course_id)
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
    assignments, total = await course_service.list_assignments(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
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
    course = await course_service.get_course(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    a = await course_service.create_assignment(
        db,
        course_id=course_id,
        title=body.title,
        due_date=body.dueDate,
        description=body.description,
        points=body.points,
        topic=body.topic,
        attachments=body.attachments,
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
    assignment = await course_service.get_assignment(db, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise NotFoundError("Assignment not found.", details=None)
    updated = await course_service.update_assignment(
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
    assignment = await course_service.get_assignment(db, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise NotFoundError("Assignment not found.", details=None)
    await course_service.delete_assignment(db, assignment_id)
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
    assignment = await course_service.get_assignment(db, assignment_id)
    if not assignment or assignment.course_id != course_id:
        raise NotFoundError("Assignment not found.", details=None)
    sub = await course_service.submit_assignment(
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
    materials, total = await course_service.list_materials(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
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
    course = await course_service.get_course(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    m = await course_service.create_material(
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
    material = await course_service.get_material(db, material_id)
    if not material or material.course_id != course_id:
        raise NotFoundError("Material not found.", details=None)
    updated = await course_service.update_material(
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


def _uploads_filename_from_url(url: str) -> str | None:
    """Extract uploads filename from material url (e.g. /uploads/abc.pdf or http://host/uploads/abc.pdf)."""
    if not url or "/uploads/" not in url:
        return None
    parts = url.split("/uploads/", 1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    name = parts[1].split("?")[0].strip()
    if not name or ".." in name:
        return None
    return name


@router.delete("/{course_id}/materials/{material_id}", status_code=204)
async def delete_material(
    course_id: int,
    material_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete material (admin/teacher). Removes DB record and file from uploads if stored locally."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    material = await course_service.get_material(db, material_id)
    if not material or material.course_id != course_id:
        raise NotFoundError("Material not found.", details=None)
    filename = _uploads_filename_from_url(material.url or "")
    if filename:
        file_path = _UPLOAD_DIR / filename
        if file_path.is_file():
            try:
                await run_in_threadpool(file_path.unlink)
            except OSError as exc:
                logger.warning(
                    "Failed to delete material file '%s' at '%s': %s",
                    filename,
                    file_path,
                    exc,
                )
    await course_service.delete_material(db, material_id)
    await db.commit()


@router.get("/{course_id}/materials/{material_id}/file")
async def get_material_file(
    course_id: int,
    material_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream material file (PDF etc.). Requires enrollment in course or teacher/admin."""
    material = await course_service.get_material(db, material_id)
    if not material or material.course_id != course_id:
        raise NotFoundError("Material not found.", details=None)
    if user.role not in ("admin", "teacher"):
        enrollment = await course_service.get_enrollment(db, user.id, course_id)
        if not enrollment:
            raise ValidationError("You must be enrolled in this course to view materials.", details=None)
    filename = _uploads_filename_from_url(material.url or "")
    if filename:
        file_path = _UPLOAD_DIR / filename
        if file_path.is_file():
            media_type = "application/pdf" if filename.lower().endswith(".pdf") else None
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type=media_type,
                content_disposition="inline",
            )
    raise NotFoundError("File not found.", details=None)


# ----- Stream -----
@router.get("/{course_id}/stream", response_model=PaginatedResponse[StreamItemResponse])
async def list_stream(
    course_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List stream/announcements for a course (paginated)."""
    items, total = await course_service.list_stream_items(
        db, course_id, limit=pagination.limit, offset=pagination.offset
    )
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
    course = await course_service.get_course(db, course_id)
    if not course:
        raise NotFoundError("Course not found.", details=None)
    s = await course_service.create_stream_item(
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
    item = await course_service.get_stream_item(db, item_id)
    if not item or item.course_id != course_id:
        raise NotFoundError("Stream item not found.", details=None)
    updated = await course_service.update_stream_item(
        db, item_id, title=body.title, description=body.description, type=body.type
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
    item = await course_service.get_stream_item(db, item_id)
    if not item or item.course_id != course_id:
        raise NotFoundError("Stream item not found.", details=None)
    await course_service.delete_stream_item(db, item_id)
    await db.commit()


# ----- File upload (assignment attachments) -----
def _write_upload_sync(dest: Path, content: bytes) -> None:
    dest.write_bytes(content)


@router.post("/upload", response_model=dict)
async def upload_file(
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
):
    """Upload a file; returns { url: "/uploads/..." } for assignment attachments."""
    if not file.filename:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID", "message": "No filename"}},
        )
    content = await file.read()
    if len(content) > _MAX_UPLOAD_MB * 1024 * 1024:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID", "message": f"File too large (max {_MAX_UPLOAD_MB}MB)"}},
        )
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix or ""
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = _UPLOAD_DIR / safe_name
    await run_in_threadpool(_write_upload_sync, dest, content)
    return {"url": f"/uploads/{safe_name}"}
