"""Chat routes: stateless message, conversation CRUD, send message, SSE stream, study plan."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.chat_schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatMessageResponseItem,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    SendMessageRequest,
    SendMessageResponse,
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
        body.message, history, context_material_title=body.contextMaterialTitle
    )
    return ChatMessageResponse(response=answer)


# ─── SSE Streaming endpoint ───────────────────────────────────────────────────

@router.post("/stream")
async def stream_message(
    body: StreamMessageRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Stream an AI response token-by-token via Server-Sent Events.
    Also persists the full exchange to the conversation when complete.
    """
    history = [{"role": m.role, "content": m.content} for m in body.conversationHistory]

    from saarthi_backend.ai.adapter import run_chat_stream
    from saarthi_backend.service.chat_service import _apply_document_context
    from saarthi_backend.dao import ChatMessageDAO, ConversationDAO

    prompt = _apply_document_context(body.message, body.contextMaterialTitle)

    async def event_generator():
        full_response = []
        async for chunk in run_chat_stream(prompt, history):
            yield chunk
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                token = chunk[6:].rstrip("\n").replace("\\n", "\n")
                full_response.append(token)

        # Persist to DB after streaming completes
        try:
            if body.conversationId:
                conv_id = int(body.conversationId)
                conv = await ConversationDAO.get_by_id(db, conv_id, user.id)
                if conv:
                    await ChatMessageDAO.create(db, conv_id, "user", body.message)
                    assistant_content = "".join(full_response)
                    await ChatMessageDAO.create(db, conv_id, "assistant", assistant_content)
                    await ConversationDAO.touch(db, conv_id)
                    await db.commit()
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
        db, conversation_id, user.id, body.message, context_material_title=body.contextMaterialTitle
    )
    if not result:
        raise NotFoundError("Conversation not found.", details=None)
    user_msg, assistant_msg = result
    await db.commit()
    return SendMessageResponse(
        userMessage=_message_to_item(user_msg),
        assistantMessage=_message_to_item(assistant_msg),
    )
