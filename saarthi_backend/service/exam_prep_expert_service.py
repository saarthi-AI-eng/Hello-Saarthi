"""Exam-prep expert: quiz questions and explanations."""

from saarthi_backend.client import AIClient
from saarthi_backend.schema.expert_schemas import UnifiedExpertRequest, UnifiedExpertResponse
from saarthi_backend.utils.constants import EXPERT_EXAM_PREP

from ._expert_common import call_ai_and_map


async def exam_prep_expert(client: AIClient, req: UnifiedExpertRequest) -> UnifiedExpertResponse:
    """Exam-prep expert: call AI chat, return unified response."""
    return await call_ai_and_map(client, req, EXPERT_EXAM_PREP)
