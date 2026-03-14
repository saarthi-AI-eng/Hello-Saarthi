"""
Production migration runner. Run once per deploy or when adding new migrations.
Uses saarthi_schema_version to run each migration file only once.
"""
import asyncio
import sys
from pathlib import Path

# Project root on path when run as script
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from saarthi_backend.utils.config import get_settings


MIGRATIONS_DIR = Path(__file__).resolve().parent


async def ensure_migrations_table(conn):
    """Create saarthi_schema_version if not exists (from 001)."""
    sql = (MIGRATIONS_DIR / "001_create_migrations_table.sql").read_text()
    await conn.execute(text(sql))


async def get_applied_versions(conn):
    """Return set of applied migration version keys (e.g. '001_create_migrations_table')."""
    result = await conn.execute(
        text("SELECT version FROM saarthi_schema_version")
    )
    return {row[0] for row in result.fetchall()}


def _split_statements(sql: str) -> list[str]:
    """Split SQL into single statements (asyncpg allows only one per execute)."""
    statements = []
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)
    return statements


async def apply_migration(conn, version: str, name: str, sql: str):
    """Execute migration SQL and record version."""
    for stmt in _split_statements(sql):
        await conn.execute(text(stmt))
    await conn.execute(
        text(
            "INSERT INTO saarthi_schema_version (version, name) VALUES (:v, :n)"
        ),
        {"v": version, "n": name},
    )


async def run():
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    # 001 is run first to ensure table exists; we still record it
    applied = set()

    async with engine.begin() as conn:
        await ensure_migrations_table(conn)
        applied = await get_applied_versions(conn)

        for path in sql_files:
            version = path.stem  # e.g. 001_create_migrations_table
            if version in applied:
                print(f"Skip (already applied): {path.name}")
                continue
            print(f"Applying: {path.name}")
            sql = path.read_text()
            await apply_migration(conn, version, path.name, sql)

    await engine.dispose()
    print("Migrations finished.")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
