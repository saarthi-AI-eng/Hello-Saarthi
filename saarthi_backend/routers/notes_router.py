"""Standalone notes (under /api/notes)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import NoteDAO
from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.note_schemas import NoteCreate, NoteResponse, NoteUpdate
from saarthi_backend.schema.pagination_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.utils.exceptions import NotFoundError

router = APIRouter(prefix="/notes", tags=["notes"])


def _note_to_response(n):
    return NoteResponse(
        id=str(n.id),
        title=n.title,
        content=n.content,
        courseId=str(n.course_id) if n.course_id else None,
        topic=n.topic,
        createdAt=n.created_at.isoformat() if n.created_at else "",
        updatedAt=n.updated_at.isoformat() if n.updated_at else "",
    )


@router.get("", response_model=PaginatedResponse[NoteResponse])
async def list_notes(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    course_id: int | None = None,
):
    """List current user's notes, optionally by course (paginated)."""
    notes = await NoteDAO.list_by_user(
        db,
        user.id,
        course_id=course_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    total = await NoteDAO.count_by_user(db, user.id, course_id=course_id)
    return PaginatedResponse(
        items=[_note_to_response(n) for n in notes],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create note."""
    n = await NoteDAO.create(
        db,
        user.id,
        title=body.title,
        content=body.content,
        course_id=body.courseId,
        topic=body.topic,
    )
    await db.commit()
    return _note_to_response(n)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get note by id (own only)."""
    n = await NoteDAO.get_by_id(db, note_id)
    if not n or n.user_id != user.id:
        raise NotFoundError("Note not found.", details=None)
    return _note_to_response(n)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    body: NoteUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update note (own only)."""
    n = await NoteDAO.update(db, note_id, user.id, title=body.title, content=body.content)
    if not n:
        raise NotFoundError("Note not found.", details=None)
    await db.commit()
    return _note_to_response(n)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete note (own only)."""
    deleted = await NoteDAO.delete(db, note_id, user.id)
    if deleted:
        await db.commit()
    return None
