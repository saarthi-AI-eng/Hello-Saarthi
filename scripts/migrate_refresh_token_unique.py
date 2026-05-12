"""
One-shot migration: add UNIQUE constraint to saarthi_refresh_tokens.token_hash.

Steps:
  1. Delete duplicate rows (keep the newest per token_hash)
  2. Add UNIQUE constraint

Run from the repo root:
    python scripts/migrate_refresh_token_unique.py

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
        # ── 1. Check if constraint already exists ─────────────────────────────
        result = await conn.execute(text("""
            SELECT COUNT(*)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'saarthi_refresh_tokens'
              AND c.contype = 'u'
              AND c.conname LIKE '%token_hash%'
        """))
        if result.scalar() > 0:
            print("✓ Unique constraint on token_hash already exists — nothing to do.")
            await engine.dispose()
            return

        # ── 2. Remove duplicate rows (keep newest id per token_hash) ──────────
        dup_result = await conn.execute(text("""
            SELECT COUNT(*) FROM saarthi_refresh_tokens srt
            WHERE id NOT IN (
                SELECT MAX(id) FROM saarthi_refresh_tokens GROUP BY token_hash
            )
        """))
        dup_count = dup_result.scalar()

        if dup_count > 0:
            print(f"  Removing {dup_count} duplicate refresh token row(s)…")
            await conn.execute(text("""
                DELETE FROM saarthi_refresh_tokens
                WHERE id NOT IN (
                    SELECT MAX(id) FROM saarthi_refresh_tokens GROUP BY token_hash
                )
            """))
            print(f"  ✓ Removed {dup_count} duplicate(s).")
        else:
            print("  No duplicate rows found.")

        # ── 3. Add unique constraint ──────────────────────────────────────────
        print("  Adding UNIQUE constraint on token_hash…")
        await conn.execute(text("""
            ALTER TABLE saarthi_refresh_tokens
            ADD CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash)
        """))
        print("✓ Migration complete: UNIQUE constraint added to saarthi_refresh_tokens.token_hash")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
