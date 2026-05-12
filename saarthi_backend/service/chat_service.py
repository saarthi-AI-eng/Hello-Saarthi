"""Chat feature service: conversations, messages, study plan, socratic mode, concept graph, exam prediction."""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.ai import run_chat
from saarthi_backend.dao import ChatMessageDAO, ConversationDAO
from saarthi_backend.model import ChatMessage, Conversation
from saarthi_backend.schema.chat_schemas import (
    ConceptGraphResponse,
    ConceptNode,
    ExamPredictionRequest,
    ExamPredictionResponse,
    ExamPredictionTopic,
    Flashcard,
    FlashcardDeckRequest,
    FlashcardDeckResponse,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
    SocraticChallengeRequest,
    SocraticChallengeResponse,
    StudyPlanDayBlock,
    StudyPlanQuizScore,
    StudyPlanRequest,
    StudyPlanResponse,
)

logger = logging.getLogger(__name__)


async def create_conversation(db: AsyncSession, user_id: int, title: str = "New Chat") -> Conversation:
    return await ConversationDAO.create(db, user_id, title=title)


async def list_conversations(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> tuple[list[Conversation], int]:
    items = await ConversationDAO.list_by_user(db, user_id, limit=limit, offset=offset)
    total = await ConversationDAO.count_by_user(db, user_id)
    return items, total


async def get_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> tuple[Conversation | None, list[ChatMessage]]:
    c = await ConversationDAO.get_by_id(db, conversation_id, user_id)
    if not c:
        return None, []
    messages = await ChatMessageDAO.list_by_conversation(db, conversation_id)
    return c, messages


async def update_conversation_title(
    db: AsyncSession, conversation_id: int, user_id: int, title: str
) -> Conversation | None:
    return await ConversationDAO.update_title(db, conversation_id, user_id, title)


async def delete_conversation(db: AsyncSession, conversation_id: int, user_id: int) -> bool:
    return await ConversationDAO.delete(db, conversation_id, user_id)


_KB_AGENTS = ["books_agent", "notes_agent", "video_agent"]


def _fetch_faiss_context(query: str, material_title: str) -> str:
    """Search all FAISS indexes for chunks relevant to the query + material title."""
    try:
        from pathlib import Path
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        kb_root = Path("knowledge_base")
        all_chunks: list[str] = []

        for agent in _KB_AGENTS:
            index_path = kb_root / agent / "vector_store"
            if not index_path.exists():
                continue
            try:
                vs = FAISS.load_local(
                    str(index_path), embeddings, allow_dangerous_deserialization=True
                )
                # Search with both the question and the material title for better recall
                docs = vs.similarity_search(f"{material_title} {query}", k=3)
                for d in docs:
                    src = d.metadata.get("source", "")
                    title_lower = material_title.lower()
                    # Only include chunks that plausibly belong to this material
                    if title_lower in src.lower() or not src:
                        all_chunks.append(d.page_content.strip())
                    else:
                        # Include anyway if no source info — better to over-include
                        if not src:
                            all_chunks.append(d.page_content.strip())
            except Exception:
                continue

        return "\n\n---\n\n".join(all_chunks[:5])  # top 5 chunks across all agents
    except Exception:
        return ""


def _apply_document_context(message: str, context_material_title: str | None) -> str:
    """Enrich prompt with real FAISS chunks from the viewed document."""
    if not context_material_title or not context_material_title.strip():
        return message
    title = context_material_title.strip()
    kb_context = _fetch_faiss_context(message, title)
    if kb_context:
        return (
            f'The user is studying the document "{title}".\n\n'
            f"Relevant excerpts from the knowledge base:\n{kb_context}\n\n"
            f"Using those excerpts as grounding, answer the student's question:\n{message}"
        )
    return (
        f'The user is currently viewing the document "{title}". '
        f"Answer their question in that context when relevant.\n\nQuestion: {message}"
    )


async def send_message(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
    message: str,
    context_material_title: str | None = None,
) -> tuple[ChatMessage, ChatMessage] | None:
    conv = await ConversationDAO.get_by_id(db, conversation_id, user_id)
    if not conv:
        return None
    existing = await ChatMessageDAO.list_by_conversation(db, conversation_id)
    user_msg = await ChatMessageDAO.create(db, conversation_id, "user", message)
    history = [{"role": m.role, "content": m.content} for m in existing]
    prompt_for_ai = _apply_document_context(message, context_material_title)
    history.append({"role": "user", "content": prompt_for_ai})
    assistant_content = await run_chat(prompt_for_ai, history, mind_mode=False)
    assistant_msg = await ChatMessageDAO.create(db, conversation_id, "assistant", assistant_content)
    if len(existing) == 0:
        title = (message.strip()[:200] + "…") if len(message.strip()) > 200 else message.strip()
        await ConversationDAO.update_title(db, conversation_id, user_id, title or "New Chat")
    await ConversationDAO.touch(db, conversation_id)
    return user_msg, assistant_msg


async def stateless_message(
    message: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
    context_material_title: str | None = None,
) -> str:
    history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in conversation_history]
    prompt_for_ai = _apply_document_context(message, context_material_title)
    history.append({"role": "user", "content": prompt_for_ai})
    return await run_chat(prompt_for_ai, history, mind_mode=mind_mode)


