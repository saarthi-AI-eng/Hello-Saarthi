# Orchestrator-to-Backend Contract

This document defines **what the orchestrator (Shrijeet) must send** to the backend: request formats, endpoints, payloads, and conventions. The backend will implement these contracts.

---

## 1. Base Conventions

### 1.1 API Base URL

- **Prefix**: `/api/v1/saarthi/`
- **Example base**: `https://<host>/api/v1/saarthi`

### 1.2 HTTP Method and Content-Type

- **POST** for all expert and retrieval calls that carry a body.
- **GET** for read-only operations (e.g. get conversation context, list topics).
- **Content-Type**: `application/json` for request bodies.
- **Accept**: `application/json` for responses.

### 1.3 Common Request Headers (Optional)

| Header | Purpose |
|--------|--------|
| `X-Request-Id` | Unique request ID for tracing (optional). |
| `X-Session-Id` | Session or conversation ID (optional). |
| `X-User-Id` | User identifier (optional; for logging/analytics). |

---

## 2. Orchestrator Request: Expert Invocation

When the orchestrator routes to an expert, it calls the corresponding backend endpoint with a **unified expert request** shape. The backend returns an expert-specific response (see [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md)).

### 2.1 Unified Expert Request Body

The orchestrator sends a **single request body** that all expert endpoints accept (with optional expert-specific fields).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | The user's question or request text. |
| `intent` | string | Yes | One of: `THEORY`, `PROBLEM_SOLVING`, `VIDEO_REFERENCE`, `CODE_REQUEST`, `DIAGRAM_EXPLAIN`, `EXAM_PREP`, `FOLLOWUP`. |
| `conversation_id` | string (UUID) | No | Id of the current conversation; used for context/memory. |
| `conversation_history` | array of messages | No | Last N messages: `[{ "role": "user" \| "assistant", "content": "..." }]`. |
| `options` | object | No | Expert-specific options (see per-expert section below). |

**Example (minimal)**:

```json
{
  "query": "Explain Fourier Transform",
  "intent": "THEORY"
}
```

**Example (with context)**:

```json
{
  "query": "Can you explain that more simply?",
  "intent": "FOLLOWUP",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_history": [
    { "role": "user", "content": "What is spectral density?" },
    { "role": "assistant", "content": "Spectral density is..." }
  ]
}
```

### 2.2 Per-Expert Options (optional `options` object)

- **THEORY**: `{ "include_prerequisites": true \| false }` — whether to include prerequisite topics (when KG is available).
- **PROBLEM_SOLVING**: `{ "problem_statement": "..." }` — full problem text if different from query.
- **VIDEO_REFERENCE**: `{ "topic_filter": "..." }` — filter videos by topic.
- **CODE_REQUEST**: `{ "language": "python", "execute": true \| false }` — language and whether to run code in sandbox.
- **DIAGRAM_EXPLAIN**: `{ "image_url": "...", "image_base64": "..." }` — one of URL or base64 for the diagram (multimodal).
- **EXAM_PREP**: `{ "topic": "...", "difficulty": "easy \| medium \| hard" }`.

The backend may ignore unknown options; it must not fail on extra fields.

---

## 3. Endpoints the Orchestrator Calls

### 3.1 Expert Endpoints (POST)

| Intent | Endpoint | Request body |
|--------|----------|--------------|
| THEORY | `POST /api/v1/saarthi/experts/theory` | Unified expert request (see above). |
| PROBLEM_SOLVING | `POST /api/v1/saarthi/experts/problem-solving` | Unified expert request. |
| VIDEO_REFERENCE | `POST /api/v1/saarthi/experts/video` | Unified expert request. |
| CODE_REQUEST | `POST /api/v1/saarthi/experts/code` | Unified expert request. |
| DIAGRAM_EXPLAIN | `POST /api/v1/saarthi/experts/multimodal` | Unified expert request (with image in options). |
| EXAM_PREP | `POST /api/v1/saarthi/experts/exam-prep` | Unified expert request. |
| FOLLOWUP | `POST /api/v1/saarthi/experts/followup` | Unified expert request (uses conversation_history). |

All of these use the **same request body shape**; the backend routes by endpoint and uses `intent` for validation.

### 3.2 Retrieval-Only Endpoint (POST)

When the orchestrator needs **raw retrieval** (e.g. for custom flow or debugging):

- **Endpoint**: `POST /api/v1/saarthi/retrieval/search`
- **Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query. |
| `content_types` | array of strings | No | Filter: `["notes", "video", "code", "exercises"]`. Default: all. |
| `top_k` | integer | No | Max results. Default: 5. |
| `include_scores` | boolean | No | Include relevance scores. Default: true. |

**Example**:

```json
{
  "query": "Fourier Transform definition",
  "content_types": ["notes", "video"],
  "top_k": 5
}
```

### 3.3 Context / Memory (GET or POST)

- **Get context**: `GET /api/v1/saarthi/context/{conversation_id}` — returns stored context for that conversation (if any).
- **Upsert context**: `POST /api/v1/saarthi/context` — body: `{ "conversation_id": "...", "summary": "...", "metadata": {} }` (optional; for backend to store conversation summary or metadata).

Exact shape of context is defined in [11-state-and-context.md](11-state-and-context.md).

---

## 4. Query Classification (Orchestrator Responsibility)

The **orchestrator** is responsible for:

1. Classifying the user query into one of the intents above.
2. Choosing the correct expert endpoint.
3. Building the unified request body (query, intent, conversation_id, conversation_history, options).
4. Calling the backend and handling HTTP errors (4xx/5xx).
5. Passing the backend response to the next step (e.g. LLM for final answer, or direct return).

The backend **does not** re-classify intent; it trusts the orchestrator's `intent` and route.

---

## 5. Idempotency and Retries

- Expert and retrieval endpoints are **idempotent** for the same (query, intent, options): calling twice with the same body yields the same retrieval/result; only the generated answer might differ if LLM is involved.
- The orchestrator may **retry** on 5xx or network errors; use `X-Request-Id` to correlate logs.

---

## 6. Summary Table: What Orchestrator Sends

| Call | Method | Path | Body (main fields) |
|------|--------|------|--------------------|
| Theory expert | POST | `/api/v1/saarthi/experts/theory` | query, intent, conversation_id?, conversation_history?, options? |
| Problem-solving expert | POST | `/api/v1/saarthi/experts/problem-solving` | Same. |
| Video expert | POST | `/api/v1/saarthi/experts/video` | Same. |
| Code expert | POST | `/api/v1/saarthi/experts/code` | Same. |
| Multimodal expert | POST | `/api/v1/saarthi/experts/multimodal` | Same (+ image in options). |
| Exam-prep expert | POST | `/api/v1/saarthi/experts/exam-prep` | Same. |
| Followup expert | POST | `/api/v1/saarthi/experts/followup` | Same. |
| Retrieval search | POST | `/api/v1/saarthi/retrieval/search` | query, content_types?, top_k?, include_scores? |
| Get context | GET | `/api/v1/saarthi/context/{conversation_id}` | — |
| Upsert context | POST | `/api/v1/saarthi/context` | conversation_id, summary?, metadata? |

All request bodies are JSON; responses are JSON as defined in [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md).
