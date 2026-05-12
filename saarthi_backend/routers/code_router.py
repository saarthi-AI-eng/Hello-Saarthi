"""Code execution routes — Piston runner + AI error explanation."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from saarthi_backend.deps import get_current_user
from saarthi_backend.model import User
from saarthi_backend.schema.code_schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CodeExplainRequest,
    CodeExplainResponse,
)
from saarthi_backend.service import code_service

router = APIRouter(prefix="/code", tags=["code"])


@router.post("/execute", response_model=CodeExecuteResponse)
async def execute_code(
    body: CodeExecuteRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Run code via Piston API and return stdout/stderr/exit code.
    If explainOnError=True and execution fails, also returns AI explanation.
    """
    return await code_service.execute_code(body)


@router.post("/explain/stream")
async def stream_explain(
    body: CodeExplainRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Stream an AI explanation of a code error token-by-token via SSE.
    Call this after /execute returns a non-zero exit code for real-time feedback.
    """
    return StreamingResponse(
        code_service.stream_explain_error(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/explain", response_model=CodeExplainResponse)
async def explain_error(
    body: CodeExplainRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """Synchronous AI error explanation (non-streaming fallback)."""
    return await code_service.explain_error(body)


@router.get("/runtimes")
async def list_runtimes():
    """List all languages/versions available on the Piston execution engine."""
    return await code_service.list_runtimes()