# ─── Study Plan Generator ─────────────────────────────────────────────────────

_STUDY_PLAN_SYSTEM = """You are an expert academic advisor for engineering students.
Generate a structured 7-day weekly study plan in valid JSON.

Rules:
- Prioritize topics where quiz scores are low (< 70%)
- Front-load urgent deadlines to earlier days
- Balance subjects — don't study same subject >2 consecutive sessions
- Each session = 90 minutes
- Include specific topics, not generic advice
- Return ONLY a JSON object with this exact structure:
{
  "weekPlan": [
    {
      "day": "Monday",
      "sessions": ["09:00–10:30 · DSP: Z-transform review (weak area)", "..."],
      "totalHours": 3.0
    }
  ],
  "summary": "one paragraph summary",
  "priorityTopics": ["topic1", "topic2", "topic3"]
}"""


async def generate_study_plan(
    db: AsyncSession,
    user_id: int,
    body: StudyPlanRequest,
) -> StudyPlanResponse:
    """Call GPT-4.1 to generate a personalized weekly study plan."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        # Build context summary
        courses_text = "\n".join(
            f"- {c.title} ({c.code}): {c.progressPercent}% complete"
            for c in body.courses
        ) or "No enrolled courses provided."

        deadlines_text = "\n".join(
            f"- {d.title} [{d.type}] for {d.course} — due {d.dueDate}"
            for d in sorted(body.deadlines, key=lambda x: x.dueDate)
        ) or "No upcoming deadlines."

        scores_text = "\n".join(
            f"- {q.quizTitle}: {q.score:.0f}% " +
            (f"(weak: {', '.join(q.weakTopics)})" if q.weakTopics else "")
            for q in body.recentQuizScores
        ) or "No recent quiz data."

        focus_text = f"\nStudent wants to focus on: {body.focusArea}" if body.focusArea else ""

        user_prompt = f"""Student profile:
Available hours per day: {body.hoursPerDay}h{focus_text}

Enrolled courses:
{courses_text}

Upcoming deadlines:
{deadlines_text}

Recent quiz performance:
{scores_text}

Generate a 7-day study plan."""

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _STUDY_PLAN_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        week_plan = [
            StudyPlanDayBlock(
                day=d["day"],
                sessions=d.get("sessions", []),
                totalHours=float(d.get("totalHours", 0)),
            )
            for d in data.get("weekPlan", [])
        ]

        return StudyPlanResponse(
            weekPlan=week_plan,
            summary=data.get("summary", ""),
            priorityTopics=data.get("priorityTopics", []),
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.exception("Study plan generation failed: %s", e)
        return StudyPlanResponse(
            weekPlan=[],
            summary="Could not generate study plan. Please try again.",
            priorityTopics=[],
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )


# ─── Socratic Challenge Mode ───────────────────────────────────────────────────

_SOCRATIC_SYSTEM = """You are a Socratic tutor for engineering students. Your job is NOT to explain —
it is to challenge the student's claim using the Socratic method.

