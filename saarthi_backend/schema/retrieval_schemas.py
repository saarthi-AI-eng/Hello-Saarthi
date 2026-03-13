"""Retrieval search request/response."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievalSearchRequest(BaseModel):
    """POST /retrieval/search body."""

    query: str = Field(..., min_length=1)
    content_types: Optional[list[str]] = None
    top_k: int = Field(default=5, ge=1, le=50)
    include_scores: bool = True


class RetrievalChunk(BaseModel):
    """One chunk in retrieval results."""

    content_type: str
    source_id: str
    text: str
    score: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


class RetrievalSearchResponse(BaseModel):
    """POST /retrieval/search response."""

    results: list[RetrievalChunk]
    query: str
    total_returned: int
