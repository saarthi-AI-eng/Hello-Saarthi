"""Request/response schemas for standalone notes."""

from typing import Optional

from pydantic import BaseModel, Field


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    courseId: Optional[str] = None
    topic: Optional[str] = None
    createdAt: str
    updatedAt: str

    class Config:
        populate_by_name = True


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    courseId: Optional[int] = None
    topic: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    content: Optional[str] = Field(None, min_length=1)
