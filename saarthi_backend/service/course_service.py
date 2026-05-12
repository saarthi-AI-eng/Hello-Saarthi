"""Course feature service: courses, enrollments, assignments, materials, stream, search, upload (no dedicated modules)."""

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import (
    AssignmentDAO,
    AssignmentSubmissionDAO,
    ClassroomInviteDAO,
    CourseDAO,
    EnrollmentDAO,
    MaterialDAO,
    StreamItemDAO,
)
from saarthi_backend.dao.course_dao import count_course_people, list_course_people, search as course_dao_search
from saarthi_backend.dao.notification_dao import NotificationDAO
from saarthi_backend.model import (
    Assignment,
    AssignmentSubmission,
    ClassroomInvite,
    Course,
    Enrollment,
    Material,
    StreamItem,
    User,
)


# ----- Courses -----
async def list_courses(
    db: AsyncSession, limit: int = 100, offset: int = 0
) -> tuple[list[Course], int]:
    items = await CourseDAO.list_all(db, limit=limit, offset=offset)
    total = await CourseDAO.count_all(db)
    return items, total


async def get_course(db: AsyncSession, course_id: int) -> Course | None:
    return await CourseDAO.get_by_id(db, course_id)


async def create_course(
    db: AsyncSession,
    title: str,
    code: str,
    instructor: str,
    description: str | None = None,
    thumbnail_emoji: str | None = None,
    color: str | None = None,
    owner_id: int | None = None,
) -> Course:
    return await CourseDAO.create(
        db,
        title=title,
        code=code,
        instructor=instructor,
        description=description,
        thumbnail_emoji=thumbnail_emoji,
        color=color,
        owner_id=owner_id,
    )


async def delete_course(db: AsyncSession, course_id: int) -> bool:
    return await CourseDAO.delete(db, course_id)


# ----- Enrollments -----
async def list_my_enrollments(
    db: AsyncSession, user_id: int, limit: int = 100, offset: int = 0
) -> tuple[list[Enrollment], int]:
    items = await EnrollmentDAO.list_by_user(db, user_id, limit=limit, offset=offset)
    total = await EnrollmentDAO.count_by_user(db, user_id)
    return items, total


async def get_enrollment(
    db: AsyncSession, user_id: int, course_id: int
) -> Enrollment | None:
    return await EnrollmentDAO.get(db, user_id, course_id)


async def enroll(db: AsyncSession, user_id: int, course_id: int) -> Enrollment:
    return await EnrollmentDAO.create(db, user_id, course_id)


async def list_course_people_paginated(
    db: AsyncSession, course_id: int, limit: int = 100, offset: int = 0
) -> tuple[list[tuple[Enrollment, User]], int]:
    pairs = await list_course_people(db, course_id, limit=limit, offset=offset)
    total = await count_course_people(db, course_id)
    return pairs, total


# ----- Assignments -----
async def list_assignments(
    db: AsyncSession, course_id: int, limit: int = 100, offset: int = 0
) -> tuple[list[Assignment], int]:
    items = await AssignmentDAO.list_by_course(db, course_id, limit=limit, offset=offset)
    total = await AssignmentDAO.count_by_course(db, course_id)
    return items, total


async def get_assignment(db: AsyncSession, assignment_id: int) -> Assignment | None:
    return await AssignmentDAO.get_by_id(db, assignment_id)


