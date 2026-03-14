"""Auth routes: signin, signup, refresh, me (under /api/auth). Cookies set for production-grade auth."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_db
from saarthi_backend.schema.auth_schemas import AuthResponse, SigninRequest, SignupRequest, RefreshRequest, UserResponse
from saarthi_backend.service import auth_service
from saarthi_backend.utils.config import get_settings
from saarthi_backend.utils.cookie_utils import set_auth_cookies, clear_auth_cookies
from saarthi_backend.utils.exceptions import ValidationError
from saarthi_backend.utils.jwt_utils import decode_token
from saarthi_backend.dao import UserDAO

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_response(user):
    role = (user.role or "").strip().lower()
    if role not in ("teacher", "admin"):
        role = "student"
    return UserResponse(
        id=str(user.id),
        email=user.email,
        fullName=user.full_name,
        name=user.full_name,
        role=role,
        institute=user.institute,
        avatar=user.avatar_url,
    )


@router.post("/signin", response_model=AuthResponse)
async def signin(
    body: SigninRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await auth_service.signin(db, body.email, body.password, remember_me=body.remember_me)
    set_auth_cookies(response, result.access_token, result.refresh_token, remember_me=body.remember_me)
    return result


@router.post("/signup", response_model=AuthResponse)
async def signup(
    body: SignupRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await auth_service.signup(
        db,
        full_name=body.fullName,
        email=body.email,
        password=body.password,
        confirm_password=body.confirmPassword,
        institute=body.institute,
        role=body.role,
    )
    set_auth_cookies(response, result.access_token, result.refresh_token, remember_me=True)
    return result


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = Body(None),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    settings = get_settings()
    refresh_token = (body.refresh_token if body else None) or request.cookies.get(settings.cookie_refresh_name)
    if not refresh_token:
        raise ValidationError("Refresh token required (cookie or body).", details=None)
    result = await auth_service.refresh(db, refresh_token)
    set_auth_cookies(response, result.access_token, result.refresh_token, remember_me=result.remember_me)
    return result


@router.get("/me", response_model=UserResponse)
async def me(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Return current user from access token (cookie or Authorization header)."""
    settings = get_settings()
    access_token = request.cookies.get(settings.cookie_access_name)
    if not access_token and request.headers.get("Authorization"):
        parts = request.headers["Authorization"].split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            access_token = parts[1]
    if not access_token:
        raise ValidationError("Not authenticated.", details=None)
    payload = decode_token(access_token)
    if not payload or payload.get("type") != "access":
        raise ValidationError("Invalid or expired access token.", details=None)
    user_id = payload.get("sub")
    if not user_id:
        raise ValidationError("Invalid token.", details=None)
    user = await UserDAO.get_by_id(db, int(user_id))
    if not user:
        raise ValidationError("User not found.", details=None)
    return _user_to_response(user)


@router.post("/logout")
async def logout(response: Response):
    """Clear auth cookies (client should clear local state)."""
    clear_auth_cookies(response)
    return JSONResponse(content={"success": True})
