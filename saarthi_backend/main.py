"""Saarthi Backend - FastAPI app entry point."""

import os
import sys
import time
import uuid as uuid_mod
import warnings
from pathlib import Path

# LangChain still uses a Pydantic V1 shim that warns on Python 3.14+; suppress until they drop it
warnings.filterwarnings(
    "ignore",
    message=".*Pydantic V1.*isn't compatible with Python 3.14.*",
    category=UserWarning,
    module="langchain_core",
)

# Ensure project root is on path (for src/ AI graph and when running as main)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Load .env into os.environ so LangChain/OpenAI see OPENAI_API_KEY (Settings alone doesn't set env)
_backend_dir = Path(__file__).resolve().parent
_env_file = _backend_dir / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

from contextlib import asynccontextmanager

from pathlib import Path as PathLib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from saarthi_backend.model import Base
from saarthi_backend.routers import api_router
from saarthi_backend.scripts.seed_demo_users import seed_demo_users
from saarthi_backend.utils.config import get_settings
from saarthi_backend.utils.exceptions import (
    AIServiceError,
    ForbiddenError,
    NotFoundError,
    SaarthiBackendError,
    UnauthorizedError,
    ValidationError,
    error_response,
)
from saarthi_backend.utils.logging import get_logger
from saarthi_backend.utils.rate_limit import (
    RATE_LIMIT_AUTH,
    RATE_LIMIT_GENERAL,
    RATE_LIMIT_MATERIAL_FILE,
    RATE_LIMIT_UPLOAD,
    check_rate_limit,
    cleanup_old_buckets,
    get_identifier_from_request,
)

logger = get_logger(__name__)

# Dev-only: set SAARTHI_DEV_AUTOCREATE_TABLES=1 to create tables from ORM (otherwise use migrations)
_DEV_AUTOCREATE_TABLES = os.getenv("SAARTHI_DEV_AUTOCREATE_TABLES", "").lower() in ("1", "true", "yes")


def _validate_settings_at_startup() -> None:
    """Fail fast if required config is missing or invalid."""
    settings = get_settings()
    if not (settings.database_url and settings.database_url.strip()):
        raise RuntimeError("database_url is required and must be non-empty. Set DATABASE_URL.")
    if settings.jwt_secret == "change-me-in-production":
        logger.warning(
            "JWT secret is the default value. Set JWT_SECRET in production."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: PostgreSQL, optional dev table creation. Shutdown: dispose. AI runs in-process (src/ graph)."""
    _validate_settings_at_startup()
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    if _DEV_AUTOCREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Dev table creation from ORM enabled (SAARTHI_DEV_AUTOCREATE_TABLES)")

    # Incremental column migrations — safe to run on every startup (IF NOT EXISTS).
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "ALTER TABLE saarthi_videos ADD COLUMN IF NOT EXISTS transcript_text TEXT"
            )
        )
    logger.info("Column migration: saarthi_videos.transcript_text ensured")
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    async with session_factory() as session:
        await seed_demo_users(session)

    # Sync FAISS knowledge-base indexes from Supabase Storage on startup.
    # If local indexes already exist they are used as-is (no download).
    # If Supabase is not configured this is a silent no-op.
    try:
        from src.tools.kb_ops_supabase import sync_all_on_startup
        kb_status = sync_all_on_startup()
        logger.info("KB startup sync: %s", kb_status)
    except Exception as _kb_err:
        logger.warning("KB startup sync skipped: %s", _kb_err)

    logger.info("Saarthi backend started: PostgreSQL ready, AI in-process (src/ graph)")
    yield
    await engine.dispose()
    logger.info("Saarthi backend shutdown")


app = FastAPI(
    title="Saarthi Backend API",
    description="Backend for Saarthi: experts, retrieval, context. Orchestrator contract.",
    version="1.0.0",
    lifespan=lifespan,
)

# Request ID middleware: set request_id on request.state and add X-Request-ID to response
REQUEST_ID_HEADER = "X-Request-ID"


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid_mod.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Per-IP rate limits: stricter for auth, upload, and material file."""
    path = request.url.path or ""
    identifier = get_identifier_from_request(request)
    if path.startswith("/api/auth") and request.method == "POST":
        limit, window = RATE_LIMIT_AUTH
        prefix = "auth"
    elif path == "/api/courses/upload" and request.method == "POST":
        limit, window = RATE_LIMIT_UPLOAD
        prefix = "upload"
    elif "/materials/" in path and path.endswith("/file") and request.method == "GET":
        limit, window = RATE_LIMIT_MATERIAL_FILE
        prefix = "file"
    else:
        limit, window = RATE_LIMIT_GENERAL
        prefix = "general"
    allowed, retry_after = check_rate_limit(identifier, prefix, limit, window)
    if not allowed:
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=429,
            content=error_response(
                "RATE_LIMIT_EXCEEDED",
                "Too many requests. Please try again later.",
                details={"retryAfterSeconds": retry_after},
                request_id=rid,
            ),
            headers={
                "Retry-After": str(retry_after),
                **({REQUEST_ID_HEADER: rid} if rid else {}),
            },
        )
    cleanup_old_buckets(max_age_sec=300)
    return await call_next(request)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log request method, path, status, duration, request_id."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    rid = getattr(request.state, "request_id", None)
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        rid or "-",
    )
    return response


