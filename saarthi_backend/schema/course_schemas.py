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


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    code: Optional[str] = Field(None, min_length=1)
    instructor: Optional[str] = Field(None, min_length=1)
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
    hardDeadline: bool = False
    status: str = "pending"  # the requesting student's own submission status
    grade: Optional[float] = None
    submittedAt: Optional[str] = None  # the requesting student's own work
    attachmentUrl: Optional[str] = None

    class Config:
        populate_by_name = True


class SubmissionResponse(BaseModel):
    """One enrolled student's work on an assignment (teacher view)."""

    userId: str
    studentName: str
    studentEmail: str
    status: str  # pending (assigned) | submitted (turned in) | graded
    submittedAt: Optional[str] = None
    attachmentUrl: Optional[str] = None
    grade: Optional[float] = None


class GradeRequest(BaseModel):
    grade: Optional[float] = Field(None, ge=0, description="Points earned; null removes the grade")


class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    dueDate: str = Field(..., min_length=1)
    points: int = 100
    topic: Optional[str] = None
    attachments: Optional[str] = None
    hardDeadline: bool = False


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    dueDate: Optional[str] = None
    points: Optional[int] = None
    topic: Optional[str] = None
    attachments: Optional[str] = None
    hardDeadline: Optional[bool] = None


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


class StreamCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


class StreamCommentResponse(BaseModel):
    id: str
    streamItemId: str
    userId: str
    author: str
    body: str
    createdAt: str


class StreamItemUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1)
    type: Optional[str] = None
    title: Optional[str] = None


# ----- Course people -----
class CoursePersonResponse(BaseModel):
    userId: str
    fullName: str
    progressPercent: float


# ----- Classroom invites -----
class InviteRequest(BaseModel):
    email: str = Field(..., description="Email address to invite. Use '*' for an open link anyone can join.")


class InviteResponse(BaseModel):
    inviteCode: str
    email: str
    courseId: str
    expiresAt: str
    inviteLink: str


class JoinRequest(BaseModel):
    inviteCode: str = Field(..., min_length=1)


class JoinResponse(BaseModel):
    courseId: str
    courseTitle: str
    message: str


class MyInviteItem(BaseModel):
    """A pending course invite addressed to the signed-in student."""

    id: str
    inviteCode: str
    courseId: str
    courseTitle: str
    courseCode: str
    instructor: str
    thumbnailEmoji: Optional[str] = None
    expiresAt: str


class InviteListItem(BaseModel):
    id: str
    email: str
    inviteCode: str
    accepted: bool
    expiresAt: str
    createdAt: str


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
