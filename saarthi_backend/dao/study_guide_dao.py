"""DAO for study guides and their prompts."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model.study_guide_model import StudyGuide, StudyGuidePrompt


class StudyGuideDAO:
    @staticmethod
    async def list_all(db: AsyncSession) -> list[StudyGuide]:
        q = select(StudyGuide).order_by(StudyGuide.created_at.desc())
        r = await db.execute(q)
        return list(r.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, guide_id: int) -> StudyGuide | None:
        r = await db.execute(select(StudyGuide).where(StudyGuide.id == guide_id))
        return r.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, title: str, description: str | None, created_by: int) -> StudyGuide:
        g = StudyGuide(title=title, description=description, created_by=created_by)
        db.add(g)
        await db.flush()
        await db.refresh(g)
        return g

    @staticmethod
    async def delete(db: AsyncSession, guide_id: int) -> bool:
        g = await StudyGuideDAO.get_by_id(db, guide_id)
        if not g:
            return False
        await db.delete(g)
        await db.flush()
        return True


class StudyGuidePromptDAO:
    @staticmethod
    async def list_by_guide(db: AsyncSession, guide_id: int) -> list[StudyGuidePrompt]:
        q = (
            select(StudyGuidePrompt)
            .where(StudyGuidePrompt.guide_id == guide_id)
            .order_by(StudyGuidePrompt.step_number)
        )
        r = await db.execute(q)
        return list(r.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, guide_id: int, step_number: int, title: str, prompt_text: str) -> StudyGuidePrompt:
        p = StudyGuidePrompt(guide_id=guide_id, step_number=step_number, title=title, prompt_text=prompt_text)
        db.add(p)
        await db.flush()
        await db.refresh(p)
        return p

    @staticmethod
    async def delete(db: AsyncSession, prompt_id: int) -> bool:
        r = await db.execute(select(StudyGuidePrompt).where(StudyGuidePrompt.id == prompt_id))
        p = r.scalar_one_or_none()
        if not p:
            return False
        await db.delete(p)
        await db.flush()
        return True

    @staticmethod
    async def next_step_number(db: AsyncSession, guide_id: int) -> int:
        prompts = await StudyGuidePromptDAO.list_by_guide(db, guide_id)
        return (max((p.step_number for p in prompts), default=0) + 1)
