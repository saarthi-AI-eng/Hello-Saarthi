"""Course feature service: courses, enrollments, assignments, materials, stream, search, upload (no dedicated modules)."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import (
    AssignmentDAO,
    AssignmentSubmissionDAO,
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
) -> Course:
    return await CourseDAO.create(
        db,
        title=title,
        code=code,
        instructor=instructor,
        description=description,
        thumbnail_emoji=thumbnail_emoji,
        color=color,
    )


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
