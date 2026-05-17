"""Chat routes: stateless message, conversation CRUD, SSE stream, study plan, socratic, concept graph, exam prediction, flashcards."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.chat_schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatMessageResponseItem,
    ConceptGraphResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    ExamPredictionRequest,
    ExamPredictionResponse,
    FlashcardDeckRequest,
    FlashcardDeckResponse,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
    SendMessageRequest,
    SendMessageResponse,
    SocraticChallengeRequest,
    SocraticChallengeResponse,
    StreamMessageRequest,
    StudyPlanRequest,
    StudyPlanResponse,
    UpdateConversationRequest,
)
from saarthi_backend.schema.common_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.service import chat_service
from saarthi_backend.utils.exceptions import NotFoundError

router = APIRouter(prefix="/chat", tags=["chat"])


def _conversation_to_response(c) -> ConversationResponse:
    return ConversationResponse(
        id=str(c.id),
        title=c.title,
        createdAt=c.created_at.isoformat(),
        updatedAt=c.updated_at.isoformat(),
    )


def _message_to_item(m) -> ChatMessageResponseItem:
    return ChatMessageResponseItem(
        id=str(m.id),
        role=m.role,
        content=m.content,
        createdAt=m.created_at.isoformat(),
    )


# ─── Stateless (AIChatbot widget) ────────────────────────────────────────────

@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(body: ChatMessageRequest):
    """Stateless chat (AIChatbot, material viewer). No persistence."""
    history = [{"role": m.role, "content": m.content} for m in body.conversationHistory]
    answer = await chat_service.stateless_message(
        body.message, history,
        context_material_title=body.contextMaterialTitle,
        course_id=body.courseId,
        context_video_id=body.contextVideoId,
        context_video_title=body.contextVideoTitle,
    )
    return ChatMessageResponse(response=answer)


# ─── SSE Streaming endpoint ───────────────────────────────────────────────────

@router.post("/stream")
async def stream_message(
    request: Request,
    body: StreamMessageRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Stream an AI response token-by-token via Server-Sent Events.
    Also persists the full exchange to the conversation when complete.
    """
    raw_history = [{"role": m.role, "content": m.content} for m in body.conversationHistory]

    from saarthi_backend.ai.adapter import run_chat_stream
    from saarthi_backend.service.chat_service import _apply_document_context, _apply_video_context
    from saarthi_backend.service.memory_service import build_context, maybe_update_summary_bg
    from saarthi_backend.dao import ChatMessageDAO, ConversationDAO

    # Build memory-trimmed context (Tier 1 + Tier 2 summary injection)
    conv_id_int = int(body.conversationId) if body.conversationId else None
    if conv_id_int:
        history = await build_context(db, conv_id_int, raw_history)
    else:
        history = raw_history[-6:]

    if body.contextVideoId:
        prompt, is_grounded = _apply_video_context(body.message, body.contextVideoId, body.contextVideoTitle)
    else:
        prompt, is_grounded = _apply_document_context(body.message, body.contextMaterialTitle, course_id=body.courseId)

    async def event_generator():
        import asyncio
        full_response = []
        from saarthi_backend.ai import run_document_chat
        if is_grounded:
            answer = await run_document_chat(prompt, history)
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk_text = word + (" " if i < len(words) - 1 else "")
                yield f"data: {chunk_text.replace(chr(10), chr(92) + 'n')}\n\n"
                full_response.append(chunk_text)
                await asyncio.sleep(0.012)
            yield "data: [DONE]\n\n"
        else:
            async for chunk in run_chat_stream(prompt, history, planning=body.planning):
                yield chunk
                if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                    token = chunk[6:].rstrip("\n").replace("\\n", "\n")
                    full_response.append(token)

        # Persist to DB after streaming completes, then trigger lazy summarization
        try:
            if conv_id_int:
                conv = await ConversationDAO.get_by_id(db, conv_id_int, user.id)
                if conv:
                    await ChatMessageDAO.create(db, conv_id_int, "user", body.message)
                    assistant_content = "".join(full_response)
                    await ChatMessageDAO.create(db, conv_id_int, "assistant", assistant_content)
                    await ConversationDAO.touch(db, conv_id_int)
                    await db.commit()

                    # Lazy memory update — runs after response is fully sent, never blocks user
                    # Uses a fresh DB session (not the request-scoped one) to avoid asyncpg conflict
                    try:
                        all_msgs = await ChatMessageDAO.list_by_conversation(db, conv_id_int)
                        session_factory = request.app.state.db_session_factory
                        asyncio.ensure_future(maybe_update_summary_bg(session_factory, conv_id_int, all_msgs))
                    except Exception as mem_err:
                        import logging
                        logging.getLogger(__name__).debug("Memory update skipped: %s", mem_err)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to persist streamed message: %s", e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Study Plan Generator ─────────────────────────────────────────────────────

