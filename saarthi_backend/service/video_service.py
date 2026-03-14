"""Video feature service: videos, progress, video notes."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import VideoDAO, VideoNoteDAO, VideoProgressDAO
from saarthi_backend.model import Video, VideoNote, VideoProgress


async def list_videos(
    db: AsyncSession,
    course_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Video], int]:
    items = await VideoDAO.list_all(db, course_id=course_id, limit=limit, offset=offset)
    total = await VideoDAO.count_all(db, course_id=course_id)
    return items, total


async def get_video(db: AsyncSession, video_id: int) -> Video | None:
    return await VideoDAO.get_by_id(db, video_id)


async def create_video(
    db: AsyncSession,
    title: str,
    url: str,
    duration_seconds: int = 0,
    course_id: int | None = None,
    description: str | None = None,
    thumbnail_url: str | None = None,
    embed_url: str | None = None,
    chapters_json: str | None = None,
    sort_order: int = 0,
) -> Video:
    return await VideoDAO.create(
        db,
        title=title,
        url=url,
        duration_seconds=duration_seconds,
        course_id=course_id,
        description=description,
        thumbnail_url=thumbnail_url,
        embed_url=embed_url,
        chapters_json=chapters_json,
        sort_order=sort_order,
    )


async def delete_video(db: AsyncSession, video_id: int) -> bool:
    return await VideoDAO.delete(db, video_id)


async def get_progress(
    db: AsyncSession, user_id: int, video_id: int
) -> VideoProgress | None:
    return await VideoProgressDAO.get(db, user_id, video_id)


async def upsert_progress(
    db: AsyncSession,
    user_id: int,
    video_id: int,
    position_seconds: int = 0,
    completed: bool = False,
) -> VideoProgress:
    return await VideoProgressDAO.upsert(
        db, user_id, video_id, position_seconds=position_seconds, completed=completed
    )


async def list_video_notes(
    db: AsyncSession, user_id: int, video_id: int
) -> list[VideoNote]:
    return await VideoNoteDAO.list_by_video_user(db, user_id, video_id)


async def create_video_note(
    db: AsyncSession,
    user_id: int,
    video_id: int,
    time_seconds: int,
    text: str,
) -> VideoNote:
    return await VideoNoteDAO.create(db, user_id, video_id, time_seconds=time_seconds, text=text)


async def delete_video_note(db: AsyncSession, note_id: int, user_id: int) -> bool:
    return await VideoNoteDAO.delete(db, note_id, user_id)
