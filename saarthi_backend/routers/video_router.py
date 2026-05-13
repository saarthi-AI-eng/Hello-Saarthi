"""Videos, progress, notes (under /api/videos)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.common_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.schema.video_schemas import (
    VideoCreate,
    VideoNoteCreate,
    VideoNoteResponse,
    VideoProgressResponse,
    VideoProgressUpdate,
    VideoResponse,
    VideoTranscriptUpload,
)
from saarthi_backend.service import video_service
from saarthi_backend.utils.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/videos", tags=["videos"])


def _video_to_response(v):
    return VideoResponse(
        id=str(v.id),
        courseId=str(v.course_id) if v.course_id else None,
        title=v.title,
        description=v.description,
        durationSeconds=v.duration_seconds,
        thumbnailUrl=v.thumbnail_url,
        url=v.url,
        embedUrl=v.embed_url,
        chaptersJson=v.chapters_json,
        sortOrder=v.sort_order,
        hasTranscript=bool(v.transcript_text),
    )


def _progress_to_response(p):
    return VideoProgressResponse(
        positionSeconds=p.position_seconds,
        completed=p.completed,
        updatedAt=p.updated_at.isoformat() if p.updated_at else "",
    )


def _note_to_response(n):
    return VideoNoteResponse(
        id=str(n.id),
        videoId=str(n.video_id),
        timeSeconds=n.time_seconds,
        text=n.text,
        createdAt=n.created_at.isoformat() if n.created_at else "",
    )


@router.get("", response_model=PaginatedResponse[VideoResponse])
async def list_videos(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    course_id: int | None = None,
):
    """List videos, optionally filtered by course_id (paginated)."""
    videos, total = await video_service.list_videos(
        db, course_id=course_id, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse(
        items=[_video_to_response(v) for v in videos],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.delete("/{video_id}", status_code=204)
async def delete_video(
    video_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete video (admin/teacher). Must be declared before GET for same path."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    deleted = await video_service.delete_video(db, video_id)
    if not deleted:
        raise NotFoundError("Video not found.", details=None)
    from saarthi_backend.service.indexing_service import delete_video_transcript_index
    delete_video_transcript_index(video_id)
    await db.commit()


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get video by id (includes playback URL)."""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise NotFoundError("Video not found.", details=None)
    return _video_to_response(video)


@router.post("", response_model=VideoResponse, status_code=201)
async def create_video(
    body: VideoCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create video (admin/teacher)."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    v = await video_service.create_video(
        db,
        title=body.title,
        url=body.url,
        duration_seconds=body.durationSeconds,
        course_id=body.courseId,
        description=body.description,
        thumbnail_url=body.thumbnailUrl,
        embed_url=body.embedUrl,
        chapters_json=body.chaptersJson,
        sort_order=body.sortOrder,
    )
    await db.commit()
    # Auto-fetch YouTube transcript in background — no admin action needed
    from saarthi_backend.service.indexing_service import auto_index_youtube_video
    auto_index_youtube_video(v.id, v.title, v.url or "", v.embed_url)
    return _video_to_response(v)


# ----- Transcript -----

@router.post("/{video_id}/transcript", status_code=200)
async def upload_transcript(
    video_id: int,
    body: VideoTranscriptUpload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Upload / replace a video transcript (admin/teacher). Triggers background FAISS indexing."""
    if user.role not in ("admin", "teacher"):
        raise ValidationError("Forbidden.", details=None)
    video = await video_service.get_video(db, video_id)
    if not video:
        raise NotFoundError("Video not found.", details=None)
    video.transcript_text = body.transcriptText
    await db.commit()
    from saarthi_backend.service.indexing_service import index_video_transcript_background
    index_video_transcript_background(video_id, video.title, body.transcriptText)
    return {"status": "indexing", "videoId": video_id}


# ----- Progress -----

@router.get("/{video_id}/progress", response_model=VideoProgressResponse)
async def get_progress(
    video_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get current user's watch progress for video."""
    if not await video_service.get_video(db, video_id):
        raise NotFoundError("Video not found.", details=None)
    prog = await video_service.get_progress(db, user.id, video_id)
    if not prog:
        return VideoProgressResponse(positionSeconds=0, completed=False, updatedAt="")
    return _progress_to_response(prog)


@router.put("/{video_id}/progress", response_model=VideoProgressResponse)
async def update_progress(
    video_id: int,
    body: VideoProgressUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Upsert watch progress."""
    if not await video_service.get_video(db, video_id):
        raise NotFoundError("Video not found.", details=None)
    prog = await video_service.upsert_progress(
        db,
        user.id,
        video_id,
        position_seconds=body.positionSeconds,
        completed=body.completed,
    )
    await db.commit()
    return _progress_to_response(prog)


# ----- Notes -----

@router.get("/{video_id}/notes", response_model=list[VideoNoteResponse])
async def list_notes(
    video_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List current user's notes for video."""
    if not await video_service.get_video(db, video_id):
        raise NotFoundError("Video not found.", details=None)
    notes = await video_service.list_video_notes(db, user.id, video_id)
    return [_note_to_response(n) for n in notes]


@router.post("/{video_id}/notes", response_model=VideoNoteResponse, status_code=201)
async def create_note(
    video_id: int,
    body: VideoNoteCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add note at timestamp."""
    if not await video_service.get_video(db, video_id):
        raise NotFoundError("Video not found.", details=None)
    n = await video_service.create_video_note(
        db, user.id, video_id, time_seconds=body.timeSeconds, text=body.text
    )
    await db.commit()
    return _note_to_response(n)


@router.delete("/{video_id}/notes/{note_id}", status_code=204)
async def delete_note(
    video_id: int,
    note_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete own note."""
    deleted = await video_service.delete_video_note(db, note_id, user.id)
    if deleted:
        await db.commit()
    return None
