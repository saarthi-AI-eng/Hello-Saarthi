"""User DAO."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import User


class UserDAO:
    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        email: str,
        password_hash: str,
        full_name: str,
        role: str = "student",
        institute: str | None = None,
    ) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            institute=institute,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user_id: int,
        full_name: str | None = None,
        institute: str | None = None,
        bio: str | None = None,
        avatar_url: str | None = None,
    ) -> User | None:
        user = await UserDAO.get_by_id(db, user_id)
        if not user:
            return None
        if full_name is not None:
            user.full_name = full_name
        if institute is not None:
            user.institute = institute
        if bio is not None:
            user.bio = bio
        if avatar_url is not None:
            user.avatar_url = avatar_url
        await db.flush()
        await db.refresh(user)
        return user
