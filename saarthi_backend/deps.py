"""FastAPI dependencies: DB session, current user, pagination."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.schema.common_schemas import MAX_PAGE_SIZE, PaginationParams
from saarthi_backend.dao import UserDAO
from saarthi_backend.model import User
from saarthi_backend.utils.config import get_settings
from saarthi_backend.utils.exceptions import ValidationError
from saarthi_backend.utils.jwt_utils import decode_token


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> PaginationParams:
    """Parse and validate pagination query params (production: default 20, max 100)."""
    return PaginationParams(limit=limit, offset=offset)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session per request."""
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Require authenticated user. Read access token from cookie or Authorization header."""
    settings = get_settings()
    token = request.cookies.get(settings.cookie_access_name)
    if not token and request.headers.get("Authorization"):
        parts = request.headers["Authorization"].split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        raise ValidationError("Not authenticated.", details=None)
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise ValidationError("Invalid or expired access token.", details=None)
    user_id = payload.get("sub")
    if not user_id:
        raise ValidationError("Invalid token.", details=None)
    user = await UserDAO.get_by_id(db, int(user_id))
    if not user:
        raise ValidationError("User not found.", details=None)
    return user


async def get_current_user_optional(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Optional auth: return user if valid token present, else None."""
    settings = get_settings()
    token = request.cookies.get(settings.cookie_access_name)
    if not token and request.headers.get("Authorization"):
        parts = request.headers["Authorization"].split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return await UserDAO.get_by_id(db, int(user_id))
