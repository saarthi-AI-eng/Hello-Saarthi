"""Auth DAO: refresh token storage and lookup."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import RefreshToken


class RefreshTokenDAO:
    @staticmethod
    async def create(db: AsyncSession, user_id: int, token_hash: str, expires_at: datetime) -> RefreshToken:
        row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @staticmethod
    async def find_valid(db: AsyncSession, token_hash: str) -> RefreshToken | None:
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_by_hash(db: AsyncSession, token_hash: str) -> None:
        row = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        r = row.scalar_one_or_none()
        if r:
            r.revoked = True
            await db.flush()
