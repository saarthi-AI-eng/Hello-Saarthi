# Expert Services Interface

This document describes **each expert** from the backend’s perspective: what it receives, what it does, and what it returns. The orchestrator (Shrijeet) calls the corresponding endpoints with the unified request; the backend routes to the right expert service and returns the unified expert response (with optional expert-specific extensions).

---

## 1. Shared Contract

- **Request**: Same as [03-orchestrator-to-backend-contract.md](03-orchestrator-to-backend-contract.md): query, intent, conversation_id?, conversation_history?, options?.
- **Response**: Same as [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md): answer, citations, confidence_score, suggested_followups, expert_used, plus expert-specific fields.

Each expert **service** (backend internal):

1. Validates options (if any).
2. Calls retrieval (with query and optional content_types filter).
3. Optionally uses conversation_history for follow-up or clarification.
4. Builds answer text (may delegate final text to orchestrator/LLM; backend can return only citations + structured data).
5. Builds citations and expert-specific payload.
6. Returns the unified expert response.

Who generates the **final natural-language answer** (backend vs orchestrator/LLM) is a design choice; this doc assumes the backend returns at least **citations and structured data**; it may also return a pre-filled `answer` or leave it empty for the orchestrator to fill with LLM.

---

## 2. Theory Expert

**Intent**: THEORY.  
**Endpoint**: `POST /api/v1/saarthi/experts/theory`.

### 2.1 Purpose

Answer conceptual and theoretical questions using notes, textbook excerpts, and theory-tagged video segments.

### 2.2 Input (from unified request)

- **query**: User question (e.g. “Explain Fourier Transform”, “What is spectral density?”).
- **options**: Optional `{ "include_prerequisites": true \| false }` (when KG is available; default false in Phase 1).

### 2.3 Backend Behavior

1. Call retrieval with query; content_types = ["notes", "video"] (and optionally "exercises" if theory is in exercises).
2. Build citations from top chunks (notes + video with timestamp).
3. If KG available and include_prerequisites=true: query KG for prerequisite topics; add to response.
4. Optionally generate or leave empty an `answer` (e.g. from LLM in backend or leave for orchestrator).
5. Set expert_used = "theory"; confidence from retrieval scores or fixed.

### 2.4 Output Extensions

- **prerequisites** (optional): Array of { topic, reason } when KG is used.

---

## 3. Problem-Solving Expert

**Intent**: PROBLEM_SOLVING.  
**Endpoint**: `POST /api/v1/saarthi/experts/problem-solving`.

### 3.1 Purpose

Guide students through solved exercises: find similar problems and return step-by-step methodology.

### 3.2 Input

- **query**: User question (e.g. “How do I solve this DFT problem?”).
- **options**: Optional `{ "problem_statement": "..." }` if the user pasted a full problem and it’s not the same as query.

### 3.3 Backend Behavior

1. Use query (or problem_statement) for retrieval; content_types = ["exercises", "notes"].
2. Retrieve similar solved problems; extract steps if stored.
3. Build citations (exercise source, page/section).
4. Optionally fill **steps** in response: array of { step_number, description, content }.
5. Set expert_used = "problem_solving".

### 3.4 Output Extensions

- **steps** (optional): Array of { step_number, description, content }.

---

## 4. Video Expert

**Intent**: VIDEO_REFERENCE.  
**Endpoint**: `POST /api/v1/saarthi/experts/video`.

### 4.1 Purpose

Find and reference specific video content: which video, at which timestamp, with a short summary.

### 4.2 Input

- **query**: User question (e.g. “Which video explains convolution?”, “Show me the lecture on FFT”).
- **options**: Optional `{ "topic_filter": "..." }`.

### 4.3 Backend Behavior

1. Call retrieval with query; content_types = ["video"]. Optionally filter by topic if topic_filter provided.
2. Build **video_timestamps**: array of { video_id, title, start_sec, end_sec, summary } from chunk metadata.
3. Build citations with source_type=video, timestamp_start/end, url (e.g. YouTube link with &t=).
4. Set expert_used = "video". Answer may be short (“See the following videos”) or empty for orchestrator to phrase.

### 4.4 Output Extensions

- **video_timestamps**: Array of { video_id, title, start_sec, end_sec, summary }.

---

## 5. Code Expert

**Intent**: CODE_REQUEST.  
**Endpoint**: `POST /api/v1/saarthi/experts/code`.

### 5.1 Purpose

Provide and optionally execute code snippets from course material or generated from theory.

### 5.2 Input

