"""Context GET/POST schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContextUpsertRequest(BaseModel):
    """POST /context body."""

    conversation_id: str = Field(..., min_length=1)
    summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ContextGetResponse(BaseModel):
    """GET /context/{conversation_id} response."""

    conversation_id: str
    summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    updated_at: Optional[str] = None  # ISO 8601
