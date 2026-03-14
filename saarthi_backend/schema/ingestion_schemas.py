"""Ingestion endpoint request/response (optional)."""

from typing import Optional

from pydantic import BaseModel, Field


class IngestionVideoRequest(BaseModel):
    """POST /ingestion/video body."""

    source_path: Optional[str] = None
    video_ids: Optional[list[str]] = None


class IngestionNotesRequest(BaseModel):
    """POST /ingestion/notes body."""

    source_path: Optional[str] = None
    doc_ids: Optional[list[str]] = None


class IngestionCodeRequest(BaseModel):
    """POST /ingestion/code body."""

    source_path: Optional[str] = None
    file_paths: Optional[list[str]] = None


class IngestionResponse(BaseModel):
    """Generic ingestion response."""

    success: bool = True
    message: str = "Ingestion triggered."
    details: Optional[dict] = None
