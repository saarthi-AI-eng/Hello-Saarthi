"""Map AI service chat response to our expert response and retrieval results."""

from saarthi_backend.schema.ai_client_schemas import (
    AIChatResponse,
    AIAgentResponse,
    AIMindResponse,
    AISource,
)
from saarthi_backend.schema.expert_schemas import (
    Citation,
    CodeSnippet,
    UnifiedExpertResponse,
    VideoTimestamp,
)
from saarthi_backend.schema.retrieval_schemas import RetrievalChunk
from saarthi_backend.utils.constants import AGENT_TO_EXPERT

# Map agent_name -> source_type for citations
AGENT_TO_SOURCE_TYPE = {
    "notes_agent": "notes",
    "books_agent": "notes",
    "video_agent": "video",
    "calculator_agent": "code",
    "saarthi_agent": "notes",
}


def _sources_to_citations(agent_name: str, sources: list[AISource] | None) -> list[Citation]:
    """Convert AI sources to our Citation list."""
    if not sources:
        return []
    source_type = AGENT_TO_SOURCE_TYPE.get(agent_name or "", "notes")
    citations = []
    for s in sources:
        citations.append(
            Citation(
                source_type=source_type,
                source_id=s.source_file or "",
                title=s.source_file or "Source",
                excerpt=s.snippet or "",
                timestamp_start=None,
                timestamp_end=None,
                url=None,
            )
        )
    return citations


def _agent_response_to_video_timestamps(ar: AIAgentResponse) -> list[VideoTimestamp]:
    """Best-effort: extract video_timestamps from video_agent response."""
    if (ar.agent_name or "") != "video_agent" or not ar.sources:
        return []
    out = []
    for s in ar.sources:
        out.append(
            VideoTimestamp(
                video_id=s.source_file or "",
                title=s.source_file or "Video",
                start_sec=0.0,
                end_sec=0.0,
                summary=ar.content or s.snippet or "",
            )
        )
    return out


def _agent_response_to_code_snippets(ar: AIAgentResponse) -> list[CodeSnippet]:
    """Best-effort: extract code_snippets from calculator/code agent."""
    if not ar.content:
        return []
    agent = ar.agent_name or ""
    if agent not in ("calculator_agent", "saarthi_agent"):
        return []
        src = ar.sources[0].source_file if ar.sources else "AI agent"
        return [
            CodeSnippet(
                language="python",
                code=ar.content,
                explanation="From course material.",
                source=src,
            )
        ]


def map_ai_chat_to_expert_response(
    ai_response: AIChatResponse,
    expert_used: str,
) -> UnifiedExpertResponse:
    """Map AI chat response to our UnifiedExpertResponse."""
    answer_parts = []
    all_citations: list[Citation] = []
    confidence: float | None = None
    video_timestamps: list[VideoTimestamp] = []
    code_snippets: list[CodeSnippet] = []

    # Prefer mind_response if present
    if ai_response.mind_response:
        mr: AIMindResponse = ai_response.mind_response
        if mr.content:
            answer_parts.append(mr.content)
        if mr.confidence_score is not None:
            confidence = mr.confidence_score
        if mr.references:
            for ref in mr.references:
                all_citations.append(
                    Citation(
                        source_type=AGENT_TO_SOURCE_TYPE.get(ref.source_agent or "", "notes"),
                        source_id=ref.source_file or "",
                        title=ref.source_file or ref.source_agent or "Source",
                        excerpt=ref.snippet or "",
                        timestamp_start=None,
                        timestamp_end=None,
                        url=None,
                    )
                )
    else:
        # Use agent_responses
        for ar in ai_response.agent_responses or []:
            if ar.content:
                answer_parts.append(ar.content)
            if ar.confidence_score is not None and confidence is None:
                confidence = ar.confidence_score
            if ar.sources:
                all_citations.extend(_sources_to_citations(ar.agent_name or "", ar.sources))
            video_timestamps.extend(_agent_response_to_video_timestamps(ar))
            code_snippets.extend(_agent_response_to_code_snippets(ar))

    answer = "\n\n".join(answer_parts) if answer_parts else ""

    out = UnifiedExpertResponse(
        answer=answer,
        citations=all_citations,
        confidence_score=confidence,
        suggested_followups=[],
        expert_used=expert_used,
    )
    if video_timestamps:
        out.video_timestamps = video_timestamps
    if code_snippets:
        out.code_snippets = code_snippets
    return out


def map_ai_chat_to_retrieval_results(
    ai_response: AIChatResponse,
    query: str,
    include_scores: bool = True,
) -> list[RetrievalChunk]:
    """Extract retrieval-style chunks from AI chat response (sources/references)."""
    chunks: list[RetrievalChunk] = []
    content_type = "notes"
    score = 0.9

    if ai_response.mind_response and ai_response.mind_response.references:
        for ref in ai_response.mind_response.references:
            agent = ref.source_agent or ""
            content_type = AGENT_TO_SOURCE_TYPE.get(agent, "notes")
            chunks.append(
                RetrievalChunk(
                    content_type=content_type,
                    source_id=ref.source_file or "",
                    text=ref.snippet or "",
                    score=score if include_scores else None,
                    metadata={"source_agent": ref.source_agent, "source_file": ref.source_file},
                )
            )
    else:
        for ar in ai_response.agent_responses or []:
            agent = ar.agent_name or ""
            content_type = AGENT_TO_SOURCE_TYPE.get(agent, "notes")
            for s in ar.sources or []:
                chunks.append(
                    RetrievalChunk(
                        content_type=content_type,
                        source_id=s.source_file or "",
                        text=s.snippet or ar.content or "",
                        score=(ar.confidence_score if include_scores else None),
                        metadata={"agent_name": agent, "source_file": s.source_file},
                    )
                )
            if not (ar.sources) and ar.content:
                chunks.append(
                    RetrievalChunk(
                        content_type=content_type,
                        source_id=agent,
                        text=ar.content,
                        score=(ar.confidence_score if include_scores else None),
                        metadata={"agent_name": agent},
                    )
                )
    return chunks
