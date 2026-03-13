"""DAO for quizzes and attempts."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model import Quiz, QuizQuestion, QuizAttempt


class QuizDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, quiz_id: int) -> Quiz | None:
        result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        db: AsyncSession,
        course_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Quiz]:
        q = select(Quiz).order_by(Quiz.id).limit(limit).offset(offset)
        if course_id is not None:
            q = q.where(Quiz.course_id == course_id)
        result = await db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def count_all(db: AsyncSession, course_id: int | None = None) -> int:
        q = select(func.count()).select_from(Quiz)
        if course_id is not None:
            q = q.where(Quiz.course_id == course_id)
        r = await db.execute(q)
        return r.scalar() or 0


class QuizQuestionDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, question_id: int) -> QuizQuestion | None:
        result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_quiz(db: AsyncSession, quiz_id: int) -> list[QuizQuestion]:
        result = await db.execute(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz_id)
            .order_by(QuizQuestion.sort_order, QuizQuestion.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        quiz_id: int,
        question_text: str,
        options_json: str,
        correct_index: int,
        sort_order: int = 0,
    ) -> QuizQuestion:
        q = QuizQuestion(
            quiz_id=quiz_id,
            question_text=question_text,
            options_json=options_json,
            correct_index=correct_index,
            sort_order=sort_order,
        )
        db.add(q)
        await db.flush()
        await db.refresh(q)
        return q

    @staticmethod
    async def update(
        db: AsyncSession,
        question_id: int,
        question_text: str | None = None,
        options_json: str | None = None,
        correct_index: int | None = None,
        sort_order: int | None = None,
    ) -> QuizQuestion | None:
        q = await QuizQuestionDAO.get_by_id(db, question_id)
        if not q:
            return None
        if question_text is not None:
            q.question_text = question_text
        if options_json is not None:
            q.options_json = options_json
        if correct_index is not None:
            q.correct_index = correct_index
        if sort_order is not None:
            q.sort_order = sort_order
        await db.flush()
        await db.refresh(q)
        return q

    @staticmethod
    async def delete(db: AsyncSession, question_id: int) -> bool:
        q = await QuizQuestionDAO.get_by_id(db, question_id)
        if not q:
            return False
        await db.delete(q)
        await db.flush()
        return True


class QuizAttemptDAO:
    @staticmethod
    async def get_by_id(db: AsyncSession, attempt_id: int) -> QuizAttempt | None:
        result = await db.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        submitted_only: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[QuizAttempt]:
        q = (
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if submitted_only:
            q = q.where(QuizAttempt.submitted_at.isnot(None))
        result = await db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def count_by_user(
        db: AsyncSession, user_id: int, submitted_only: bool = False
    ) -> int:
        q = select(func.count()).select_from(QuizAttempt).where(
            QuizAttempt.user_id == user_id
        )
        if submitted_only:
            q = q.where(QuizAttempt.submitted_at.isnot(None))
        r = await db.execute(q)
        return r.scalar() or 0

    @staticmethod
    async def list_by_user_quiz(
        db: AsyncSession,
        user_id: int,
        quiz_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[QuizAttempt]:
        result = await db.execute(
            select(QuizAttempt)
            .where(
                QuizAttempt.user_id == user_id,
                QuizAttempt.quiz_id == quiz_id,
            )
            .order_by(QuizAttempt.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_user_quiz(
        db: AsyncSession, user_id: int, quiz_id: int
    ) -> int:
        r = await db.execute(
            select(func.count())
            .select_from(QuizAttempt)
            .where(
                QuizAttempt.user_id == user_id,
                QuizAttempt.quiz_id == quiz_id,
            )
        )
        return r.scalar() or 0

    @staticmethod
    async def create(db: AsyncSession, user_id: int, quiz_id: int) -> QuizAttempt:
        a = QuizAttempt(user_id=user_id, quiz_id=quiz_id)
        db.add(a)
        await db.flush()
        await db.refresh(a)
        return a

    @staticmethod
    async def submit(
        db: AsyncSession,
        attempt_id: int,
        user_id: int,
        score: float,
        answers_json: str,
    ) -> QuizAttempt | None:
        a = await QuizAttemptDAO.get_by_id(db, attempt_id)
        if not a or a.user_id != user_id:
            return None
        a.score = score
        a.answers_json = answers_json
        a.submitted_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(a)
        return a
