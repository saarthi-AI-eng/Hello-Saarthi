"""Course-related models: Course, Enrollment, Assignment, Material, Stream, ClassroomInvite."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saarthi_backend.model.context_model import Base


class Course(Base):
    """Course (subject) metadata."""

    __tablename__ = "saarthi_courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    instructor: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # owner_id links course to the teacher/admin who created it
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("saarthi_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Enrollment(Base):
    """User enrollment in a course with progress."""

    __tablename__ = "saarthi_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("saarthi_users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("saarthi_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assignment(Base):
    """Assignment within a course."""

    __tablename__ = "saarthi_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("saarthi_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[str] = mapped_column(String(32), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    topic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attachments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssignmentSubmission(Base):
    """User submission for an assignment."""

    __tablename__ = "saarthi_assignment_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("saarthi_users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("saarthi_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Material(Base):
    """Course material (PDF, link, etc.)."""

    __tablename__ = "saarthi_materials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("saarthi_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StreamItem(Base):
    """Stream/announcement in a course."""

    __tablename__ = "saarthi_stream_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("saarthi_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="announcement")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClassroomInvite(Base):
    """Email-based invite code that lets a student join a course (like Google Classroom)."""

    __tablename__ = "saarthi_classroom_invites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("saarthi_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_by: Mapped[int] = mapped_column(
        ForeignKey("saarthi_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    invite_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
