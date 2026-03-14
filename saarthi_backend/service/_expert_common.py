"""Shared logic for expert services: build AI chat request, call client, map response."""

from saarthi_backend.client import AIClient, map_ai_chat_to_expert_response
from saarthi_backend.schema.ai_client_schemas import AIChatMessage, AIChatRequest
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse


def build_chat_request(req: UnifiedExpertRequest) -> AIChatRequest:
    """Build AIChatRequest from UnifiedExpertRequest."""
    history = None
    if req.conversation_history:
        history = [
            AIChatMessage(role=m.role, content=m.content)
            for m in req.conversation_history
        ]
    return AIChatRequest(
        query=req.query,
        mind_mode=False,
        session_id=req.conversation_id,
        conversation_history=history,
    )


async def call_ai_and_map(
    client: AIClient,
    req: UnifiedExpertRequest,
    expert_used: str,
) -> UnifiedExpertResponse:
    """Call AI chat and map response to UnifiedExpertResponse."""
    chat_req = build_chat_request(req)
    ai_response = await client.chat(chat_req)
    return map_ai_chat_to_expert_response(ai_response, expert_used)
