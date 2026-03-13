"""Theory expert: conceptual/theoretical questions."""

from saarthi_backend.client import AIClient
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse
from saarthi_backend.utils.constants import EXPERT_THEORY

from ._expert_common import call_ai_and_map


async def theory_expert(client: AIClient, req: UnifiedExpertRequest) -> UnifiedExpertResponse:
    """Theory expert: call AI chat, return unified response."""
    return await call_ai_and_map(client, req, EXPERT_THEORY)
