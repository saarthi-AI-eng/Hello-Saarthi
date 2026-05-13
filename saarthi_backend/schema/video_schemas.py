"""Request/response schemas for videos and progress/notes."""

from typing import Optional

from pydantic import BaseModel, Field


class VideoResponse(BaseModel):
    id: str
    courseId: Optional[str] = None
    title: str
    description: Optional[str] = None
    durationSeconds: int
    thumbnailUrl: Optional[str] = None
    url: str
    embedUrl: Optional[str] = None
    chaptersJson: Optional[str] = None
    sortOrder: int
    hasTranscript: bool = False

    class Config:
        populate_by_name = True


class VideoCreate(BaseModel):
    title: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    durationSeconds: int = 0
    courseId: Optional[int] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    embedUrl: Optional[str] = None
    chaptersJson: Optional[str] = None
    sortOrder: int = 0


class VideoProgressResponse(BaseModel):
    positionSeconds: int
    completed: bool
    updatedAt: str

    class Config:
        populate_by_name = True


class VideoProgressUpdate(BaseModel):
    positionSeconds: int = 0
    completed: bool = False


class VideoNoteResponse(BaseModel):
    id: str
    videoId: str
    timeSeconds: int
    text: str
    createdAt: str

    class Config:
        populate_by_name = True


class VideoNoteCreate(BaseModel):
    timeSeconds: int = Field(..., ge=0)
    text: str = Field(..., min_length=1)


class VideoTranscriptUpload(BaseModel):
    transcriptText: str = Field(..., min_length=10)
