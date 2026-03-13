"""Problem-solving expert: solved exercises, step-by-step."""

from saarthi_backend.client import AIClient
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse
from saarthi_backend.utils.constants import EXPERT_PROBLEM_SOLVING

from ._expert_common import call_ai_and_map


async def problem_solving_expert(
    client: AIClient,
    req: UnifiedExpertRequest,
) -> UnifiedExpertResponse:
    """Problem-solving expert: call AI chat, return unified response."""
    return await call_ai_and_map(client, req, EXPERT_PROBLEM_SOLVING)
