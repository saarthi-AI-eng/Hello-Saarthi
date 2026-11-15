"""Manual QA review dashboard API — for the internal `qa_reviewer` role
(and admins). Only ever reads/writes the existing OCR/transcript JSONL
files (via src/content_qa/manual_review.py) plus one new audit table;
never touches Qdrant, embeddings, or OCR/transcription directly.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db
from saarthi_backend.model import User
from saarthi_backend.service import qa_review_service
from saarthi_backend.utils.exceptions import ForbiddenError

router = APIRouter(prefix="/qa-review", tags=["qa-review"])


def _require_qa_reviewer(user: User) -> None:
    if user.role not in ("qa_reviewer", "admin"):
        raise ForbiddenError("QA reviewer role required.")


class ReviewRequest(BaseModel):
    contentId: str
    sourceJsonlPath: str
    decision: str  # accept | reject | reprocess
    reason: Optional[str] = None
    editedText: Optional[str] = None


@router.get("/stats")
async def get_stats(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_qa_reviewer(user)
    stats = await qa_review_service.dashboard_stats(db)
    return {"success": True, "data": stats}


@router.get("/queue")
async def get_queue(
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    contentType: Optional[str] = None,
    course: Optional[str] = None,
):
    _require_qa_reviewer(user)
    result = qa_review_service.pending_queue(limit=limit, offset=offset, content_type=contentType, course=course)
    return {"success": True, "data": result}


@router.get("/content/{content_id}")
async def get_content(
    content_id: str,
    source_jsonl_path: Annotated[str, Query(alias="sourceJsonlPath")],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_qa_reviewer(user)
    detail = qa_review_service.content_detail(source_jsonl_path, content_id)
    return {"success": True, "data": detail}


@router.get("/content/{content_id}/source-image")
async def get_source_image(
    content_id: str,
    source_jsonl_path: Annotated[str, Query(alias="sourceJsonlPath")],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_qa_reviewer(user)
    png_bytes = qa_review_service.source_image(source_jsonl_path, content_id)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/content/{content_id}/history")
async def get_history(
    content_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_qa_reviewer(user)
    history = await qa_review_service.review_history(db, content_id)
    return {"success": True, "data": history}


@router.post("/review")
async def post_review(
    body: ReviewRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_qa_reviewer(user)
    result = await qa_review_service.submit_review(
        db,
        source_jsonl_path=body.sourceJsonlPath,
        content_id=body.contentId,
        decision=body.decision,
        reviewer_id=user.id,
        reason=body.reason,
        edited_text=body.editedText,
    )
    return {"success": True, "data": result}
