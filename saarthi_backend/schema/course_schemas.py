"""Request/response schemas for courses, enrollments, assignments, materials, stream."""

from typing import Optional

from pydantic import BaseModel, Field


# ----- Course -----
class CourseResponse(BaseModel):
    id: str
    title: str
    code: str
    instructor: str
    description: Optional[str] = None
    thumbnailEmoji: Optional[str] = None
    color: Optional[str] = None

    class Config:
        populate_by_name = True


class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    instructor: str = Field(..., min_length=1)
    description: Optional[str] = None
    thumbnailEmoji: Optional[str] = None
    color: Optional[str] = None


# ----- Enrollment -----
class EnrollmentResponse(BaseModel):
    id: str
    courseId: str
    progressPercent: float
    lastAccessedAt: Optional[str] = None

    class Config:
        populate_by_name = True


class EnrollmentWithCourseResponse(EnrollmentResponse):
    course: CourseResponse


# ----- Assignment -----
class AssignmentResponse(BaseModel):
    id: str
    courseId: str
    title: str
    description: Optional[str] = None
    dueDate: str
    points: int
    topic: Optional[str] = None
    attachments: Optional[str] = None
    createdAt: str

    class Config:
        populate_by_name = True


class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    dueDate: str = Field(..., min_length=1)
    points: int = 100
    topic: Optional[str] = None
    attachments: Optional[str] = None


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    dueDate: Optional[str] = None
    points: Optional[int] = None
    topic: Optional[str] = None
    attachments: Optional[str] = None


class AssignmentSubmitRequest(BaseModel):
    attachmentUrl: Optional[str] = None


# ----- Material -----
class MaterialResponse(BaseModel):
    id: str
    courseId: str
    title: str
    description: Optional[str] = None
    type: str
    url: str
    topic: Optional[str] = None
    createdAt: str

    class Config:
        populate_by_name = True


class MaterialCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    type: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    topic: Optional[str] = None


class MaterialUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    topic: Optional[str] = None


# ----- Stream -----
class StreamItemResponse(BaseModel):
    id: str
    courseId: str
    type: str
    title: Optional[str] = None
    description: str
    author: str
    createdAt: str

    class Config:
        populate_by_name = True


class StreamItemCreate(BaseModel):
    description: str = Field(..., min_length=1)
    type: str = "announcement"
    title: Optional[str] = None


class StreamItemUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1)
    type: Optional[str] = None
    title: Optional[str] = None


# ----- Course people -----
class CoursePersonResponse(BaseModel):
    userId: str
    fullName: str
    progressPercent: float


# ----- Search (no dedicated search_schemas; under course domain) -----
class SearchItem(BaseModel):
    type: str
    id: str
    title: str
    subtitle: Optional[str] = None
    link: str


class SearchResponse(BaseModel):
    limit: int
    offset: int
    courses: list[SearchItem] = []
    materials: list[SearchItem] = []
    videos: list[SearchItem] = []
    totalCourses: int = 0
    totalMaterials: int = 0
    totalVideos: int = 0
