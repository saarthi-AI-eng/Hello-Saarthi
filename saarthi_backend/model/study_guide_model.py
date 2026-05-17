"""Study guides: teacher-created topic guides with sequenced prompts."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from saarthi_backend.model.context_model import Base


class StudyGuide(Base):
    __tablename__ = "saarthi_study_guides"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("saarthi_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudyGuidePrompt(Base):
    __tablename__ = "saarthi_study_guide_prompts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guide_id: Mapped[int] = mapped_column(ForeignKey("saarthi_study_guides.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
