"""Error response shape (04-backend-to-orchestrator-responses)."""

from typing import Any, Optional

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Inner error object."""

    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Full error response body."""

    success: bool = False
    error: ErrorDetail
