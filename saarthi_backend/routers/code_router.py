"""Code execution routes — Piston runner + AI error explanation."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db
from saarthi_backend.model import User
from saarthi_backend.model.code_problem_model import CodeProblem
from saarthi_backend.schema.code_schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CodeExplainRequest,
    CodeExplainResponse,
    CodeProblemCreate,
    CodeProblemResponse,
    CodeProblemUpdate,
)
from saarthi_backend.service import code_service

router = APIRouter(prefix="/code", tags=["code"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_list(value: str | None) -> list[str]:
    """Parse a JSON-encoded list of strings; return [] on error or None."""
    if not value:
        return []
    try:
        result = json.loads(value)
        if isinstance(result, list):
            return [str(item) for item in result]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _parse_json_dict(value: str | None) -> dict[str, str]:
    """Parse a JSON-encoded dict of strings; return {} on error or None."""
    if not value:
        return {}
    try:
        result = json.loads(value)
        if isinstance(result, dict):
            return {str(k): str(v) for k, v in result.items()}
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _problem_to_response(p: CodeProblem) -> CodeProblemResponse:
    """Convert a CodeProblem ORM row to CodeProblemResponse."""
    return CodeProblemResponse(
        id=p.id,
        title=p.title,
        difficulty=p.difficulty,
        points=p.points,
        description=p.description,
        requirements=_parse_json_list(p.requirements_json),
        expectedOutput=p.expected_output,
        hints=_parse_json_list(p.hints_json),
        starterCode=_parse_json_dict(p.starter_code_json),
        topics=p.topics,
        sortOrder=p.sort_order,
    )


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


# ---------------------------------------------------------------------------
# Coding Lab problem endpoints
# ---------------------------------------------------------------------------

@router.get("/problems", response_model=list[CodeProblemResponse])
async def list_problems(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return all active coding lab problems ordered by sort_order."""
    result = await db.execute(
        select(CodeProblem)
        .where(CodeProblem.is_active == True)  # noqa: E712
        .order_by(CodeProblem.sort_order, CodeProblem.id)
    )
    problems = result.scalars().all()
    return [_problem_to_response(p) for p in problems]


@router.get("/problems/{problem_id}", response_model=CodeProblemResponse)
async def get_problem(
    problem_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return a single active coding lab problem by id."""
    result = await db.execute(
        select(CodeProblem).where(CodeProblem.id == problem_id, CodeProblem.is_active == True)  # noqa: E712
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return _problem_to_response(problem)


@router.post("/problems", response_model=CodeProblemResponse, status_code=201)
async def create_problem(
    body: CodeProblemCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new coding lab problem. Requires admin or teacher role."""
    if user.role not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="Admin or teacher role required")
    problem = CodeProblem(
        title=body.title,
        difficulty=body.difficulty,
        points=body.points,
        description=body.description,
        requirements_json=json.dumps(body.requirements),
        expected_output=body.expectedOutput,
        hints_json=json.dumps(body.hints),
        starter_code_json=json.dumps(body.starterCode),
        topics=body.topics,
        sort_order=body.sortOrder,
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)
    return _problem_to_response(problem)


@router.patch("/problems/{problem_id}", response_model=CodeProblemResponse)
async def update_problem(
    problem_id: int,
    body: CodeProblemUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Partially update a coding lab problem. Requires admin or teacher role."""
    if user.role not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="Admin or teacher role required")
    result = await db.execute(select(CodeProblem).where(CodeProblem.id == problem_id))
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if body.title is not None:
        problem.title = body.title
    if body.difficulty is not None:
        problem.difficulty = body.difficulty
    if body.points is not None:
        problem.points = body.points
    if body.description is not None:
        problem.description = body.description
    if body.requirements is not None:
        problem.requirements_json = json.dumps(body.requirements)
    if body.expectedOutput is not None:
        problem.expected_output = body.expectedOutput
    if body.hints is not None:
        problem.hints_json = json.dumps(body.hints)
    if body.starterCode is not None:
        problem.starter_code_json = json.dumps(body.starterCode)
    if body.topics is not None:
        problem.topics = body.topics
    if body.sortOrder is not None:
        problem.sort_order = body.sortOrder
    if body.isActive is not None:
        problem.is_active = body.isActive
    await db.commit()
    await db.refresh(problem)
    return _problem_to_response(problem)


@router.delete("/problems/{problem_id}", status_code=204)
async def delete_problem(
    problem_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Soft-delete a coding lab problem (sets is_active=False). Requires admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    result = await db.execute(select(CodeProblem).where(CodeProblem.id == problem_id))
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    problem.is_active = False
    await db.commit()