- **query**: User question (e.g. “Write Python code for DFT”, “Run this signal processing code”).
- **options**: Optional `{ "language": "python", "execute": true \| false }`.

### 5.3 Backend Behavior

1. Call retrieval with query; content_types = ["code", "notes"] (notes for theory-backed code).
2. Build **code_snippets**: array of { language, code, explanation, source } from retrieved code chunks.
3. If execute=true: run code in sandbox (Docker, timeout 30s, 512MB, no network); append **execution_output** (stdout/stderr or error message).
4. Build citations (source_type=code).
5. Set expert_used = "code".

### 5.4 Output Extensions

- **code_snippets**: Array of { language, code, explanation, source }.
- **execution_output** (optional): String or { stdout, stderr, success }.

---

## 6. Multimodal (Diagram) Expert

**Intent**: DIAGRAM_EXPLAIN.  
**Endpoint**: `POST /api/v1/saarthi/experts/multimodal`.

### 6.1 Purpose

Understand and explain diagrams, graphs, circuits from notes or user-uploaded image.

### 6.2 Input

- **query**: User question (e.g. “Explain this circuit diagram”).
- **options**: `{ "image_url": "..." }` or `{ "image_base64": "..." }` — one of URL or base64 for the image.

### 6.3 Backend Behavior

1. If image provided: call VLM (e.g. Llama 3.2 Vision) to get description or explanation.
2. Optionally use description to call retrieval (notes/code) for related theory.
3. Build **diagram_explanation** and **related_concepts**.
4. Build citations if retrieval returns relevant notes.
5. Set expert_used = "multimodal".

### 6.4 Output Extensions

- **diagram_explanation**: String (VLM output).
- **related_concepts**: Array of strings.

---

## 7. Exam-Prep Expert

**Intent**: EXAM_PREP.  
**Endpoint**: `POST /api/v1/saarthi/experts/exam-prep`.

### 7.1 Purpose

Quiz the user: generate or retrieve questions, options, correct answer, and explanation.

### 7.2 Input

- **query**: User request (e.g. “Quiz me on Z-transforms”).
- **options**: Optional `{ "topic": "...", "difficulty": "easy" | "medium" | "hard" }`.

### 7.3 Backend Behavior

1. Use topic (from options or extracted from query) to retrieve relevant content; optionally retrieve pre-built quiz questions if stored.
2. Build **question**, **options**, **correct_index**, **explanation** (or leave to orchestrator/LLM to generate from retrieved context).
3. Set expert_used = "exam_prep".

### 7.4 Output Extensions

- **question**: String.
- **options**: Array of strings.
- **correct_index**: Integer (0-based).
- **explanation**: String.

---

## 8. Follow-Up Expert

**Intent**: FOLLOWUP.  
**Endpoint**: `POST /api/v1/saarthi/experts/followup`.

### 8.1 Purpose

Handle follow-up questions like “Can you explain that more simply?” or “Show me another example” using conversation_history (and optionally stored context).

### 8.2 Input

- **query**: Follow-up text.
- **conversation_history**: Required for context (last assistant answer + user follow-up).
- **conversation_id**: Optional; backend may load stored context.

### 8.3 Backend Behavior

1. Use conversation_history (and optionally GET context by conversation_id) to understand “that” (previous topic or answer).
2. Rewrite or expand query for retrieval (e.g. “simplify explanation of X” → retrieve simpler content for X).
3. Call retrieval; build citations and answer as for theory or problem-solving depending on inferred sub-intent.
4. Set expert_used = "followup".

### 8.4 Output

Same unified response; no special extensions required.

---

## 9. Summary Table

| Expert | Intent | Main retrieval types | Special options | Response extensions |
|--------|--------|----------------------|-----------------|---------------------|
| Theory | THEORY | notes, video | include_prerequisites | prerequisites |
| Problem-Solving | PROBLEM_SOLVING | exercises, notes | problem_statement | steps |
| Video | VIDEO_REFERENCE | video | topic_filter | video_timestamps |
| Code | CODE_REQUEST | code, notes | language, execute | code_snippets, execution_output |
| Multimodal | DIAGRAM_EXPLAIN | notes (after VLM) | image_url / image_base64 | diagram_explanation, related_concepts |
| Exam-Prep | EXAM_PREP | notes, exercises (quiz) | topic, difficulty | question, options, correct_index, explanation |
| Follow-Up | FOLLOWUP | all (context-aware) | — | — |

All experts return the common fields (answer, citations, confidence_score, suggested_followups, expert_used) plus any extensions above.
