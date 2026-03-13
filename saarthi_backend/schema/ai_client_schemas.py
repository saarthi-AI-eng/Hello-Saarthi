"""Internal DTOs for AI service (backend_api_docs.md) request/response."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --- Chat request (POST /v1/chat) ---
class AIChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AIChatRequest(BaseModel):
    """Body we send to AI service POST /v1/chat."""

    query: str
    mind_mode: bool = False
    session_id: Optional[str] = None
    conversation_history: Optional[list[AIChatMessage]] = None


# --- Chat response ---
class AISource(BaseModel):
    """One source in agent_responses."""

    source_file: Optional[str] = None
    page_number: Optional[int] = None
    snippet: Optional[str] = None


class AIAgentResponse(BaseModel):
    """One entry in agent_responses."""

    agent_name: Optional[str] = None
    content: Optional[str] = None
    sources: Optional[list[AISource]] = None
    confidence_score: Optional[float] = None
    is_knowledge_present: Optional[bool] = None


class AIReference(BaseModel):
    """One reference in mind_response.references."""

    number: Optional[int] = None
    source_agent: Optional[str] = None
    source_file: Optional[str] = None
    snippet: Optional[str] = None


class AIMindResponse(BaseModel):
    """mind_response when mind_mode=true."""

    content: Optional[str] = None
    references: Optional[list[AIReference]] = None
    confidence_score: Optional[float] = None


class AIChatResponse(BaseModel):
    """Response from AI service POST /v1/chat."""

    session_id: Optional[str] = None
    response_type: Optional[str] = None
    agent_responses: Optional[list[AIAgentResponse]] = None
    mind_response: Optional[AIMindResponse] = None

    model_config = {"extra": "allow"}


# --- AI error (backend_api_docs §4) ---
class AIErrorResponse(BaseModel):
    """AI service error body."""

    error: bool = True
    code: str = ""
    message: str = ""


# --- KB status ---
class AIAgentKbStatus(BaseModel):
    indexed: Optional[bool] = None
    file_count: Optional[int] = None
    chunk_count: Optional[int] = None
    last_updated: Optional[str] = None


class AIKbStatusResponse(BaseModel):
    agents: Optional[dict[str, AIAgentKbStatus]] = None


# --- Session history ---
class AISessionMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None


class AISessionHistoryResponse(BaseModel):
    session_id: Optional[str] = None
    messages: Optional[list[AISessionMessage]] = None
