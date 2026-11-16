"""CodeProblem model for coding lab problems."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from saarthi_backend.model.context_model import Base


class CodeProblem(Base):
    """A coding lab problem with starter code, hints, and expected output."""

    __tablename__ = "saarthi_code_problems"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requirements_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON list of {"input": str, "expectedOutput": str, "hidden": bool}.
    test_cases_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    hints_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    starter_code_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CodeSubmission(Base):
    """A student's submitted solution, with the test results at submit time."""

    __tablename__ = "saarthi_code_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("saarthi_code_problems.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("saarthi_users.id", ondelete="CASCADE"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
