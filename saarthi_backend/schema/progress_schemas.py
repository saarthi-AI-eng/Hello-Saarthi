"""Dashboard / progress aggregation (frontend-aligned)."""

from typing import Optional

from pydantic import BaseModel


class ProgressResponse(BaseModel):
    """GET /api/users/me/progress or /api/progress."""

    coursesEnrolled: int = 0
    pendingAssignments: int = 0
    avgQuizScorePercent: float = 0.0
    studyTimeHours: float = 0.0
    streakDays: int = 0
