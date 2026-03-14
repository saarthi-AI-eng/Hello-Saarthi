"""Chat routes: POST /message (legacy) + conversation CRUD and send message."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.client import AIClient, map_ai_chat_to_expert_response
from saarthi_backend.dao import ChatMessageDAO, ConversationDAO
from saarthi_backend.deps import get_ai_client, get_current_user, get_db, get_pagination
from saarthi_backend.model import User
from saarthi_backend.schema.ai_client_schemas import AIChatMessage, AIChatRequest
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
from saarthi_backend.schema.pagination_schemas import PaginatedResponse, PaginationParams
from saarthi_backend.utils.constants import EXPERT_THEORY
from saarthi_backend.utils.exceptions import NotFoundError, ValidationError

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
async def chat_message(
    body: ChatMessageRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    """Stateless chat (e.g. AIChatbot). No persistence."""
    history = [AIChatMessage(role=m.role, content=m.content) for m in body.conversationHistory]
    chat_req = AIChatRequest(
        query=body.message,
        mind_mode=False,
        session_id=None,
        conversation_history=history,
    )
    ai_response = await client.chat(chat_req)
    unified = map_ai_chat_to_expert_response(ai_response, EXPERT_THEORY)
    return ChatMessageResponse(
        response=unified.answer or "I couldn't generate a response. Please try again."
    )


# --- Conversations (persisted tutor chat) ---
@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new conversation. Returns id, title, timestamps."""
    c = await ConversationDAO.create(db, user.id, title=body.title)
    await db.commit()
    return _conversation_to_response(c)


@router.get("/conversations", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    """List current user's conversations, most recently updated first."""
    items = await ConversationDAO.list_by_user(db, user.id, limit=pagination.limit, offset=pagination.offset)
    total = await ConversationDAO.count_by_user(db, user.id)
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
    c = await ConversationDAO.get_by_id(db, conversation_id, user.id)
    if not c:
        raise NotFoundError("Conversation not found.", details=None)
    messages = await ChatMessageDAO.list_by_conversation(db, conversation_id)
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
    c = await ConversationDAO.update_title(db, conversation_id, user.id, body.title)
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
    deleted = await ConversationDAO.delete(db, conversation_id, user.id)
    if not deleted:
        raise NotFoundError("Conversation not found.", details=None)
    await db.commit()


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse, status_code=201)
async def send_message(
    conversation_id: int,
    body: SendMessageRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    """Append user message, call AI, append assistant reply. Optionally set title from first message."""
    conv = await ConversationDAO.get_by_id(db, conversation_id, user.id)
    if not conv:
        raise NotFoundError("Conversation not found.", details=None)
    existing = await ChatMessageDAO.list_by_conversation(db, conversation_id)
    # Persist user message
    user_msg = await ChatMessageDAO.create(db, conversation_id, "user", body.message)
    # Build history for AI (existing + new user message)
    history = [AIChatMessage(role=m.role, content=m.content) for m in existing]
    history.append(AIChatMessage(role="user", content=body.message))
    chat_req = AIChatRequest(
        query=body.message,
        mind_mode=False,
        session_id=None,
        conversation_history=history,
    )
    ai_response = await client.chat(chat_req)
    unified = map_ai_chat_to_expert_response(ai_response, EXPERT_THEORY)
    assistant_content = unified.answer or "I couldn't generate a response. Please try again."
    assistant_msg = await ChatMessageDAO.create(db, conversation_id, "assistant", assistant_content)
    # First user message: set conversation title from message (truncate)
    if len(existing) == 0:
        title = (body.message.strip()[:200] + "…") if len(body.message.strip()) > 200 else body.message.strip()
        if not title:
            title = "New Chat"
        await ConversationDAO.update_title(db, conversation_id, user.id, title)
    await ConversationDAO.touch(db, conversation_id)
    await db.commit()
    return SendMessageResponse(
        userMessage=_message_to_item(user_msg),
        assistantMessage=_message_to_item(assistant_msg),
    )
