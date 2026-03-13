"""DAO for videos and video progress/notes."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import Video, VideoProgress, VideoNote


class VideoDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, video_id: int) -> Video | None:
        result = await db.execute(select(Video).where(Video.id == video_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        db: AsyncSession,
        course_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Video]:
        q = (
            select(Video)
            .order_by(Video.sort_order, Video.id)
            .limit(limit)
            .offset(offset)
        )
        if course_id is not None:
            q = q.where(Video.course_id == course_id)
        result = await db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def count_all(db: AsyncSession, course_id: int | None = None) -> int:
        q = select(func.count()).select_from(Video)
        if course_id is not None:
            q = q.where(Video.course_id == course_id)
        r = await db.execute(q)
        return r.scalar() or 0

    @staticmethod
    async def create(
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
        v = Video(
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
        db.add(v)
        await db.flush()
        await db.refresh(v)
        return v

    @staticmethod
    async def delete(db: AsyncSession, video_id: int) -> bool:
        """Delete video by id. Returns True if deleted. Progress/notes cascade."""
        v = await VideoDAO.get_by_id(db, video_id)
        if not v:
            return False
        await db.delete(v)
        await db.flush()
        return True


class VideoProgressDAO:
    @staticmethod
    async def get(db: AsyncSession, user_id: int, video_id: int) -> VideoProgress | None:
        result = await db.execute(
            select(VideoProgress).where(
                VideoProgress.user_id == user_id,
                VideoProgress.video_id == video_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        user_id: int,
        video_id: int,
        position_seconds: int = 0,
        completed: bool = False,
    ) -> VideoProgress:
        from datetime import datetime, timezone
        from sqlalchemy import update

        prog = await VideoProgressDAO.get(db, user_id, video_id)
        if prog:
            prog.position_seconds = position_seconds
            prog.completed = completed
            prog.updated_at = datetime.now(timezone.utc)
            await db.flush()
            await db.refresh(prog)
            return prog
        prog = VideoProgress(
            user_id=user_id,
            video_id=video_id,
            position_seconds=position_seconds,
            completed=completed,
        )
        db.add(prog)
        await db.flush()
        await db.refresh(prog)
        return prog


class VideoNoteDAO:
    @staticmethod
    async def list_by_video_user(db: AsyncSession, user_id: int, video_id: int) -> list[VideoNote]:
        result = await db.execute(
            select(VideoNote)
            .where(
                VideoNote.user_id == user_id,
                VideoNote.video_id == video_id,
            )
            .order_by(VideoNote.time_seconds)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        video_id: int,
        time_seconds: int,
        text: str,
    ) -> VideoNote:
        n = VideoNote(user_id=user_id, video_id=video_id, time_seconds=time_seconds, text=text)
        db.add(n)
        await db.flush()
        await db.refresh(n)
        return n

    @staticmethod
    async def delete(db: AsyncSession, note_id: int, user_id: int) -> bool:
        result = await db.execute(
            select(VideoNote).where(VideoNote.id == note_id, VideoNote.user_id == user_id)
        )
        n = result.scalar_one_or_none()
        if n:
            await db.delete(n)
            await db.flush()
            return True
        return False