async def create_assignment(
    db: AsyncSession,
    course_id: int,
    title: str,
    due_date: str,
    description: str | None = None,
    points: int = 100,
    topic: str | None = None,
    attachments: str | None = None,
) -> Assignment:
    a = await AssignmentDAO.create(
        db,
        course_id=course_id,
        title=title,
        due_date=due_date,
        description=description,
        points=points,
        topic=topic,
        attachments=attachments,
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
    return a


async def update_assignment(
    db: AsyncSession,
    assignment_id: int,
    title: str | None = None,
    description: str | None = None,
    due_date: str | None = None,
    points: int | None = None,
    topic: str | None = None,
    attachments: str | None = None,
) -> Assignment | None:
    return await AssignmentDAO.update(
        db,
        assignment_id,
        title=title,
        description=description,
        due_date=due_date,
        points=points,
        topic=topic,
        attachments=attachments,
    )


async def delete_assignment(db: AsyncSession, assignment_id: int) -> bool:
    return await AssignmentDAO.delete(db, assignment_id)


async def submit_assignment(
    db: AsyncSession,
    user_id: int,
    assignment_id: int,
    status: str = "submitted",
    attachment_url: str | None = None,
) -> AssignmentSubmission:
    return await AssignmentSubmissionDAO.create_or_update(
        db, user_id, assignment_id, status=status, attachment_url=attachment_url
    )


# ----- Materials -----
async def list_materials(
    db: AsyncSession, course_id: int, limit: int = 100, offset: int = 0
) -> tuple[list[Material], int]:
    items = await MaterialDAO.list_by_course(db, course_id, limit=limit, offset=offset)
    total = await MaterialDAO.count_by_course(db, course_id)
    return items, total


async def get_material(db: AsyncSession, material_id: int) -> Material | None:
    return await MaterialDAO.get_by_id(db, material_id)


async def create_material(
    db: AsyncSession,
    course_id: int,
    title: str,
    type: str,
    url: str,
    description: str | None = None,
    topic: str | None = None,
) -> Material:
    return await MaterialDAO.create(
        db,
        course_id=course_id,
        title=title,
        type=type,
        url=url,
        description=description,
        topic=topic,
    )


async def update_material(
    db: AsyncSession,
    material_id: int,
    title: str | None = None,
    description: str | None = None,
    type: str | None = None,
    url: str | None = None,
    topic: str | None = None,
) -> Material | None:
    return await MaterialDAO.update(
        db, material_id, title=title, description=description, type=type, url=url, topic=topic
    )


async def delete_material(db: AsyncSession, material_id: int) -> bool:
    return await MaterialDAO.delete(db, material_id)


# ----- Stream -----
async def list_stream_items(
    db: AsyncSession, course_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[StreamItem], int]:
    items = await StreamItemDAO.list_by_course(db, course_id, limit=limit, offset=offset)
    total = await StreamItemDAO.count_by_course(db, course_id)
    return items, total


async def get_stream_item(db: AsyncSession, item_id: int) -> StreamItem | None:
    return await StreamItemDAO.get_by_id(db, item_id)


async def create_stream_item(
    db: AsyncSession,
    course_id: int,
    description: str,
    author: str,
    type: str = "announcement",
    title: str | None = None,
) -> StreamItem:
    return await StreamItemDAO.create(
        db, course_id=course_id, description=description, author=author, type=type, title=title
    )


async def update_stream_item(
    db: AsyncSession,
    item_id: int,
    title: str | None = None,
    description: str | None = None,
    type: str | None = None,
) -> StreamItem | None:
    return await StreamItemDAO.update(db, item_id, title=title, description=description, type=type)


async def delete_stream_item(db: AsyncSession, item_id: int) -> bool:
    return await StreamItemDAO.delete(db, item_id)


# ----- Search (no dedicated search_service; under course domain) -----
async def search(
    db: AsyncSession,
    q: str,
    limit_per_type: int = 20,
    offset_per_type: int = 0,
) -> tuple[list, list, list, int, int, int]:
    """Search courses, materials, videos. Returns (courses, materials, videos, total_courses, total_materials, total_videos)."""
    return await course_dao_search(db, q, limit_per_type, offset_per_type)


# ----- Scoped course listing -----

async def list_enrolled_courses(
    db: AsyncSession, user_id: int, limit: int = 100, offset: int = 0
) -> tuple[list[Course], int]:
    """Return only courses the student is enrolled in."""
    from saarthi_backend.dao.course_dao import list_courses_for_student as _dao_fn
    return await _dao_fn(db, user_id, limit=limit, offset=offset)


# ----- Classroom invites -----

_INVITE_CHARS = string.ascii_letters + string.digits


def _generate_invite_code(length: int = 10) -> str:
    return "".join(secrets.choice(_INVITE_CHARS) for _ in range(length))


async def create_invite(
    db: AsyncSession,
    course_id: int,
    invited_by: int,
    email: str,
    expires_in_hours: int = 72,
) -> ClassroomInvite:
    invite_code = _generate_invite_code()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    invite = await ClassroomInviteDAO.create(
        db,
        course_id=course_id,
        invited_by=invited_by,
        email=email.lower().strip(),
        invite_code=invite_code,
        expires_at=expires_at,
    )
    return invite


async def get_invite_by_code(db: AsyncSession, invite_code: str) -> ClassroomInvite | None:
    return await ClassroomInviteDAO.get_by_code(db, invite_code)


async def join_by_invite_code(
    db: AsyncSession, user_id: int, user_email: str, invite_code: str
) -> tuple[Enrollment, Course] | None:
    """Accept an invite and enroll the user. Returns (enrollment, course) or None if invalid."""
    invite = await ClassroomInviteDAO.get_by_code(db, invite_code)
    if not invite:
        return None
    if invite.accepted:
        return None
    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    # Invite is either addressed to this user's email or is a general open code (email="*")
    if invite.email != "*" and invite.email != user_email.lower().strip():
        return None

    course = await CourseDAO.get_by_id(db, invite.course_id)
    if not course:
        return None

    existing = await EnrollmentDAO.get(db, user_id, invite.course_id)
    if existing:
        await ClassroomInviteDAO.mark_accepted(db, invite.id)
        return existing, course

    enrollment = await EnrollmentDAO.create(db, user_id, invite.course_id)
    await ClassroomInviteDAO.mark_accepted(db, invite.id)
    return enrollment, course


async def list_course_invites(
    db: AsyncSession, course_id: int
) -> list[ClassroomInvite]:
    return await ClassroomInviteDAO.list_by_course(db, course_id)
