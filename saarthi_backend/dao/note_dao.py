"""DAO for standalone notes."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import Note


class NoteDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, note_id: int) -> Note | None:
        result = await db.execute(select(Note).where(Note.id == note_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        course_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Note]:
        q = (
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if course_id is not None:
            q = q.where(Note.course_id == course_id)
        result = await db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def count_by_user(
        db: AsyncSession, user_id: int, course_id: int | None = None
    ) -> int:
        q = select(func.count()).select_from(Note).where(Note.user_id == user_id)
        if course_id is not None:
            q = q.where(Note.course_id == course_id)
        r = await db.execute(q)
        return r.scalar() or 0

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        title: str,
        content: str,
        course_id: int | None = None,
        topic: str | None = None,
    ) -> Note:
        n = Note(
            user_id=user_id,
            title=title,
            content=content,
            course_id=course_id,
            topic=topic,
        )
        db.add(n)
        await db.flush()
        await db.refresh(n)
        return n

    @staticmethod
    async def update(
        db: AsyncSession,
        note_id: int,
        user_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> Note | None:
        n = await NoteDAO.get_by_id(db, note_id)
        if not n or n.user_id != user_id:
            return None
        if title is not None:
            n.title = title
        if content is not None:
            n.content = content
        await db.flush()
        await db.refresh(n)
        return n

    @staticmethod
    async def delete(db: AsyncSession, note_id: int, user_id: int) -> bool:
        n = await NoteDAO.get_by_id(db, note_id)
        if not n or n.user_id != user_id:
            return False
        await db.delete(n)
        await db.flush()
        return True
