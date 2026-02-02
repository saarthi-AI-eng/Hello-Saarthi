# API Endpoints Index

This document lists **all API endpoints** the backend will expose for the orchestrator (and optionally the frontend). Base prefix: `/api/v1/saarthi/`.

---

## 1. Expert Endpoints (POST)

All expert endpoints accept the **unified expert request** body (query, intent, conversation_id?, conversation_history?, options?) and return the **unified expert response** (answer, citations, confidence_score, suggested_followups, expert_used, plus expert-specific extensions). See [03-orchestrator-to-backend-contract.md](03-orchestrator-to-backend-contract.md) and [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/saarthi/experts/theory` | Theory expert: conceptual/theoretical questions. |
| POST | `/api/v1/saarthi/experts/problem-solving` | Problem-solving expert: solved exercises, step-by-step. |
| POST | `/api/v1/saarthi/experts/video` | Video expert: which video, timestamps, summaries. |
| POST | `/api/v1/saarthi/experts/code` | Code expert: code snippets, optional execution. |
| POST | `/api/v1/saarthi/experts/multimodal` | Multimodal expert: diagram/image explanation. |
| POST | `/api/v1/saarthi/experts/exam-prep` | Exam-prep expert: quiz questions and explanations. |
| POST | `/api/v1/saarthi/experts/followup` | Follow-up expert: context-aware follow-up answers. |

---

## 2. Retrieval Endpoint (POST)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/saarthi/retrieval/search` | Raw retrieval: query, optional content_types, top_k, include_scores. Returns ranked chunks. |

**Body**: See [03-orchestrator-to-backend-contract.md](03-orchestrator-to-backend-contract.md).  
**Response**: See [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md) (Retrieval-Only Response).

---

## 3. Context / Memory Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/saarthi/context/{conversation_id}` | Get stored context for a conversation. |
| POST | `/api/v1/saarthi/context` | Upsert context (conversation_id, summary?, metadata?). |

**Response (GET)**: conversation_id, summary?, metadata?, updated_at?.  
See [11-state-and-context.md](11-state-and-context.md).

---

## 4. Ingestion Endpoints (Optional)

If ingestion is triggered via API (optional):

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/saarthi/ingestion/video` | Trigger video ingestion (body: source path or list of video ids). |
| POST | `/api/v1/saarthi/ingestion/notes` | Trigger notes ingestion (body: source path or list of doc ids). |
| POST | `/api/v1/saarthi/ingestion/code` | Trigger code ingestion (body: source path or list of file paths). |

Exact request/response for ingestion endpoints to be defined when implemented; they are **not** called by the orchestrator for normal chat flow.

---

## 5. Health and Root (Typical)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (e.g. `{ "status": "healthy", "service": "saarthi" }`). May live at app root, not under `/api/v1/saarthi/`. |
| GET | `/` | Root: API name, version, docs link. |

---

## 6. Summary Table (Orchestrator-Relevant Only)

| Method | Path |
|--------|------|
| POST | `/api/v1/saarthi/experts/theory` |
| POST | `/api/v1/saarthi/experts/problem-solving` |
| POST | `/api/v1/saarthi/experts/video` |
| POST | `/api/v1/saarthi/experts/code` |
| POST | `/api/v1/saarthi/experts/multimodal` |
| POST | `/api/v1/saarthi/experts/exam-prep` |
| POST | `/api/v1/saarthi/experts/followup` |
| POST | `/api/v1/saarthi/retrieval/search` |
| GET | `/api/v1/saarthi/context/{conversation_id}` |
| POST | `/api/v1/saarthi/context` |

---

## 7. OpenAPI / Docs

- **Swagger UI**: Typically at `/docs` (FastAPI default).
- **ReDoc**: Typically at `/redoc`.
- All expert and retrieval endpoints should be documented with summary, request body schema, and response schema; use the schemas defined in [05-data-models-and-schemas.md](05-data-models-and-schemas.md).
