"""JWT access and refresh tokens."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from saarthi_backend.utils.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(sub: str, extra: Optional[dict[str, Any]] = None) -> str:
    settings = get_settings()
    payload = {
        "sub": str(sub),
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.jwt_access_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(sub: str, expire_days: int | None = None) -> str:
    settings = get_settings()
    days = expire_days if expire_days is not None else settings.jwt_refresh_expire_days
    payload = {
        "sub": str(sub),
        "type": "refresh",
        "iat": _now(),
        "exp": _now() + timedelta(days=days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError:
        return None
