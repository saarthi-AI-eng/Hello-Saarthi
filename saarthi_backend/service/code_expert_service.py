"""Code expert: code snippets, optional execution."""

from saarthi_backend.client import AIClient
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse
from saarthi_backend.utils.constants import EXPERT_CODE

from ._expert_common import call_ai_and_map


async def code_expert(client: AIClient, req: UnifiedExpertRequest) -> UnifiedExpertResponse:
    """Code expert: call AI chat, return unified response with code_snippets."""
    return await call_ai_and_map(client, req, EXPERT_CODE)
