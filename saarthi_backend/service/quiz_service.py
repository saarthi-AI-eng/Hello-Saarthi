"""Quiz feature service: quizzes, questions, attempts."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import QuizAttemptDAO, QuizDAO, QuizQuestionDAO
from saarthi_backend.model import Quiz, QuizAttempt, QuizQuestion


async def list_quizzes(
    db: AsyncSession,
    course_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Quiz], int]:
    quizzes = await QuizDAO.list_all(db, course_id=course_id, limit=limit, offset=offset)
    total = await QuizDAO.count_all(db, course_id=course_id)
    return quizzes, total


async def get_quiz_with_questions(
    db: AsyncSession, quiz_id: int
) -> tuple[Quiz | None, list[QuizQuestion]]:
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        return None, []
    questions = await QuizQuestionDAO.list_by_quiz(db, quiz_id)
    return quiz, questions


async def start_attempt(db: AsyncSession, user_id: int, quiz_id: int) -> QuizAttempt | None:
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        return None
    return await QuizAttemptDAO.create(db, user_id, quiz_id)


async def submit_attempt(
    db: AsyncSession,
    attempt_id: int,
    user_id: int,
    score: float,
    answers_json: str,
) -> QuizAttempt | None:
    return await QuizAttemptDAO.submit(
        db, attempt_id, user_id, score=score, answers_json=answers_json
    )


async def list_attempts(
    db: AsyncSession,
    user_id: int,
    quiz_id: int,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[QuizAttempt], int]:
    items = await QuizAttemptDAO.list_by_user_quiz(db, user_id, quiz_id, limit=limit, offset=offset)
    total = await QuizAttemptDAO.count_by_user_quiz(db, user_id, quiz_id)
    return items, total


async def create_question(
    db: AsyncSession,
    quiz_id: int,
    question_text: str,
    options_json: str,
    correct_index: int,
    sort_order: int = 0,
) -> QuizQuestion | None:
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        return None
    return await QuizQuestionDAO.create(
        db,
        quiz_id=quiz_id,
        question_text=question_text,
        options_json=options_json,
        correct_index=correct_index,
        sort_order=sort_order,
    )


async def update_question(
    db: AsyncSession,
    quiz_id: int,
    question_id: int,
    question_text: str | None = None,
    options_json: str | None = None,
    correct_index: int | None = None,
    sort_order: int | None = None,
) -> QuizQuestion | None:
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        return None
    q = await QuizQuestionDAO.get_by_id(db, question_id)
    if not q or q.quiz_id != quiz_id:
        return None
    return await QuizQuestionDAO.update(
        db,
        question_id,
        question_text=question_text,
        options_json=options_json,
        correct_index=correct_index,
        sort_order=sort_order,
    )


async def delete_question(
    db: AsyncSession, quiz_id: int, question_id: int
) -> bool:
    quiz = await QuizDAO.get_by_id(db, quiz_id)
    if not quiz:
        return False
    q = await QuizQuestionDAO.get_by_id(db, question_id)
    if not q or q.quiz_id != quiz_id:
        return False
    await QuizQuestionDAO.delete(db, question_id)
    return True
