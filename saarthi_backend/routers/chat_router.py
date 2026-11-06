"""Chat routes: stateless message, conversation CRUD, SSE stream, study plan,
socratic, concept graph, exam prediction, flashcards."""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.chat_schemas import (
    AnswerFeedbackRequest,
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
    FlashcardListResponse,
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

# Exact sentinel frames emitted by adapter.run_chat_stream — used to tell a
# real streamed token apart from a control frame. Previously this was done
# with `chunk.startswith("data: [")`, which silently dropped any legitimate
# answer whose *first token* happened to render as e.g. "[1]" (a citation
# marker the tutor is explicitly instructed to use).
_SSE_DONE = "data: [DONE]\n\n"
_SSE_ERROR_PREFIX = "data: [ERROR]"


def _is_content_frame(chunk: str) -> bool:
    """True if this SSE frame carries an actual answer token."""
    if not chunk.startswith("data: "):
        return False
    if chunk == _SSE_DONE:
        return False
    if chunk.startswith(_SSE_ERROR_PREFIX):
        return False
    return True


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
def _retrieval_query(question: str, history: list[dict], policy) -> str:
    """What to search for this turn. Socratic continuations search for the thread's problem;
    other follow-ups prepend the previous student question; everything else uses the question."""
    if policy.socratic.stage in ("hint", "reveal") and policy.socratic.thread_query:
        if policy.socratic.thread_query.strip() != question.strip():
            return f"{policy.socratic.thread_query} {question}"
        return question
    if policy.qclass.kind == "followup":
        prev = next((m.get("content", "") for m in reversed(history) if m.get("role") == "user"), "")
        return f"{prev} {question}".strip()
    return question


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

    Per turn: scrub PII → query classifier (Tier 0 = stored repeated query served from the
    semantic cache with no LLM call; else Tier 1 / Tier 2) → Socratic stage → answer ONLY
    from the course materials (grounding rule) with inline citations → trace.
    """
    import time as _time

    raw_history = [{"role": m.role, "content": m.content} for m in body.conversationHistory]

    from saarthi_backend.ai.adapter import _sse_data, run_chat_stream, stream_scoped_answer
    from saarthi_backend.service.memory_service import build_context, maybe_update_summary_bg
    from saarthi_backend.service.weak_topics_service import flag_weak_topic, get_weak_topics
    from saarthi_backend.dao import ChatMessageDAO, ConversationDAO
    from saarthi_backend.service import course_service
    from src.cache.semantic_cache import get_cache
    from src.orchestrator.policy import plan_turn
    from src.orchestrator.topics import topic_of
    from src.safety.guard import check_injection, scrub_pii
    from src.telemetry.traces import hash_user, summarize_usage, write_trace
    from src.tools.grounding import ground
    from src.utils import budget
    from src.utils.llm import chat_model_name, reset_tier, set_tier

    # No student PII reaches the LLM, the cache or the trace (spec 2.3, R7).
    question, pii_scrubbed = scrub_pii(body.message, [user.full_name] if user.full_name else [])
    injection = check_injection(question)
    user_key = hash_user(user.id)

    # Build memory-trimmed context (Tier 1 + Tier 2 summary injection)
    conv_id_int = int(body.conversationId) if body.conversationId else None
    if conv_id_int:
        history = await build_context(db, conv_id_int, raw_history)
    else:
        history = raw_history[-10:]

    course_name = None
    if body.courseId:
        course = await course_service.get_course(db, body.courseId)
        course_name = course.title if course else None
    scoped = bool(body.courseId or body.contextMaterialTitle or body.contextVideoId)

    policy = await run_in_threadpool(
        lambda: plan_turn(
            question,
            raw_history,
            course_id=body.courseId,
            material_title=body.contextMaterialTitle,
            video_id=body.contextVideoId,
            mode="planning" if body.planning else "chat",
            answer_mode=body.answerMode,
            user_key=user_key,
            role=user.role,
        )
    )
    weak_topics = await get_weak_topics(db, user.id, body.courseId)
    flagged_topic = None
    if policy.socratic.escalated:
        # Spec 4.4: after 3 unsuccessful attempts the topic is flagged as a weakness.
        flagged_topic = topic_of(policy.socratic.thread_query or question)
        if await flag_weak_topic(db, user.id, flagged_topic):
            await db.commit()
    system_extra = policy.socratic.system_instructions()
    meta_extra = {
        "tier": policy.tier,
        "socratic": policy.socratic.stage,
        "cached": False,
        "classifier": policy.decision.source,
    }
    if policy.cap.get("over") or policy.cap.get("near"):
        meta_extra["cap"] = policy.cap

    async def event_generator():
        import asyncio
        import json as _json
        full_response = []
        sink: dict = {}
        cache_hit = policy.cache_hit
        stream = None
        started = _time.perf_counter()
        usage_token = budget.request_usage.set([])
        tier_token = set_tier(policy.tier or 1)
        from saarthi_backend.ai.adapter import _sse_status

        try:
            if await request.is_disconnected():
                return

            if cache_hit is not None:
                # Tier 0: the classifier matched a stored repeated query — no LLM call.
                yield _sse_status("cache", "Answered from a previous identical question")
                meta = {**meta_extra, "cached": True, "tier": 0, "citations": cache_hit.citations,
                        "cache_entry_id": cache_hit.entry_id, "confidence": "ok", "reply_mode": "grounded"}
                yield f"event: meta\ndata: {_json.dumps(meta)}\n\n"
                answer = cache_hit.answer
                for i in range(0, len(answer), 160):
                    yield _sse_data(answer[i:i + 160])
                full_response.append(answer)
                sink.update({"citations": cache_hit.citations, "chunk_ids": cache_hit.chunk_ids,
                             "reply_mode": "grounded", "confidence": "ok", "covered": True})
                yield "data: [DONE]\n\n"
            elif scoped:
                yield _sse_status("retrieving", "Searching your course materials")
                # Follow-ups ("I'm stuck", "explain more") carry no course terms of their own:
                # retrieve for the problem / previous question they refer to.
                retrieval_query = _retrieval_query(question, raw_history, policy)
                grounding = await run_in_threadpool(
                    lambda: ground(
                        retrieval_query,
                        course_id=body.courseId,
                        material_title=body.contextMaterialTitle,
                        video_id=body.contextVideoId,
                        n=policy.top_n,
                        boost_terms=weak_topics,
                    )
                )
                stream = stream_scoped_answer(
                    question, grounding, history, kind=policy.qclass.kind, tier=policy.tier,
                    system_extra=system_extra, course_name=course_name, meta_extra=meta_extra, sink=sink,
                )
            else:
                stream = run_chat_stream(
                    question, history, planning=body.planning, tier=policy.tier, system_extra=system_extra,
                    boost_terms=weak_topics, meta_extra=meta_extra, sink=sink,
                    kind=policy.qclass.kind, n=policy.top_n, course_name=course_name,
                )
            if stream is not None:
                async for chunk in stream:
                    if await request.is_disconnected():
                        return
                    yield chunk
                    if _is_content_frame(chunk):
                        full_response.append(chunk[6:].rstrip("\n").replace("\\n", "\n"))
        except asyncio.CancelledError:
            return
        finally:
            usage = budget.request_usage.get() or []
            for var_reset in (lambda: reset_tier(tier_token), lambda: budget.request_usage.reset(usage_token)):
                try:
                    var_reset()
                except ValueError:  # generator closed from another context (client disconnect)
                    pass

            assistant_content = "".join(full_response)
            tokens = summarize_usage(usage)
            budget.record_user(user_key, tokens["prompt"] + tokens["completion"])
            try:
                # Tier 0 write-back: only verified, cited, grounded answers are reused.
                if (cache_hit is None and policy.cache_scope and assistant_content
                        and sink.get("reply_mode") == "grounded" and sink.get("confidence") == "ok"
                        and not injection):
                    await run_in_threadpool(
                        lambda: get_cache().store(
                            question,
                            policy.cache_scope,
                            assistant_content,
                            citations=sink.get("citations") or [],
                            chunk_ids=[c for c in (sink.get("chunk_ids") or []) if c],
                            answer_model=chat_model_name(tier=policy.tier),
                            tier=policy.tier,
                            embedding=policy.embedding,
                        )
                    )
                write_trace({
                    "path": "stream",
                    "user": user_key,
                    "role": user.role,
                    "conversation": conv_id_int,
                    "scope": {"course_id": body.courseId, "material": body.contextMaterialTitle, "video_id": body.contextVideoId},
                    "query": question,
                    **policy.trace(),
                    "tier": 0 if cache_hit else policy.tier,
                    "model": None if cache_hit else chat_model_name(tier=policy.tier),
                    "cache": {"hit": cache_hit is not None, "similarity": getattr(cache_hit, "similarity", None),
                              "entry_id": getattr(cache_hit, "entry_id", None)},
                    "reply_mode": sink.get("reply_mode"),
                    "covered": sink.get("covered"),
                    "cited": sink.get("cited"),
                    "confidence": sink.get("confidence"),
                    "confidence_reasons": sink.get("confidence_reasons"),
                    "expert": sink.get("expert"),
                    "plan": sink.get("plan"),
                    "critic_ok": sink.get("critic_ok"),
                    "weak_topics": weak_topics,
                    "flagged_weak_topic": flagged_topic,
                    "safety": {"pii_scrubbed": pii_scrubbed, "injection_suspected": injection, "leak": sink.get("leaked")},
                    "retrieval": sink.get("retrieval"),
                    "cite_ids": [c for c in (sink.get("chunk_ids") or []) if c],
                    "n_citations": len(sink.get("citations") or []),
                    "tokens": tokens,
                    "latency_ms": round((_time.perf_counter() - started) * 1000),
                    "answer_chars": len(assistant_content),
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug("cache/trace write skipped: %s", e)

        # Persist to DB after streaming completes, then trigger lazy summarization
        try:
            if conv_id_int:
                conv = await ConversationDAO.get_by_id(db, conv_id_int, user.id)
                if conv:
                    await ChatMessageDAO.create(db, conv_id_int, "user", body.message)
                    await ChatMessageDAO.create(db, conv_id_int, "assistant", assistant_content)
                    await ConversationDAO.touch(db, conv_id_int)
                    await db.commit()

                    # Lazy memory update — runs after response is fully sent, never blocks user.
                    # Uses a fresh DB session (not the request-scoped one) to avoid asyncpg conflict.
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
    items, total = await chat_service.list_conversations(db, user.id, limit=pagination.limit, offset=pagination.offset)
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
@router.get("/flashcards", response_model=FlashcardListResponse)
async def list_flashcards(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    topic: str | None = None,
):
    """Saved library for this user. New generates APPEND; they never wipe older topics."""
    return await chat_service.list_flashcards(db, user.id, topic=topic)


@router.post("/flashcards/generate", response_model=FlashcardDeckResponse)
async def generate_flashcards(
    body: FlashcardDeckRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Extract Anki-style flashcards and append them to the user's library."""
    return await chat_service.generate_flashcards(body, db=db, user_id=user.id)


@router.post("/flashcards/review", response_model=FlashcardReviewResponse)
async def review_flashcard(
    body: FlashcardReviewRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """SM-2 next interval, written back onto the saved card."""
    return await chat_service.review_flashcard(body, db=db, user_id=user.id)


# ─── Answer feedback (thumbs up / down) ──────────────────────────────────────
@router.post("/feedback")
async def answer_feedback(
    body: AnswerFeedbackRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """Record a rating for the researcher dashboard (traces) and, on thumbs-down,
    evict the answer from the semantic cache so it is never served again (WBS 3.4.4)."""
    from saarthi_backend.schema.chat_schemas import AnswerFeedbackResponse
    from src.cache.semantic_cache import build_scope, get_cache
    from src.safety.guard import scrub_pii
    from src.telemetry.traces import hash_user, write_trace

    query, _ = scrub_pii(body.query, [user.full_name] if user.full_name else [])
    comment = scrub_pii(body.comment, [user.full_name] if user.full_name else [])[0] if body.comment else None
    evicted = 0
    if body.rating == "down":
        scope = build_scope(course_id=body.courseId, material_title=body.contextMaterialTitle,
                            video_id=body.contextVideoId, mode="chat")
        evicted = await run_in_threadpool(lambda: get_cache().forget(scope, query, body.cacheEntryId))
    write_trace({
        "type": "feedback",
        "user": hash_user(user.id),
        "role": user.role,
        "rating": body.rating,
        "comment": comment,
        "query": query,
        "scope": {"course_id": body.courseId, "material": body.contextMaterialTitle, "video_id": body.contextVideoId},
        "conversation": body.conversationId,
        "cache_evicted": evicted,
    })
    return AnswerFeedbackResponse(recorded=True, cacheEvicted=evicted)
