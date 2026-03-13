"""Retrieval search: call AI chat, return chunks as retrieval results."""

from saarthi_backend.client import AIClient, map_ai_chat_to_retrieval_results
from saarthi_backend.schema.ai_client_schemas import AIChatRequest
from saarthi_backend.schema.retrieval_schemas import RetrievalChunk, RetrievalSearchRequest


async def retrieval_search(
    client: AIClient,
    req: RetrievalSearchRequest,
) -> tuple[list[RetrievalChunk], str]:
    """Call AI chat with query, extract sources as retrieval chunks. Returns (results, query)."""
    chat_req = AIChatRequest(
        query=req.query,
        mind_mode=False,
        session_id=None,
        conversation_history=None,
    )
    ai_response = await client.chat(chat_req)
    chunks = map_ai_chat_to_retrieval_results(
        ai_response,
        req.query,
        include_scores=req.include_scores,
    )
    # Optional: filter by content_types if we have that info in chunks
    if req.content_types:
        allowed = set(req.content_types)
        chunks = [c for c in chunks if c.content_type in allowed]
    chunks = chunks[: req.top_k]
    return chunks, req.query