- Ask sharp probing questions that expose gaps in reasoning
- If the student is wrong, don't say so directly — lead them to discover it
- If the student is correct, push them deeper: "Why does that hold? What breaks this assumption?"
- Keep your challenge to 2-3 sentences maximum
- Provide 2 short hints the student can reveal if stuck
- After full analysis, give a verdict: "correct" | "partially_correct" | "incorrect"

Return ONLY valid JSON:
{
  "challenge": "...",
  "hints": ["hint1", "hint2"],
  "verdict": "correct|partially_correct|incorrect",
  "explanation": "full correct explanation"
}"""


async def socratic_challenge(body: SocraticChallengeRequest) -> SocraticChallengeResponse:
    """Generate a Socratic counter-challenge to a student's claim."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        difficulty_map = {
            "gentle": "Be encouraging and ask one soft question.",
            "moderate": "Challenge them firmly but fairly.",
            "rigorous": "Be relentless. Find every flaw. Don't accept vague answers.",
        }

        user_prompt = (
            f"Topic: {body.topic}\n"
            + (f"Course: {body.courseTitle}\n" if body.courseTitle else "")
            + f"Student's claim: \"{body.claim}\"\n"
            f"Difficulty level: {difficulty_map[body.difficulty]}"
        )

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _SOCRATIC_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=600,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content or "{}")
        return SocraticChallengeResponse(
            challenge=data.get("challenge", "Can you explain your reasoning further?"),
            hints=data.get("hints", []),
            verdict=data.get("verdict"),
            explanation=data.get("explanation", ""),
        )
    except Exception as e:
        logger.exception("Socratic challenge failed: %s", e)
        return SocraticChallengeResponse(
            challenge="Interesting claim. Can you walk me through how you arrived at that conclusion?",
            hints=["Think about the definition", "Consider the edge cases"],
            verdict=None,
            explanation="",
        )


# ─── Concept Graph ─────────────────────────────────────────────────────────────

_CONCEPT_GRAPH_SYSTEM = """You are an expert in engineering curriculum design.
Given a course title and quiz performance data, generate a concept dependency graph.

Return ONLY valid JSON:
{
  "nodes": [
    {
      "id": "unique_slug",
      "label": "Human readable name",
      "topic": "parent topic",
      "mastery": 0.0,
      "prereqs": ["id_of_prereq1"]
    }
  ]
}

Rules:
- Generate 12-20 nodes covering core concepts of the course
- mastery: derive from quiz scores where topic matches; default 0.5 if unknown
- prereqs: list ids of concepts that must be understood first
- Keep ids lowercase_with_underscores
- Cover foundational → advanced progression"""


async def generate_concept_graph(
    course_title: str,
    quiz_scores: list[StudyPlanQuizScore],
) -> ConceptGraphResponse:
    """Build a concept dependency graph with mastery levels from quiz history."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        scores_text = "\n".join(
            f"- {q.quizTitle}: {q.score:.0f}%" + (f" (weak: {', '.join(q.weakTopics)})" if q.weakTopics else "")
            for q in quiz_scores
        ) or "No quiz data available."

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _CONCEPT_GRAPH_SYSTEM},
                {"role": "user", "content": f"Course: {course_title}\n\nQuiz performance:\n{scores_text}"},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content or "{}")
        nodes = [
            ConceptNode(
                id=n["id"],
                label=n["label"],
                topic=n.get("topic", ""),
                mastery=float(n.get("mastery", 0.5)),
                prereqs=n.get("prereqs", []),
            )
            for n in data.get("nodes", [])
        ]
        return ConceptGraphResponse(nodes=nodes, generatedAt=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        logger.exception("Concept graph generation failed: %s", e)
        return ConceptGraphResponse(nodes=[], generatedAt=datetime.now(timezone.utc).isoformat())


# ─── Exam Prediction ───────────────────────────────────────────────────────────

_EXAM_PRED_SYSTEM = """You are an expert at predicting exam topics for engineering courses.
Analyze quiz performance and course content to predict the most likely exam topics.

Return ONLY valid JSON:
{
  "predictions": [
    {
      "topic": "topic name",
      "probability": 85,
      "readiness": 60,
      "action": "review|practice|ready"
    }
  ],
  "topPriority": "one sentence: most important thing to do right now"
}

