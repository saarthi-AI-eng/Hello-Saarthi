"""Multimodal expert: diagram/image explanation."""

from saarthi_backend.client import AIClient
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse
from saarthi_backend.utils.constants import EXPERT_MULTIMODAL

from ._expert_common import call_ai_and_map


async def multimodal_expert(client: AIClient, req: UnifiedExpertRequest) -> UnifiedExpertResponse:
    """Multimodal expert: call AI chat (image in options could be sent when AI supports it)."""
    return await call_ai_and_map(client, req, EXPERT_MULTIMODAL)
