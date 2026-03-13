"""Saarthi API router: experts, retrieval, context, ingestion."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_ai_client, get_db
from saarthi_backend.schema import (
    ContextGetResponse,
    ContextUpsertRequest,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    UnifiedExpertRequest,
    UnifiedExpertResponse,
)
from saarthi_backend.schema.ingestion_schemas import (
    IngestionCodeRequest,
    IngestionNotesRequest,
    IngestionResponse,
    IngestionVideoRequest,
)
from saarthi_backend.service import (
    code_expert,
    context_service,
    exam_prep_expert,
    followup_expert,
    ingestion_service,
    multimodal_expert,
    problem_solving_expert,
    retrieval_service,
    theory_expert,
    video_expert,
)
from saarthi_backend.utils.exceptions import NotFoundError
from saarthi_backend.client import AIClient

router = APIRouter()


# --- Expert endpoints ---
@router.post("/experts/theory", response_model=UnifiedExpertResponse)
async def expert_theory(
    body: UnifiedExpertRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await theory_expert(client, body)


@router.post("/experts/problem-solving", response_model=UnifiedExpertResponse)
async def expert_problem_solving(
    body: UnifiedExpertRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await problem_solving_expert(client, body)


@router.post("/experts/video", response_model=UnifiedExpertResponse)
async def expert_video(
    body: UnifiedExpertRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await video_expert(client, body)


@router.post("/experts/code", response_model=UnifiedExpertResponse)
async def expert_code(
    body: UnifiedExpertRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await code_expert(client, body)


@router.post("/experts/multimodal", response_model=UnifiedExpertResponse)
async def expert_multimodal(
    body: UnifiedExpertRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await multimodal_expert(client, body)


@router.post("/experts/exam-prep", response_model=UnifiedExpertResponse)
async def expert_exam_prep(
    body: UnifiedExpertRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await exam_prep_expert(client, body)


@router.post("/experts/followup", response_model=UnifiedExpertResponse)
async def expert_followup(
    body: UnifiedExpertRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await followup_expert(client, body)


# --- Retrieval ---
@router.post("/retrieval/search", response_model=RetrievalSearchResponse)
async def retrieval_search_endpoint(
    body: RetrievalSearchRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    chunks, query = await retrieval_service.retrieval_search(client, body)
    return RetrievalSearchResponse(results=chunks, query=query, total_returned=len(chunks))


# --- Context ---
@router.get("/context/{conversation_id}", response_model=ContextGetResponse)
async def context_get(
    conversation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await context_service.get_context(db, conversation_id)
    if ctx is None:
        raise NotFoundError("Context not found for this conversation.")
    return ctx


@router.post("/context", response_model=ContextGetResponse, status_code=status.HTTP_201_CREATED)
async def context_upsert(
    body: ContextUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await context_service.upsert_context(db, body)


# --- Ingestion (optional) ---
@router.post("/ingestion/video", response_model=IngestionResponse)
async def ingestion_video_endpoint(
    body: IngestionVideoRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await ingestion_service.ingestion_video(
        client,
        source_path=body.source_path,
        video_ids=body.video_ids,
    )


@router.post("/ingestion/notes", response_model=IngestionResponse)
async def ingestion_notes_endpoint(
    body: IngestionNotesRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await ingestion_service.ingestion_notes(
        client,
        source_path=body.source_path,
        doc_ids=body.doc_ids,
    )


@router.post("/ingestion/code", response_model=IngestionResponse)
async def ingestion_code_endpoint(
    body: IngestionCodeRequest,
    client: Annotated[AIClient, Depends(get_ai_client)],
):
    return await ingestion_service.ingestion_code(
        client,
        source_path=body.source_path,
        file_paths=body.file_paths,
    )
