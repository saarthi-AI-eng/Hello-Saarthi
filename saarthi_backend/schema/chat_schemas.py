"""Chat message request/response (frontend Chat / AIChatbot)."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatMessageRequest(BaseModel):
    """POST /api/chat/message."""

    message: str = Field(..., min_length=1)
    conversationHistory: list[ChatMessageItem] = Field(default_factory=list)


class ChatMessageResponse(BaseModel):
    """Response: frontend expects .response."""

    response: str


# --- Tutor chat conversations (persisted) ---


class ConversationResponse(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str


class ChatMessageResponseItem(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: str


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messages: list[ChatMessageResponseItem] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=255)


class UpdateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class SendMessageResponse(BaseModel):
    userMessage: ChatMessageResponseItem
    assistantMessage: ChatMessageResponseItem
