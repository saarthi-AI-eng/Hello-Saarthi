"""Load config from environment."""

from functools import lru_cache

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
    # Comma-separated list; include Vite (5173) and CRA (3000) for local dev
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
