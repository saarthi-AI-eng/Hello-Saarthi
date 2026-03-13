"""Auth service: signin, signup, refresh."""

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import RefreshTokenDAO, UserDAO
from saarthi_backend.model import User
from saarthi_backend.schema.auth_schemas import AuthResponse, UserResponse
from saarthi_backend.utils.config import get_settings
from saarthi_backend.utils.exceptions import ValidationError
from saarthi_backend.utils.jwt_utils import create_access_token, create_refresh_token, decode_token
from saarthi_backend.utils.password import hash_password, verify_password


def _user_to_response(user: User) -> UserResponse:
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
    )


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def signin(db: AsyncSession, email: str, password: str, remember_me: bool = False) -> AuthResponse:
    user = await UserDAO.get_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise ValidationError("Invalid email or password.", details=None)
    access = create_access_token(str(user.id))
    settings = get_settings()
    refresh_days = settings.jwt_refresh_expire_days if remember_me else 1
    refresh = create_refresh_token(str(user.id), expire_days=refresh_days)
    expires = datetime.now(timezone.utc) + timedelta(days=refresh_days)
    await RefreshTokenDAO.create(db, user.id, _hash_refresh(refresh), expires)
    await db.commit()
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        token=access,
        user=_user_to_response(user),
    )


async def signup(
    db: AsyncSession,
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    institute: str | None = None,
    role: str | None = None,
) -> AuthResponse:
    if password != confirm_password:
        raise ValidationError("Passwords do not match.", details=None)
    existing = await UserDAO.get_by_email(db, email)
    if existing:
        raise ValidationError("An account with this email already exists.", details=None)
    user_role = "teacher" if (role and str(role).strip().lower() == "teacher") else "student"
    user = await UserDAO.create(
        db,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=user_role,
        institute=institute,
    )
    await db.flush()
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    await RefreshTokenDAO.create(db, user.id, _hash_refresh(refresh), expires)
    await db.commit()
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        token=access,
        user=_user_to_response(user),
    )


async def refresh(db: AsyncSession, refresh_token: str) -> AuthResponse:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise ValidationError("Invalid or expired refresh token.", details=None)
    token_hash = _hash_refresh(refresh_token)
    row = await RefreshTokenDAO.find_valid(db, token_hash)
    if not row:
        raise ValidationError("Invalid or expired refresh token.", details=None)
    user = await UserDAO.get_by_id(db, row.user_id)
    if not user:
        raise ValidationError("User not found.", details=None)
    access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))
    await RefreshTokenDAO.revoke_by_hash(db, token_hash)
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    await RefreshTokenDAO.create(db, user.id, _hash_refresh(new_refresh), expires)
    await db.commit()
    return AuthResponse(
        access_token=access,
        refresh_token=new_refresh,
        token=access,
        user=_user_to_response(user),
    )
