"""Seed demo users on startup only when explicitly enabled (non-production)."""

import os

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import UserDAO
from saarthi_backend.utils.password import hash_password

# Demo user seeding is disabled by default. Set SAARTHI_ENABLE_DEMO_USERS=1 (or true/yes)
# only in non-production environments to allow seeding. Do not use in production.
DEMO_USER_SEED_ENABLED = os.getenv("SAARTHI_ENABLE_DEMO_USERS", "").lower() in ("1", "true", "yes")

DEMO_USERS = [
    {"email": "admin@saarthi.ai", "password": "Admin123", "full_name": "Demo Admin", "role": "admin"},
    {"email": "student@saarthi.ai", "password": "Student123", "full_name": "Demo Student", "role": "student"},
    {"email": "teacher@saarthi.ai", "password": "Teacher123", "full_name": "Demo Teacher", "role": "teacher"},
]


async def seed_demo_users(db: AsyncSession) -> None:
    """Create demo users if they don't exist. No-op unless SAARTHI_ENABLE_DEMO_USERS is set."""
    if not DEMO_USER_SEED_ENABLED:
        return
    for u in DEMO_USERS:
        existing = await UserDAO.get_by_email(db, u["email"])
        if existing:
            continue
        await UserDAO.create(
            db,
            email=u["email"],
            password_hash=hash_password(u["password"]),
            full_name=u["full_name"],
            role=u["role"],
            institute=None,
        )
    await db.commit()
    # One demo course so the student dashboard is not empty
    try:
        from sqlalchemy import select, func
        from saarthi_backend.model.course_model import Course, Enrollment
        n = (await db.execute(select(func.count()).select_from(Course))).scalar() or 0
        if n == 0:
            teacher = await UserDAO.get_by_email(db, "teacher@saarthi.ai")
            student = await UserDAO.get_by_email(db, "student@saarthi.ai")
            course = Course(
                title="Demo Signals & Systems",
                code="EE210",
                instructor="Demo Teacher",
                description="Sample course so you can click around locally. Add your own materials as teacher.",
                thumbnail_emoji="📡",
                color="#2563eb",
                owner_id=teacher.id if teacher else None,
            )
            db.add(course)
            await db.flush()
            if student:
                db.add(Enrollment(user_id=student.id, course_id=course.id, progress_percent=10.0))
            if teacher:
                db.add(Enrollment(user_id=teacher.id, course_id=course.id, progress_percent=0.0))
            await db.commit()
    except Exception:
        await db.rollback()
