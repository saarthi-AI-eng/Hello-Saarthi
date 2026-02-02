# Data Models and Schemas

This document describes **entities, request/response schema naming, and field descriptions** for the Saarthi.ai backend. It is documentation only; implementation will use Pydantic (schemas) and SQLAlchemy (models) following these names and conventions.

---

## 1. Schema Naming Conventions

All Pydantic schemas follow a consistent pattern:

| Purpose | Naming | Example |
|--------|--------|---------|
| Create (request body) | `{Entity}CreateRequest` | `ExpertInvocationCreateRequest` |
| Update / Patch | `{Entity}UpdateRequest` or `{Entity}PatchRequest` | `ContextUpdateRequest` |
| Single response | `{Entity}Response` | `ExpertResponse` |
| List response | `{Entity}ListResponse` | `RetrievalResultListResponse` |
| Detail (richer single) | `{Entity}DetailResponse` | Optional, when needed. |
| Query params (list/filter) | `{Entity}ListQuery` | `RetrievalSearchQuery` |

- Request schemas **must** end with `Request` (or `Query` for query params).
- Response schemas **must** end with `Response` (or `ListResponse` / `DetailResponse`).

---

## 2. Orchestrator Request / Response Entities

### 2.1 Expert Invocation Request (what orchestrator sends)

**Logical name**: Expert invocation request.

**Suggested schema name**: `ExpertInvocationRequest` (or `UnifiedExpertRequest`).

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | User question or request text. |
| intent | string (enum) | Yes | THEORY, PROBLEM_SOLVING, VIDEO_REFERENCE, CODE_REQUEST, DIAGRAM_EXPLAIN, EXAM_PREP, FOLLOWUP. |
| conversation_id | UUID string | No | Conversation identifier. |
| conversation_history | array of Message | No | Last N messages. |
| options | object | No | Expert-specific options. |

**Message**:

| Field | Type | Description |
|-------|------|-------------|
| role | string | "user" or "assistant". |
| content | string | Message content. |

---

### 2.2 Expert Response (what backend returns to orchestrator)

**Logical name**: Expert response.

**Suggested schema name**: `ExpertResponse`.

**Fields**: See [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md) (answer, citations, confidence_score, suggested_followups, expert_used, plus expert-specific extensions).

**Citation** (nested): `CitationResponse` — source_type, source_id, title, excerpt, timestamp_start, timestamp_end, url.

---

### 2.3 Retrieval Search Request

**Suggested schema name**: `RetrievalSearchRequest`.

**Fields**: query (string), content_types (array of strings, optional), top_k (integer, optional), include_scores (boolean, optional).

---

### 2.4 Retrieval Search Response

**Suggested schema name**: `RetrievalSearchResponse`.

**Fields**: results (array of ChunkResult), query (string), total_returned (integer).

**ChunkResult**: content_type, source_id, text, score, metadata.

---

## 3. Persistence Entities (Database / ORM)

These are **logical entities** that may be stored in the database. Table names should be prefixed (e.g. `saarthi_*`).

### 3.1 Video Metadata

**Purpose**: Store metadata for indexed videos (id, title, duration, upload_date, transcript_path, etc.).

**Suggested table name**: `saarthi_video_metadata`.

**Key fields**: id (UUID), external_id (e.g. YouTube id), title, description, duration_sec, upload_date, transcript_path, created_at, updated_at.

---

### 3.2 Note Chunk

**Purpose**: Store chunked note content after OCR/LaTeX and chunking.

**Suggested table name**: `saarthi_note_chunks`.

**Key fields**: id (UUID), source_doc_id, subject (e.g. SS, DSP), page_number, chunk_index, text, metadata (JSON), created_at.

---

### 3.3 Video Transcript Chunk

**Purpose**: Store chunked video transcript with timestamps.

**Suggested table name**: `saarthi_video_transcript_chunks`.

**Key fields**: id (UUID), video_id (FK or reference), start_sec, end_sec, text, created_at.

---

### 3.4 Code Chunk

**Purpose**: Store indexed code (function-level or file-level chunks).

**Suggested table name**: `saarthi_code_chunks`.

**Key fields**: id (UUID), source_file_path, function_name, language, text, topic_tags (array or JSON), created_at.

---

### 3.5 Solved Exercise

**Purpose**: Store solved exercise problems and solutions (for problem-solving expert).

**Suggested table name**: `saarthi_solved_exercises`.

**Key fields**: id (UUID), subject, topic, problem_text, solution_text, steps (JSON), created_at.

---

### 3.6 Conversation Context (Optional)

**Purpose**: Store conversation summary or metadata for follow-up and memory.

**Suggested table name**: `saarthi_conversation_context`.

**Key fields**: id (UUID), conversation_id (unique), summary (text), metadata (JSON), updated_at.

---

## 4. Vector Store (Non-SQL)

Chunks are **embedded and stored in a vector DB** (ChromaDB / Qdrant). The backend does not define SQL tables for vector store; it defines:

- **Collection / namespace** per content type (e.g. notes, video, code, exercises) or a single collection with a `content_type` field.
- **Document shape** for indexing: id, text, metadata (source_id, title, start_sec, end_sec, etc.).
- **Query**: same embedding model; return top-k with metadata.

Exact schema of the vector store is implementation-defined; this doc only states that chunks are stored with id, text, and metadata consistent with the citation and retrieval response shapes.

---

## 5. Enums

**Intent** (orchestrator → backend): THEORY, PROBLEM_SOLVING, VIDEO_REFERENCE, CODE_REQUEST, DIAGRAM_EXPLAIN, EXAM_PREP, FOLLOWUP.

**Source type** (citations): notes, video, code, exercise.

**Content type** (retrieval filter): notes, video, code, exercises.

---

## 6. Summary

| Area | Schemas / Models | Notes |
|------|------------------|-------|
| Orchestrator request | ExpertInvocationRequest, RetrievalSearchRequest | Pydantic; validate at router. |
| Orchestrator response | ExpertResponse, CitationResponse, RetrievalSearchResponse, ChunkResult | Pydantic; used in response_model. |
| Persistence | Video metadata, Note chunk, Video transcript chunk, Code chunk, Solved exercise, Conversation context | SQLAlchemy models; tables prefixed. |
| Vector store | Document with id, text, metadata | Implementation-defined; no SQL schema here. |

All schema and model **files** should live under `backend/schema/` and `backend/model/` as per [02-directory-structure.md](02-directory-structure.md).
