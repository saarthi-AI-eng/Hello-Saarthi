"""Note feature service: study notes."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import NoteDAO
from saarthi_backend.model import Note


async def list_notes(
    db: AsyncSession,
    user_id: int,
    course_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Note], int]:
    items = await NoteDAO.list_by_user(db, user_id, course_id=course_id, limit=limit, offset=offset)
    total = await NoteDAO.count_by_user(db, user_id, course_id=course_id)
    return items, total


async def get_note(db: AsyncSession, note_id: int, user_id: int | None = None) -> Note | None:
    n = await NoteDAO.get_by_id(db, note_id)
    if not n:
        return None
    if user_id is not None and n.user_id != user_id:
        return None
    return n


async def create_note(
    db: AsyncSession,
    user_id: int,
    title: str,
    content: str,
    course_id: int | None = None,
    topic: str | None = None,
) -> Note:
    return await NoteDAO.create(
        db, user_id, title=title, content=content, course_id=course_id, topic=topic
    )


async def update_note(
    db: AsyncSession,
    note_id: int,
    user_id: int,
    title: str | None = None,
    content: str | None = None,
) -> Note | None:
    return await NoteDAO.update(db, note_id, user_id, title=title, content=content)


async def delete_note(db: AsyncSession, note_id: int, user_id: int) -> bool:
    return await NoteDAO.delete(db, note_id, user_id)
