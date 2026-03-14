"""Shared schemas: pagination and error (non-feature)."""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

# --- Pagination ---
T = TypeVar("T")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class PaginationParams(BaseModel):
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Page size")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total number of items matching the filter")
    limit: int = Field(ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(ge=0)


# --- Error ---
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
