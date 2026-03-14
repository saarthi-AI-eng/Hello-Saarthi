"""Follow-up expert: context-aware follow-up answers."""

from saarthi_backend.client import AIClient
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse
from saarthi_backend.utils.constants import EXPERT_FOLLOWUP

from ._expert_common import call_ai_and_map


async def followup_expert(client: AIClient, req: UnifiedExpertRequest) -> UnifiedExpertResponse:
    """Follow-up expert: uses conversation_history; call AI chat."""
    return await call_ai_and_map(client, req, EXPERT_FOLLOWUP)
