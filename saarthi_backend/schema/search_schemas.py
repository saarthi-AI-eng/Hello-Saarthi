"""Search response (frontend-aligned, paginated per type)."""

from typing import Optional

from pydantic import BaseModel, Field


class SearchItem(BaseModel):
    type: str
    id: str
    title: str
    subtitle: Optional[str] = None
    link: Optional[str] = None


class SearchResponse(BaseModel):
    courses: list[SearchItem] = []
    materials: list[SearchItem] = []
    videos: list[SearchItem] = []
    totalCourses: int = 0
    totalMaterials: int = 0
    totalVideos: int = 0
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
