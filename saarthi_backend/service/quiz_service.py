"""Quiz feature service: quizzes, questions, attempts, adaptive generation."""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao import QuizAttemptDAO, QuizDAO, QuizQuestionDAO
from saarthi_backend.model import Quiz, QuizAttempt, QuizQuestion
from saarthi_backend.schema.quiz_schemas import (
    AdaptiveQuizRequest,
    AdaptiveQuizResponse,
    GeneratedQuizQuestion,
)

logger = logging.getLogger(__name__)


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


# ─── Adaptive Quiz Generation ─────────────────────────────────────────────────

_QUIZ_GEN_SYSTEM = """You are an expert engineering professor creating adaptive quiz questions.
Analyze the student's past performance and generate targeted questions.

Return ONLY valid JSON with this structure:
{
  "title": "Quiz title",
  "difficulty": "easy|medium|hard",
  "weakAreasDetected": ["topic1", "topic2"],
  "questions": [
    {
      "questionText": "...",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correctIndex": 0,
      "explanation": "Brief explanation of why this answer is correct",
      "difficulty": "easy|medium|hard",
      "topic": "specific sub-topic"
    }
  ]
}

Rules:
- If student scored < 60% previously, generate 60% easy + 40% medium questions
- If student scored 60-80%, generate 30% easy + 50% medium + 20% hard
- If student scored > 80% or no history, generate 20% medium + 80% hard
- Focus extra questions on topics where student got answers wrong
- Questions must be specific and technically accurate for engineering students
- Each option must be plausible (no obviously wrong answers)"""


async def generate_adaptive_quiz(
    db: AsyncSession,
    user_id: int,
    body: AdaptiveQuizRequest,
) -> AdaptiveQuizResponse:
    """Use GPT-4.1 to generate an adaptive quiz based on past attempt analysis."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        # Analyze past performance
        avg_score = 0.0
        weak_areas: list[str] = []
        if body.pastAttempts:
            scores = [a.score for a in body.pastAttempts]
            avg_score = sum(scores) / len(scores)

        # Determine target difficulty
        difficulty = body.difficulty or "auto"
        if difficulty == "auto":
            if not body.pastAttempts:
                difficulty = "medium"
            elif avg_score < 60:
                difficulty = "easy-medium"
            elif avg_score < 80:
                difficulty = "medium"
            else:
                difficulty = "hard"

        attempts_text = ""
        if body.pastAttempts:
            attempts_text = f"\nPast performance on {body.topic}:\n"
            for a in body.pastAttempts[-3:]:  # last 3 attempts
                attempts_text += f"- {a.quizTitle}: {a.score:.0f}%\n"
            attempts_text += f"Average score: {avg_score:.0f}%\n"

        user_prompt = f"""Generate {body.numQuestions} adaptive quiz questions on: {body.topic}
{"Course: " + body.courseTitle if body.courseTitle else ""}
Target difficulty: {difficulty}{attempts_text}

Focus on making questions that test deep understanding, not just memorization.
For engineering students studying signals, systems, ML, or algorithms."""

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _QUIZ_GEN_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        questions = [
            GeneratedQuizQuestion(
                questionText=q["questionText"],
                options=q.get("options", []),
                correctIndex=int(q.get("correctIndex", 0)),
                explanation=q.get("explanation", ""),
                difficulty=q.get("difficulty", difficulty),
                topic=q.get("topic", body.topic),
            )
            for q in data.get("questions", [])
        ]

        return AdaptiveQuizResponse(
            title=data.get("title", f"Adaptive Quiz: {body.topic}"),
            topic=body.topic,
            difficulty=difficulty,
            questions=questions,
            weakAreasDetected=data.get("weakAreasDetected", weak_areas),
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.exception("Adaptive quiz generation failed: %s", e)
        return AdaptiveQuizResponse(
            title=f"Quiz: {body.topic}",
            topic=body.topic,
            difficulty=body.difficulty or "medium",
            questions=[],
            weakAreasDetected=[],
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )
