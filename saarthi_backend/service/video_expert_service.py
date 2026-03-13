"""Video expert: which video, timestamps, summaries."""

from saarthi_backend.client import AIClient
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse
from saarthi_backend.utils.constants import EXPERT_VIDEO

from ._expert_common import call_ai_and_map


async def video_expert(client: AIClient, req: UnifiedExpertRequest) -> UnifiedExpertResponse:
    """Video expert: call AI chat, return unified response with video_timestamps."""
    return await call_ai_and_map(client, req, EXPERT_VIDEO)