@router.post("/study-plan", response_model=StudyPlanResponse)
async def generate_study_plan(
    body: StudyPlanRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a personalized weekly study plan based on enrollments, deadlines, and quiz scores."""
    plan = await chat_service.generate_study_plan(db, user.id, body)
    return plan


# ─── Conversations ────────────────────────────────────────────────────────────

@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    c = await chat_service.create_conversation(db, user.id, title=body.title)
    await db.commit()
    return _conversation_to_response(c)


@router.get("/conversations", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    items, total = await chat_service.list_conversations(
        db, user.id, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse(
        items=[_conversation_to_response(c) for c in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    c, messages = await chat_service.get_conversation(db, conversation_id, user.id)
    if not c:
        raise NotFoundError("Conversation not found.", details=None)
    return ConversationDetailResponse(
        id=str(c.id),
        title=c.title,
        createdAt=c.created_at.isoformat(),
        updatedAt=c.updated_at.isoformat(),
        messages=[_message_to_item(m) for m in messages],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    body: UpdateConversationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    c = await chat_service.update_conversation_title(db, conversation_id, user.id, body.title)
    if not c:
        raise NotFoundError("Conversation not found.", details=None)
    await db.commit()
    return _conversation_to_response(c)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await chat_service.delete_conversation(db, conversation_id, user.id)
    if not deleted:
        raise NotFoundError("Conversation not found.", details=None)
    await db.commit()


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse, status_code=201)
async def send_message(
    conversation_id: int,
    body: SendMessageRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Non-streaming: append user message, call AI, append assistant reply."""
    result = await chat_service.send_message(
        db, conversation_id, user.id, body.message,
        context_material_title=body.contextMaterialTitle,
        course_id=body.courseId,
    )
    if not result:
        raise NotFoundError("Conversation not found.", details=None)
    user_msg, assistant_msg = result
    await db.commit()
    return SendMessageResponse(
        userMessage=_message_to_item(user_msg),
        assistantMessage=_message_to_item(assistant_msg),
    )


# ─── Socratic Challenge Mode ───────────────────────────────────────────────────

@router.post("/socratic", response_model=SocraticChallengeResponse)
async def socratic_challenge(
    body: SocraticChallengeRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """AI challenges the student's claim using the Socratic method to force active recall."""
    return await chat_service.socratic_challenge(body)


# ─── Concept Graph ─────────────────────────────────────────────────────────────

class ConceptGraphRequest(StudyPlanRequest):
    courseTitle: str = ""

    model_config = {"extra": "ignore"}


@router.post("/concept-graph", response_model=ConceptGraphResponse)
async def concept_graph(
    body: ConceptGraphRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """Generate a concept dependency graph with mastery levels for a course."""
    course_title = body.courseTitle or (body.courses[0].title if body.courses else "Engineering Course")
    return await chat_service.generate_concept_graph(course_title, body.recentQuizScores)


# ─── Exam Prediction ───────────────────────────────────────────────────────────

@router.post("/exam-prediction", response_model=ExamPredictionResponse)
async def exam_prediction(
    body: ExamPredictionRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """Predict likely exam topics and student readiness for each."""
    return await chat_service.predict_exam_topics(body)


# ─── Flashcards (Spaced Repetition) ───────────────────────────────────────────

@router.post("/flashcards/generate", response_model=FlashcardDeckResponse)
async def generate_flashcards(
    body: FlashcardDeckRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """Extract Anki-style flashcards from note/transcript text using GPT-4.1."""
    return await chat_service.generate_flashcards(body)


@router.post("/flashcards/review", response_model=FlashcardReviewResponse)
async def review_flashcard(body: FlashcardReviewRequest):
    """Compute SM-2 spaced repetition next interval after a card review."""
    return chat_service.compute_sm2_review(body)
