"""Load config from environment."""

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from env."""

    app_name: str = "Saarthi Backend"
    port: int = 8000
    host: str = "0.0.0.0"

    # AI service (backend_api_docs.md)
    ai_service_base_url: str = "https://api.saarthi.app/v1"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/saarthi"

    # JWT (access + refresh)
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7

    # Auth cookies (production-grade: HTTP-only, SameSite)
    cookie_access_name: str = "saarthi_access_token"
    cookie_refresh_name: str = "saarthi_refresh_token"
    cookie_secure: bool = False  # True in production (HTTPS)
    cookie_same_site: str = "lax"
    cookie_domain: str | None = None  # e.g. ".saarthi.ai" in prod

    # CORS: allow_credentials=True requires explicit origins (no "*")
    # Comma-separated list; include Vite (5173, or 5174 when 5173 is taken) and CRA (3000) for local dev
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    # Supabase — used by KB sync and data store
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""

    # Admin panel — static bearer token protecting /api/admin/* routes
    admin_secret_token: str = ""

    # Email (SMTP) — classroom invites
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@saarthi.app"
    app_frontend_url: str = "https://saarthi.app"

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg(cls, v: str) -> str:
        """Accept plain postgres URLs (e.g. Neon's copy-paste string) for the asyncpg engine.

        asyncpg needs the +asyncpg driver, takes ssl= instead of sslmode=, and rejects
        channel_binding=.
        """
        parts = urlsplit(v.strip())
        scheme = parts.scheme
        if scheme in ("postgres", "postgresql", "postgresql+psycopg2"):
            scheme = "postgresql+asyncpg"
        if scheme != "postgresql+asyncpg":
            return v
        query = []
        for key, value in parse_qsl(parts.query):
            if key == "channel_binding":
                continue
            query.append(("ssl" if key == "sslmode" else key, value))
        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
