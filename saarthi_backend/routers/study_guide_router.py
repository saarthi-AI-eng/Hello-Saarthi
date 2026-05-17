"""Study guide routes: teacher CRUD + student read."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao.study_guide_dao import StudyGuideDAO, StudyGuidePromptDAO
from saarthi_backend.deps import get_current_user, get_db
from saarthi_backend.model import User
from saarthi_backend.schema.study_guide_schemas import (
    CreateGuideRequest,
    CreatePromptRequest,
    GuideItem,
    PromptItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/study-guides", tags=["study-guides"])


def _is_teacher(user: User) -> bool:
    return (user.role or "student") in ("teacher", "admin")


def _prompt_to_item(p) -> PromptItem:
    return PromptItem(
        id=p.id,
        guide_id=p.guide_id,
        step_number=p.step_number,
        title=p.title,
        prompt_text=p.prompt_text,
        created_at=p.created_at,
    )


def _guide_to_item(g, prompts=None) -> GuideItem:
    return GuideItem(
        id=g.id,
        title=g.title,
        description=g.description,
        created_by=g.created_by,
        created_at=g.created_at,
        prompts=[_prompt_to_item(p) for p in (prompts or [])],
    )


# ── List all guides (students + teachers) ─────────────────────────────────────

@router.get("", response_model=list[GuideItem])
async def list_guides(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    guides = await StudyGuideDAO.list_all(db)
    result = []
    for g in guides:
        prompts = await StudyGuidePromptDAO.list_by_guide(db, g.id)
        result.append(_guide_to_item(g, prompts))
    return result


# ── Create guide (teachers only) ──────────────────────────────────────────────

@router.post("", response_model=GuideItem, status_code=201)
async def create_guide(
    body: CreateGuideRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not _is_teacher(user):
        raise HTTPException(status_code=403, detail="Only teachers can create study guides.")
    g = await StudyGuideDAO.create(db, body.title, body.description, user.id)
    await db.commit()
    return _guide_to_item(g, [])


# ── Delete guide (teachers only) ──────────────────────────────────────────────

@router.delete("/{guide_id}", status_code=204)
async def delete_guide(
    guide_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not _is_teacher(user):
        raise HTTPException(status_code=403, detail="Only teachers can delete study guides.")
    deleted = await StudyGuideDAO.delete(db, guide_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Guide not found.")
    await db.commit()


# ── Add prompt to guide (teachers only) ───────────────────────────────────────

@router.post("/{guide_id}/prompts", response_model=PromptItem, status_code=201)
async def add_prompt(
    guide_id: int,
    body: CreatePromptRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not _is_teacher(user):
        raise HTTPException(status_code=403, detail="Only teachers can add prompts.")
    g = await StudyGuideDAO.get_by_id(db, guide_id)
    if not g:
        raise HTTPException(status_code=404, detail="Guide not found.")
    step = await StudyGuidePromptDAO.next_step_number(db, guide_id)
    p = await StudyGuidePromptDAO.create(db, guide_id, step, body.title, body.prompt_text)
    await db.commit()
    return _prompt_to_item(p)


# ── Delete prompt (teachers only) ─────────────────────────────────────────────

@router.delete("/{guide_id}/prompts/{prompt_id}", status_code=204)
async def delete_prompt(
    guide_id: int,
    prompt_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not _is_teacher(user):
        raise HTTPException(status_code=403, detail="Only teachers can delete prompts.")
    deleted = await StudyGuidePromptDAO.delete(db, prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prompt not found.")
    await db.commit()
