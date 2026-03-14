"""DAO for courses, enrollments, assignments, materials, stream. Includes search (courses, materials, videos)."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import (
    Assignment,
    AssignmentSubmission,
    Course,
    Enrollment,
    Material,
    StreamItem,
    User,
    Video,
)


async def count_pending_assignments_for_user(db: AsyncSession, user_id: int) -> int:
    """Count assignments in user's enrolled courses that are not submitted (or status pending)."""
    enrollments = await EnrollmentDAO.list_by_user(db, user_id, limit=10_000, offset=0)
    course_ids = [e.course_id for e in enrollments]
    if not course_ids:
        return 0
    # All assignments in those courses
    result = await db.execute(
        select(Assignment).where(Assignment.course_id.in_(course_ids))
    )
    assignments = list(result.scalars().all())
    pending = 0
    for a in assignments:
        sub = await AssignmentSubmissionDAO.get(db, user_id, a.id)
        if not sub or sub.status != "submitted":
            pending += 1
    return pending


class CourseDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, course_id: int) -> Course | None:
        result = await db.execute(select(Course).where(Course.id == course_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        db: AsyncSession, limit: int = 100, offset: int = 0
    ) -> list[Course]:
        result = await db.execute(
            select(Course).order_by(Course.id).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_all(db: AsyncSession) -> int:
        r = await db.execute(select(func.count()).select_from(Course))
        return r.scalar() or 0

    @staticmethod
    async def create(
        db: AsyncSession,
        title: str,
        code: str,
        instructor: str,
        description: str | None = None,
        thumbnail_emoji: str | None = None,
        color: str | None = None,
    ) -> Course:
        c = Course(
            title=title,
            code=code,
            instructor=instructor,
            description=description,
            thumbnail_emoji=thumbnail_emoji,
            color=color,
        )
        db.add(c)
        await db.flush()
        await db.refresh(c)
        return c


class EnrollmentDAO:
    @staticmethod
    async def get(db: AsyncSession, user_id: int, course_id: int) -> Enrollment | None:
        result = await db.execute(
            select(Enrollment).where(
                Enrollment.user_id == user_id,
                Enrollment.course_id == course_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        db: AsyncSession, user_id: int, limit: int = 100, offset: int = 0
    ) -> list[Enrollment]:
        result = await db.execute(
            select(Enrollment)
            .where(Enrollment.user_id == user_id)
            .order_by(Enrollment.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_user(db: AsyncSession, user_id: int) -> int:
        r = await db.execute(
            select(func.count()).select_from(Enrollment).where(Enrollment.user_id == user_id)
        )
        return r.scalar() or 0

    @staticmethod
    async def list_by_course(
        db: AsyncSession, course_id: int, limit: int = 100, offset: int = 0
    ) -> list[Enrollment]:
        result = await db.execute(
            select(Enrollment)
            .where(Enrollment.course_id == course_id)
            .order_by(Enrollment.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_course(db: AsyncSession, course_id: int) -> int:
        r = await db.execute(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.course_id == course_id)
        )
        return r.scalar() or 0

    @staticmethod
    async def create(db: AsyncSession, user_id: int, course_id: int) -> Enrollment:
        e = Enrollment(user_id=user_id, course_id=course_id)
        db.add(e)
        await db.flush()
        await db.refresh(e)
        return e

    @staticmethod
    async def update_progress(
        db: AsyncSession, user_id: int, course_id: int, progress_percent: float
    ) -> None:
        e = await EnrollmentDAO.get(db, user_id, course_id)
        if e:
            e.progress_percent = progress_percent
            await db.flush()


async def list_course_people(
    db: AsyncSession, course_id: int, limit: int = 100, offset: int = 0
) -> list[tuple[Enrollment, User]]:
    """Return (Enrollment, User) for each enrolled user in the course."""
    result = await db.execute(
        select(Enrollment, User)
        .join(User, Enrollment.user_id == User.id)
        .where(Enrollment.course_id == course_id)
        .order_by(Enrollment.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.all())


async def count_course_people(db: AsyncSession, course_id: int) -> int:
    r = await db.execute(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.course_id == course_id)
    )
    return r.scalar() or 0


class AssignmentDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, assignment_id: int) -> Assignment | None:
        result = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_course(
        db: AsyncSession, course_id: int, limit: int = 100, offset: int = 0
    ) -> list[Assignment]:
        result = await db.execute(
            select(Assignment)
            .where(Assignment.course_id == course_id)
            .order_by(Assignment.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_course(db: AsyncSession, course_id: int) -> int:
        r = await db.execute(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.course_id == course_id)
        )
        return r.scalar() or 0

    @staticmethod
    async def create(
        db: AsyncSession,
        course_id: int,
        title: str,
        due_date: str,
        description: str | None = None,
        points: int = 100,
        topic: str | None = None,
        attachments: str | None = None,
    ) -> Assignment:
        a = Assignment(
            course_id=course_id,
            title=title,
            description=description,
            due_date=due_date,
            points=points,
            topic=topic,
            attachments=attachments,
        )
        db.add(a)
        await db.flush()
        await db.refresh(a)
        return a

    @staticmethod
    async def update(
        db: AsyncSession,
        assignment_id: int,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        points: int | None = None,
        topic: str | None = None,
        attachments: str | None = None,
    ) -> Assignment | None:
        a = await AssignmentDAO.get_by_id(db, assignment_id)
        if not a:
            return None
        if title is not None:
            a.title = title
        if description is not None:
            a.description = description
        if due_date is not None:
            a.due_date = due_date
        if points is not None:
            a.points = points
        if topic is not None:
            a.topic = topic
        if attachments is not None:
            a.attachments = attachments
        await db.flush()
        await db.refresh(a)
        return a

    @staticmethod
    async def delete(db: AsyncSession, assignment_id: int) -> bool:
        a = await AssignmentDAO.get_by_id(db, assignment_id)
        if a:
            await db.delete(a)
            await db.flush()
            return True
        return False


class AssignmentSubmissionDAO:
    @staticmethod
    async def get(db: AsyncSession, user_id: int, assignment_id: int) -> AssignmentSubmission | None:
        result = await db.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.user_id == user_id,
                AssignmentSubmission.assignment_id == assignment_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_or_update(
        db: AsyncSession,
        user_id: int,
        assignment_id: int,
        status: str = "submitted",
        attachment_url: str | None = None,
    ) -> AssignmentSubmission:
        from datetime import datetime, timezone

        sub = await AssignmentSubmissionDAO.get(db, user_id, assignment_id)
        if sub:
            sub.status = status
            sub.submitted_at = datetime.now(timezone.utc)
            if attachment_url is not None:
                sub.attachment_url = attachment_url
            await db.flush()
            await db.refresh(sub)
            return sub
        sub = AssignmentSubmission(
            user_id=user_id,
            assignment_id=assignment_id,
            status=status,
            attachment_url=attachment_url,
        )
        db.add(sub)
        await db.flush()
        await db.refresh(sub)
        return sub


class MaterialDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, material_id: int) -> Material | None:
        result = await db.execute(select(Material).where(Material.id == material_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_course(
        db: AsyncSession, course_id: int, limit: int = 100, offset: int = 0
    ) -> list[Material]:
        result = await db.execute(
            select(Material)
            .where(Material.course_id == course_id)
            .order_by(Material.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_course(db: AsyncSession, course_id: int) -> int:
        r = await db.execute(
            select(func.count())
            .select_from(Material)
            .where(Material.course_id == course_id)
        )
        return r.scalar() or 0

    @staticmethod
    async def create(
        db: AsyncSession,
        course_id: int,
        title: str,
        type: str,
        url: str,
        description: str | None = None,
        topic: str | None = None,
    ) -> Material:
        m = Material(
            course_id=course_id,
            title=title,
            description=description,
            type=type,
            url=url,
            topic=topic,
        )
        db.add(m)
        await db.flush()
        await db.refresh(m)
        return m

    @staticmethod
    async def update(
        db: AsyncSession,
        material_id: int,
        title: str | None = None,
        description: str | None = None,
        type: str | None = None,
        url: str | None = None,
        topic: str | None = None,
    ) -> Material | None:
        m = await MaterialDAO.get_by_id(db, material_id)
        if not m:
            return None
        if title is not None:
            m.title = title
        if description is not None:
            m.description = description
        if type is not None:
            m.type = type
        if url is not None:
            m.url = url
        if topic is not None:
            m.topic = topic
        await db.flush()
        await db.refresh(m)
        return m

    @staticmethod
    async def delete(db: AsyncSession, material_id: int) -> bool:
        m = await MaterialDAO.get_by_id(db, material_id)
        if m:
            await db.delete(m)
            await db.flush()
            return True
        return False


class StreamItemDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, item_id: int) -> StreamItem | None:
        result = await db.execute(select(StreamItem).where(StreamItem.id == item_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_course(
        db: AsyncSession, course_id: int, limit: int = 50, offset: int = 0
    ) -> list[StreamItem]:
        result = await db.execute(
            select(StreamItem)
            .where(StreamItem.course_id == course_id)
            .order_by(StreamItem.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_course(db: AsyncSession, course_id: int) -> int:
        r = await db.execute(
            select(func.count())
            .select_from(StreamItem)
            .where(StreamItem.course_id == course_id)
        )
        return r.scalar() or 0

    @staticmethod
    async def create(
        db: AsyncSession,
        course_id: int,
        description: str,
        author: str,
        type: str = "announcement",
        title: str | None = None,
    ) -> StreamItem:
        s = StreamItem(
            course_id=course_id,
            type=type,
            title=title,
            description=description,
            author=author,
        )
        db.add(s)
        await db.flush()
        await db.refresh(s)
        return s

    @staticmethod
    async def update(
        db: AsyncSession,
        item_id: int,
        title: str | None = None,
        description: str | None = None,
        type: str | None = None,
    ) -> StreamItem | None:
        s = await StreamItemDAO.get_by_id(db, item_id)
        if not s:
            return None
        if title is not None:
            s.title = title
        if description is not None:
            s.description = description
        if type is not None:
            s.type = type
        await db.flush()
        await db.refresh(s)
        return s

    @staticmethod
    async def delete(db: AsyncSession, item_id: int) -> bool:
        s = await StreamItemDAO.get_by_id(db, item_id)
        if s:
            await db.delete(s)
            await db.flush()
            return True
        return False


# ----- Search (no dedicated search_dao; lives under course domain) -----
def _course_filter(term: str):
    return or_(Course.title.ilike(term), Course.code.ilike(term))


async def search(
    db: AsyncSession,
    q: str,
    limit_per_type: int = 20,
    offset_per_type: int = 0,
) -> tuple[list[Course], list[Material], list[Video], int, int, int]:
    """Search courses, materials, videos. Returns (courses, materials, videos, total_courses, total_materials, total_videos)."""
    term = f"%{q.strip()}%" if q else "%"
    tc = await db.execute(select(func.count()).select_from(Course).where(_course_filter(term)))
    tm = await db.execute(select(func.count()).select_from(Material).where(Material.title.ilike(term)))
    tv = await db.execute(select(func.count()).select_from(Video).where(Video.title.ilike(term)))
    total_courses = tc.scalar() or 0
    total_materials = tm.scalar() or 0
    total_videos = tv.scalar() or 0
    courses = await db.execute(
        select(Course)
        .where(_course_filter(term))
        .order_by(Course.id)
        .limit(limit_per_type)
        .offset(offset_per_type)
    )
    materials = await db.execute(
        select(Material)
        .where(Material.title.ilike(term))
        .order_by(Material.id)
        .limit(limit_per_type)
        .offset(offset_per_type)
    )
    videos = await db.execute(
        select(Video)
        .where(Video.title.ilike(term))
        .order_by(Video.id)
        .limit(limit_per_type)
        .offset(offset_per_type)
    )
    return (
        list(courses.scalars().all()),
        list(materials.scalars().all()),
        list(videos.scalars().all()),
        total_courses,
        total_materials,
        total_videos,
    )
