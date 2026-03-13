"""Ingestion service: trigger AI KB upload/reindex (proxy to AI guy)."""

from typing import Any, Optional

from saarthi_backend.client import AIClient
from saarthi_backend.schema.ingestion_schemas import IngestionResponse

# Map our ingestion type -> AI agent_name
INGESTION_TO_AGENT = {
    "notes": "notes_agent",
    "video": "video_agent",
    "code": "books_agent",  # AI doc has notes_agent, books_agent, video_agent; no code_agent
}


async def ingestion_video(
    client: AIClient,
    source_path: Optional[str] = None,
    video_ids: Optional[list[str]] = None,
) -> IngestionResponse:
    """Trigger video ingestion via AI KB. For now we only support reindex of video_agent."""
    try:
        result = await client.reindex("video_agent")
        return IngestionResponse(
            success=True,
            message="Video ingestion triggered.",
            details=result,
        )
    except Exception as e:
        return IngestionResponse(
            success=False,
            message=str(e),
            details=None,
        )


async def ingestion_notes(
    client: AIClient,
    source_path: Optional[str] = None,
    doc_ids: Optional[list[str]] = None,
) -> IngestionResponse:
    """Trigger notes ingestion via AI KB reindex."""
    try:
        result = await client.reindex("notes_agent")
        return IngestionResponse(
            success=True,
            message="Notes ingestion triggered.",
            details=result,
        )
    except Exception as e:
        return IngestionResponse(
            success=False,
            message=str(e),
            details=None,
        )


async def ingestion_code(
    client: AIClient,
    source_path: Optional[str] = None,
    file_paths: Optional[list[str]] = None,
) -> IngestionResponse:
    """Trigger code/books ingestion via AI KB reindex."""
    try:
        result = await client.reindex("books_agent")
        return IngestionResponse(
            success=True,
            message="Code/books ingestion triggered.",
            details=result,
        )
    except Exception as e:
        return IngestionResponse(
            success=False,
            message=str(e),
            details=None,
        )
