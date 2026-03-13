"""Search across courses, materials, videos (paginated per type)."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import Course, Material, Video


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
    # Counts
    tc = await db.execute(select(func.count()).select_from(Course).where(_course_filter(term)))
    tm = await db.execute(select(func.count()).select_from(Material).where(Material.title.ilike(term)))
    tv = await db.execute(select(func.count()).select_from(Video).where(Video.title.ilike(term)))
    total_courses = tc.scalar() or 0
    total_materials = tm.scalar() or 0
    total_videos = tv.scalar() or 0
    # Slice per type
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
