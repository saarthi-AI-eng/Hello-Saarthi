"""Seed demo users on startup if they don't exist (for Demo Admin / Demo Student / Demo Teacher)."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import UserDAO
from saarthi_backend.utils.password import hash_password


DEMO_USERS = [
    {"email": "admin@saarthi.ai", "password": "Admin123", "full_name": "Demo Admin", "role": "admin"},
    {"email": "student@saarthi.ai", "password": "Student123", "full_name": "Demo Student", "role": "student"},
    {"email": "teacher@saarthi.ai", "password": "Teacher123", "full_name": "Demo Teacher", "role": "teacher"},
]


async def seed_demo_users(db: AsyncSession) -> None:
    """Create demo users if they don't exist."""
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
