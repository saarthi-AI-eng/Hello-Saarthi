# Schema package - re-export commonly used schemas
from .common_schemas import ErrorResponse, MAX_PAGE_SIZE, PaginationParams

__all__ = [
    "ErrorResponse",
    "MAX_PAGE_SIZE",
    "PaginationParams",
]
