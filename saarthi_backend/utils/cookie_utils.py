"""Set/clear auth cookies (production-grade: HTTP-only, SameSite)."""

from fastapi import Response

from saarthi_backend.utils.config import get_settings


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    *,
    remember_me: bool = True,
) -> None:
    """Set access and refresh token cookies. Session cookie for refresh when remember_me is False."""
    s = get_settings()
    access_max_age = s.jwt_access_expire_minutes * 60
    # Session cookie (no max_age) when remember_me is False; otherwise long-lived
    refresh_max_age = (s.jwt_refresh_expire_days * 24 * 3600) if remember_me else None

    response.set_cookie(
        key=s.cookie_access_name,
        value=access_token,
        max_age=access_max_age,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_same_site,
        domain=s.cookie_domain,
    )
    response.set_cookie(
        key=s.cookie_refresh_name,
        value=refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_same_site,
        domain=s.cookie_domain,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies (on logout)."""
    s = get_settings()
    for name in (s.cookie_access_name, s.cookie_refresh_name):
        response.delete_cookie(key=name, domain=s.cookie_domain, path="/")
