# Backend-to-Orchestrator Responses

This document defines **what the backend returns** to the orchestrator: response schemas, examples, and error formats. The orchestrator must consume these shapes.

---

## 1. Base Response Wrapper (Optional)

All successful responses may be wrapped in a **base response** for consistency:

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for 2xx. |
| `data` | object | The actual payload (expert response, retrieval result, or context). |
| `meta` | object | Optional: `request_id`, `latency_ms`, etc. |

If the backend uses a wrapper, the orchestrator must read `data` for the actual payload. If no wrapper is used, the response body **is** the payload directly. This doc describes the **payload** shape in both cases.

---

## 2. Expert Response (Unified Shape)

All expert endpoints return a **unified expert response** with optional expert-specific fields.

### 2.1 Common Fields (All Experts)

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Main answer text (may be empty if response is citation-only). |
| `citations` | array of citation objects | Source references (notes, video, code). See below. |
| `confidence_score` | float (0–1) | Backend confidence in the answer (optional). |
| `suggested_followups` | array of strings | Optional suggested follow-up questions. |
| `expert_used` | string | One of: `theory`, `problem_solving`, `video`, `code`, `multimodal`, `exam_prep`, `followup`. |

### 2.2 Citation Object

| Field | Type | Description |
|-------|------|-------------|
| `source_type` | string | One of: `notes`, `video`, `code`, `exercise`. |
| `source_id` | string | Id of the source (e.g. note chunk id, video id). |
| `title` | string | Human-readable title (e.g. video title, "Notes Page 42"). |
| `excerpt` | string | Short excerpt of the cited content. |
| `timestamp_start` | float or null | For video: start time in seconds. |
| `timestamp_end` | float or null | For video: end time in seconds. |
| `url` | string or null | Optional link (e.g. video URL with timestamp). |

### 2.3 Expert-Specific Extensions

- **THEORY**: May include `prerequisites`: array of `{ "topic": "...", "reason": "..." }` (when KG is available).
- **VIDEO**: May include `video_timestamps`: array of `{ "video_id": "...", "title": "...", "start_sec": 0, "end_sec": 0, "summary": "..." }`.
- **CODE**: May include `code_snippets`: array of `{ "language": "python", "code": "...", "explanation": "...", "source": "..." }`; optionally `execution_output` if execution was requested.
- **PROBLEM_SOLVING**: May include `steps`: array of `{ "step_number": 1, "description": "...", "content": "..." }`.
- **MULTIMODAL**: May include `diagram_explanation`: string; `related_concepts`: array of strings.
- **EXAM_PREP**: May include `question`: string; `options`: array of strings; `correct_index`: integer; `explanation`: string (for quiz-style).

---

## 3. Example: Theory Expert Response

```json
{
  "answer": "The Fourier Transform decomposes a signal into its frequency components...",
  "citations": [
    {
      "source_type": "notes",
      "source_id": "note_chunk_42",
      "title": "Notes Page 42 - Fourier Transform",
      "excerpt": "Definition: F(ω) = ∫ f(t) e^{-iωt} dt",
      "timestamp_start": null,
      "timestamp_end": null,
      "url": null
    },
    {
      "source_type": "video",
      "source_id": "video_12",
      "title": "Introduction to Fourier Transform",
      "excerpt": "In this segment we define the continuous-time Fourier transform.",
      "timestamp_start": 270.0,
      "timestamp_end": 315.0,
      "url": "https://youtube.com/watch?v=...&t=270"
    }
  ],
  "confidence_score": 0.92,
  "suggested_followups": ["What is the difference between DFT and FFT?", "Give an example of FFT in Python."],
  "expert_used": "theory",
  "prerequisites": [
    { "topic": "Complex Numbers", "reason": "Required for understanding exponential form." }
  ]
}
```

---

## 4. Example: Video Expert Response

```json
{
  "answer": "The topic is covered in the following videos. You can jump to the timestamps below.",
  "citations": [],
  "confidence_score": 1.0,
  "suggested_followups": [],
  "expert_used": "video",
  "video_timestamps": [
    {
      "video_id": "abc123",
      "title": "Fourier Transform Explained",
      "start_sec": 270,
      "end_sec": 315,
      "summary": "Definition of continuous-time Fourier transform."
    }
  ]
}
```

---

## 5. Example: Code Expert Response

```json
{
  "answer": "Here is a Python implementation of DFT based on the course material.",
  "citations": [
    {
      "source_type": "code",
      "source_id": "assignment_3_ex2",
      "title": "Assignment 3, Exercise 2",
      "excerpt": "def dft(x): ...",
      "timestamp_start": null,
      "timestamp_end": null,
      "url": null
    }
  ],
  "confidence_score": 0.88,
  "suggested_followups": [],
  "expert_used": "code",
  "code_snippets": [
    {
      "language": "python",
      "code": "import numpy as np\ndef dft(x):\n    N = len(x)\n    ...",
      "explanation": "N-point DFT implementation.",
      "source": "Assignment 3, Ex 2"
    }
  ],
  "execution_output": null
}
```

---

## 6. Retrieval-Only Response (`POST /retrieval/search`)

| Field | Type | Description |
|-------|------|-------------|
| `results` | array of chunk objects | Ranked chunks. |
| `query` | string | Echo of the query. |
| `total_returned` | integer | Number of results returned. |

**Chunk object**:

| Field | Type | Description |
|-------|------|-------------|
| `content_type` | string | `notes`, `video`, `code`, `exercise`. |
| `source_id` | string | Id of the source. |
| `text` | string | Chunk text. |
| `score` | float | Relevance score (if include_scores was true). |
| `metadata` | object | title, video_id, start_sec, end_sec, etc. |

**Example**:

```json
{
  "results": [
    {
      "content_type": "notes",
      "source_id": "note_chunk_42",
      "text": "Definition: F(ω) = ∫ f(t) e^{-iωt} dt...",
      "score": 0.95,
      "metadata": { "title": "Notes Page 42", "page": 42 }
    }
  ],
  "query": "Fourier Transform definition",
  "total_returned": 1
}
```

---

## 7. Context Response (`GET /context/{conversation_id}`)

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | string | Echo of the id. |
| `summary` | string or null | Stored conversation summary (if any). |
| `metadata` | object | Arbitrary metadata (topics, last_intent, etc.). |
| `updated_at` | string (ISO 8601) or null | Last update time. |

---

## 8. Error Response (4xx / 5xx)

All errors return a **consistent error body**:

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `false`. |
| `error` | object | See below. |

**Error object**:

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Machine-readable code (e.g. `VALIDATION_ERROR`, `NOT_FOUND`, `RETRIEVAL_ERROR`). |
| `message` | string | Human-readable message (safe for UI). |
| `details` | object or null | Optional extra info (e.g. validation errors). |

**Example (400)**:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request body.",
    "details": { "query": ["Field required."] }
  }
}
```

**Example (500)**:

```json
{
  "success": false,
  "error": {
    "code": "RETRIEVAL_ERROR",
    "message": "Retrieval service temporarily unavailable.",
    "details": null
  }
}
```

---

## 9. HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success (expert response, retrieval result, context). |
| 201 | Created (e.g. context upserted). |
| 400 | Bad request (validation, invalid options). |
| 404 | Not found (e.g. conversation_id for context). |
| 500 | Internal server error (retrieval failure, DB error, etc.). |

The orchestrator should handle 4xx by logging and showing a user-friendly message; 5xx may be retried with backoff.
