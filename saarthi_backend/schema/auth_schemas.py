"""Auth request/response (frontend-aligned)."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SigninRequest(BaseModel):
    """POST /api/auth/signin."""

    email: EmailStr
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class SignupRequest(BaseModel):
    """POST /api/auth/signup."""

    fullName: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirmPassword: str = Field(..., min_length=8)
    institute: Optional[str] = None
    role: Optional[str] = None  # "teacher" for instructor signup, else "student"


class RefreshRequest(BaseModel):
    """POST /api/auth/refresh. refresh_token optional if sent via cookie."""

    refresh_token: Optional[str] = None


class UserResponse(BaseModel):
    """User in auth response (frontend: id, email, fullName, name, role)."""

    id: str
    email: str
    fullName: str
    name: Optional[str] = None
    role: str = "student"
    institute: Optional[str] = None
    avatar: Optional[str] = None


class AuthResponse(BaseModel):
    """Auth response: access_token, refresh_token, token, user. remember_me for cookie duration."""

    access_token: str
    refresh_token: str
    token: str
    user: UserResponse
    remember_me: bool = True  # Used by router to set cookie expiry (short vs long session)
