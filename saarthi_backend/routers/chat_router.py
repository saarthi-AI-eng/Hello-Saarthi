"""Chat routes: POST /message (legacy) + conversation CRUD and send message."""

from typing import Annotated

from fastapi import APIRouter, Depends
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


# --- Legacy: stateless message (no conversation id) ---
@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(body: ChatMessageRequest):
    """Stateless chat (e.g. AIChatbot, material viewer). No persistence. Uses in-process src/ AI graph."""
    history = [{"role": m.role, "content": m.content} for m in body.conversationHistory]
    answer = await chat_service.stateless_message(
        body.message, history, context_material_title=body.contextMaterialTitle
    )
    return ChatMessageResponse(response=answer)


# --- Conversations (persisted tutor chat) ---
@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new conversation. Returns id, title, timestamps."""
    c = await chat_service.create_conversation(db, user.id, title=body.title)
    await db.commit()
    return _conversation_to_response(c)


@router.get("/conversations", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List current user's conversations, most recently updated first."""
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
    """Get one conversation with all messages (owner only)."""
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
    """Update conversation title (owner only)."""
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
    """Delete conversation and all messages (owner only)."""
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
    """Append user message, call AI (src/ graph), append assistant reply. Optionally set title from first message."""
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
