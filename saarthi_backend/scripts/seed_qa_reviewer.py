"""Idempotent QA reviewer account seed — the ONLY way to create a
qa_reviewer account. Never run automatically at app startup (unlike
seed_demo_users.py) and never exposed through signup/registration.

Usage:
    QA_REVIEWER_EMAIL=qa@saarthi.ai QA_REVIEWER_PASSWORD='...' python -m saarthi_backend.scripts.seed_qa_reviewer
    QA_REVIEWER_EMAIL=qa@saarthi.ai python -m saarthi_backend.scripts.seed_qa_reviewer   # auto-generates a
                                                            # secure random password, printed once —
                                                            # store it, it is never shown again
    python -m saarthi_backend.scripts.seed_qa_reviewer --interactive   # prompts for email/password instead

Safe to re-run: if the account already exists with role qa_reviewer, this
is a no-op (idempotent). If the email already exists with a DIFFERENT
role, it refuses to touch it rather than silently overwriting someone
else's account.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import secrets
import string
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from saarthi_backend.dao import UserDAO
from saarthi_backend.utils.config import get_settings
from saarthi_backend.utils.password import hash_password


def _generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def seed_qa_reviewer(db: AsyncSession, email: str, password: str, full_name: str = "QA Reviewer") -> tuple:
    """Returns (user, created: bool). Raises RuntimeError if the email
    already exists with a role OTHER than qa_reviewer — never silently
    reassigns an existing account's role."""
    existing = await UserDAO.get_by_email(db, email)
    if existing:
        if existing.role != "qa_reviewer":
            raise RuntimeError(
                f"{email} already exists with role {existing.role!r}, not qa_reviewer — refusing to modify it."
            )
        return existing, False
    user = await UserDAO.create(
        db,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role="qa_reviewer",
    )
    await db.commit()
    return user, True


async def main() -> int:
    # --interactive is opt-in, not auto-detected via sys.stdin.isatty():
    # that check is unreliable across terminals/CI/sandboxed shells (some
    # report a TTY that never actually yields input), which can hang a
    # getpass.getpass() call forever with no feedback. Confirmed directly.
    interactive = "--interactive" in sys.argv[1:]

    email = os.environ.get("QA_REVIEWER_EMAIL", "").strip()
    password = os.environ.get("QA_REVIEWER_PASSWORD", "").strip()
    full_name = os.environ.get("QA_REVIEWER_NAME", "QA Reviewer").strip() or "QA Reviewer"

    if not email:
        if not interactive:
            print(
                "QA_REVIEWER_EMAIL is not set. Set it, or pass --interactive to be prompted.",
                file=sys.stderr,
            )
            return 1
        email = input("QA reviewer email: ").strip()
    if not email:
        print("No email provided — aborting.", file=sys.stderr)
        return 1

    generated = False
    if not password:
        if interactive:
            password = getpass.getpass("QA reviewer password (leave blank to auto-generate): ").strip()
        if not password:
            password = _generate_password()
            generated = True

    settings = get_settings()
    engine = create_async_engine(settings.database_url, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            user, created = await seed_qa_reviewer(db, email, password, full_name)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    if created:
        print(f"Created qa_reviewer account: {email}")
        if generated:
            print(f"Generated password (shown once — store it securely now): {password}")
    else:
        print(f"qa_reviewer account {email} already exists (id={user.id}) — no changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
