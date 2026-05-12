"""
One-shot migration: add owner_id to saarthi_courses + create saarthi_classroom_invites table.

Run from repo root:
    python scripts/migrate_classroom_invites.py

Reads DATABASE_URL from environment (falls back to the default dev URL).
"""

import asyncio
import os
import sys


async def main() -> None:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
    except ImportError:
        print("ERROR: sqlalchemy not installed. Run: pip install sqlalchemy asyncpg")
        sys.exit(1)

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/saarthi",
    )

    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        # 1. Add owner_id column to saarthi_courses if it doesn't exist
        await conn.execute(text("""
            ALTER TABLE saarthi_courses
            ADD COLUMN IF NOT EXISTS owner_id INTEGER
            REFERENCES saarthi_users(id) ON DELETE SET NULL;
        """))
        print("✓ owner_id column added to saarthi_courses (or already existed)")

        # 2. Index on owner_id
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_saarthi_courses_owner_id
            ON saarthi_courses (owner_id);
        """))
        print("✓ Index on saarthi_courses.owner_id ensured")

        # 3. Create saarthi_classroom_invites table if it doesn't exist
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS saarthi_classroom_invites (
                id          SERIAL PRIMARY KEY,
                course_id   INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
                invited_by  INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
                email       VARCHAR(255) NOT NULL,
                invite_code VARCHAR(64)  NOT NULL UNIQUE,
                accepted    BOOLEAN NOT NULL DEFAULT FALSE,
                expires_at  TIMESTAMPTZ NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """))
        print("✓ saarthi_classroom_invites table ensured")

        # 4. Indexes on the invites table
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_course_id
            ON saarthi_classroom_invites (course_id);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_invited_by
            ON saarthi_classroom_invites (invited_by);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_email
            ON saarthi_classroom_invites (email);
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_saarthi_classroom_invites_invite_code
            ON saarthi_classroom_invites (invite_code);
        """))
        print("✓ Indexes on saarthi_classroom_invites ensured")

    await engine.dispose()
    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(main())
