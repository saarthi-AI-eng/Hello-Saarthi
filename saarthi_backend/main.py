"""Saarthi Backend - FastAPI app entry point."""

import sys
from pathlib import Path

# When running as `python main.py` from saarthi_backend, ensure project root is on path
if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from contextlib import asynccontextmanager

from pathlib import Path as PathLib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from saarthi_backend.client import AIClient
from saarthi_backend.model import Base
from saarthi_backend.router import router
from saarthi_backend.routers import api_router
from saarthi_backend.service.seed_demo_users import seed_demo_users
from saarthi_backend.utils.config import get_settings
from saarthi_backend.utils.exceptions import (
    AIServiceError,
    NotFoundError,
    SaarthiBackendError,
    ValidationError,
    error_response,
)
from saarthi_backend.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: PostgreSQL, create tables, AI client. Shutdown: dispose."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    app.state.ai_client = AIClient(settings.ai_service_base_url)
    async with session_factory() as session:
        await seed_demo_users(session)
    logger.info("Saarthi backend started: PostgreSQL and AI client ready")
    yield
    await engine.dispose()
    logger.info("Saarthi backend shutdown")


app = FastAPI(
    title="Saarthi Backend API",
    description="Backend for Saarthi: experts, retrieval, context. Orchestrator contract.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details),
    )


@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details),
    )


@app.exception_handler(AIServiceError)
async def ai_service_exception_handler(request: Request, exc: AIServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response("RETRIEVAL_ERROR", exc.message, exc.details),
    )


@app.exception_handler(SaarthiBackendError)
async def saarthi_backend_exception_handler(request: Request, exc: SaarthiBackendError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message, exc.details),
    )


app.include_router(api_router, prefix="/api")
app.include_router(router, prefix="/api/v1/saarthi", tags=["saarthi"])

# Serve uploaded files
_uploads_dir = PathLib(__file__).resolve().parent.parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "saarthi"}


@app.get("/")
async def root():
    return {
        "service": "Saarthi Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "api_prefix": "/api/v1/saarthi",
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
