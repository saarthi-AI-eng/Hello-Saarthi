"""User profile update (frontend-aligned)."""

from typing import Optional

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    id: str
    email: str
    fullName: str
    name: Optional[str] = None
    role: str = "student"
    institute: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None

    class Config:
        populate_by_name = True


class UserProfileUpdate(BaseModel):
    fullName: Optional[str] = Field(None, min_length=1)
    institute: Optional[str] = None
    bio: Optional[str] = None
    avatarUrl: Optional[str] = None