Rules:
- Generate 6-10 topic predictions
- probability: likelihood this topic appears (0-100)
- readiness: how prepared the student is based on quiz scores (0-100)
- action: "review" if readiness<50, "practice" if 50-79, "ready" if >=80
- topPriority must be specific and actionable"""


async def predict_exam_topics(body: ExamPredictionRequest) -> ExamPredictionResponse:
    """Predict likely exam topics and student readiness for each."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        scores_text = "\n".join(
            f"- {q.quizTitle}: {q.score:.0f}%" + (f" (weak: {', '.join(q.weakTopics)})" if q.weakTopics else "")
            for q in body.recentQuizScores
        ) or "No quiz data."

        notes_text = ", ".join(body.notesTopics) if body.notesTopics else "No notes data."

        user_prompt = (
            f"Course: {body.courseTitle}\n"
            f"Hours until exam: {body.hoursUntilExam}\n\n"
            f"Quiz performance:\n{scores_text}\n\n"
            f"Topics covered in notes: {notes_text}"
        )

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _EXAM_PRED_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content or "{}")
        predictions = [
            ExamPredictionTopic(
                topic=p["topic"],
                probability=float(p.get("probability", 50)),
                readiness=float(p.get("readiness", 50)),
                action=p.get("action", "review"),
            )
            for p in data.get("predictions", [])
        ]
        return ExamPredictionResponse(
            predictions=predictions,
            topPriority=data.get("topPriority", "Review your weakest topics first."),
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.exception("Exam prediction failed: %s", e)
        return ExamPredictionResponse(
            predictions=[],
            topPriority="Focus on topics with the lowest quiz scores.",
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )


# ─── Flashcard Generation (Spaced Repetition) ─────────────────────────────────

_FLASHCARD_SYSTEM = """You are an expert at creating Anki-style flashcards for engineering students.
Extract the most important facts, definitions, formulas, and concepts from the provided text.

Return ONLY valid JSON:
{
  "cards": [
    {
      "front": "concise question or prompt",
      "back": "precise answer (include formula if applicable)",
      "topic": "sub-topic name",
      "difficulty": "easy|medium|hard"
    }
  ]
}

Rules:
- Prefer atomic cards (one fact per card)
- Formulas should appear in the back with a brief explanation
- difficulty: easy=definition, medium=application, hard=derivation/analysis
- Vary difficulty: ~30% easy, 40% medium, 30% hard
- Never duplicate semantically equivalent cards"""


async def generate_flashcards(body: FlashcardDeckRequest) -> FlashcardDeckResponse:
    """Extract flashcards from a note or transcript using GPT-4.1."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        user_prompt = (
            f"Topic: {body.topic}\n"
            + (f"Course: {body.courseTitle}\n" if body.courseTitle else "")
            + f"Generate up to {body.maxCards} flashcards from this text:\n\n{body.sourceText[:6000]}"
        )

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _FLASHCARD_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content or "{}")
        now = datetime.now(timezone.utc)
        cards = [
            Flashcard(
                id=str(i + 1),
                front=c["front"],
                back=c["back"],
                topic=c.get("topic", body.topic),
                difficulty=c.get("difficulty", "medium"),
                nextReviewAt=now.isoformat(),
                interval=1,
                easeFactor=2.5,
            )
            for i, c in enumerate(data.get("cards", [])[: body.maxCards])
        ]
        return FlashcardDeckResponse(
            topic=body.topic,
            cards=cards,
            generatedAt=now.isoformat(),
        )
    except Exception as e:
        logger.exception("Flashcard generation failed: %s", e)
        return FlashcardDeckResponse(
            topic=body.topic, cards=[], generatedAt=datetime.now(timezone.utc).isoformat()
        )


def compute_sm2_review(body: FlashcardReviewRequest) -> FlashcardReviewResponse:
    """SM-2 spaced repetition algorithm — compute next review interval."""
    q = body.quality
    ef = body.currentEaseFactor
    interval = body.currentInterval

    if q < 3:
        interval = 1
    elif interval == 1:
        interval = 6
    else:
        interval = round(interval * ef)

    ef = max(1.3, ef + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    next_review = (datetime.now(timezone.utc) + timedelta(days=interval)).isoformat()
    return FlashcardReviewResponse(nextInterval=interval, nextEaseFactor=ef, nextReviewAt=next_review)
