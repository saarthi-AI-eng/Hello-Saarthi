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


class ProgressResponse(BaseModel):
    """GET /api/users/me/progress — dashboard aggregation (frontend-aligned)."""

    coursesEnrolled: int = 0
    pendingAssignments: int = 0
    avgQuizScorePercent: float = 0.0
    studyTimeHours: float = 0.0
    streakDays: int = 0