# CORS: explicit origins required when allow_credentials=True (browsers reject * with credentials)
_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()] or ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    rid = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details, request_id=rid),
        headers={REQUEST_ID_HEADER: rid} if rid else None,
    )


@app.exception_handler(UnauthorizedError)
async def unauthorized_exception_handler(request: Request, exc: UnauthorizedError):
    rid = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details, request_id=rid),
        headers={REQUEST_ID_HEADER: rid} if rid else None,
    )


@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError):
    rid = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details, request_id=rid),
        headers={REQUEST_ID_HEADER: rid} if rid else None,
    )


@app.exception_handler(ForbiddenError)
async def forbidden_exception_handler(request: Request, exc: ForbiddenError):
    rid = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details, request_id=rid),
        headers={REQUEST_ID_HEADER: rid} if rid else None,
    )


@app.exception_handler(AIServiceError)
async def ai_service_exception_handler(request: Request, exc: AIServiceError):
    rid = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details, request_id=rid),
        headers={REQUEST_ID_HEADER: rid} if rid else None,
    )


@app.exception_handler(SaarthiBackendError)
async def saarthi_backend_exception_handler(request: Request, exc: SaarthiBackendError):
    rid = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details, request_id=rid),
        headers={REQUEST_ID_HEADER: rid} if rid else None,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = _request_id(request)
    logger.exception("Unhandled exception (request_id=%s): %s", rid, exc, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Use the requestId to correlate with server logs.",
            details=None,
            request_id=rid,
        ),
        headers={REQUEST_ID_HEADER: rid} if rid else None,
    )


app.include_router(api_router, prefix="/api")

# Serve uploaded files
_uploads_dir = PathLib(__file__).resolve().parent.parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


@app.get("/health")
async def health(request: Request):
    """Liveness: always 200. For readiness (DB) use GET /ready."""
    return {"status": "healthy", "service": "saarthi"}


@app.get("/ready")
async def ready(request: Request):
    """Readiness: 200 if DB is reachable, 503 otherwise (for load balancers)."""
    engine = getattr(request.app.state, "db_engine", None)
    if not engine:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": "saarthi", "db": "not_initialized"},
        )
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "saarthi", "db": "ok"}
    except Exception as e:
        logger.warning("Readiness check failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": "saarthi", "db": "down"},
        )


@app.get("/")
async def root():
    return {
        "service": "Saarthi Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "api_prefix": "/api",
    }


if __name__ == "__main__":
    # Run from saarthi_backend: python main.py  (use venv: ../.venv/bin/python main.py)
    # Or from project root: python saarthi_backend/main.py
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
    )
