"""Production-grade pagination: params and response envelope."""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class PaginationParams(BaseModel):
    """Validated limit and offset from query (use with Depends)."""

    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Page size")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for paginated list endpoints."""

    items: List[T] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total number of items matching the filter")
    limit: int = Field(ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(ge=0)
