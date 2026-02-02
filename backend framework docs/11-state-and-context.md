# State and Context

This document describes **conversation state and context**: what the backend may store, what the orchestrator may send, and what is returned for follow-up and memory. No code — only specifications.

---

## 1. Scope

- **Orchestrator** (Shrijeet) owns the **conversation state machine** (LangGraph): current node, conversation history in memory, etc.
- **Backend** may optionally store **context** per conversation: summary, metadata (e.g. last intent, topics discussed), and updated_at. This supports:
  - **Follow-up expert**: “Explain that more simply” — backend can load context to know “that” refers to previous topic.
  - **Analytics**: Topics queried, intent distribution (if stored in metadata).
  - **Future**: Student profile, weak areas (Phase 3+).

The backend does **not** store full conversation history by default; it may store a **summary** or **metadata** only. Full history is passed by the orchestrator in each request (conversation_history).

---

## 2. Context Object (Stored by Backend)

When the backend stores context for a conversation, it uses a **context object** with at least:

| Field | Type | Description |
|-------|------|-------------|
| conversation_id | string (UUID) | Unique conversation identifier. |
| summary | string or null | Optional short summary of the conversation (e.g. last topic or one-paragraph summary). |
| metadata | object | Optional key-value: e.g. last_intent, last_topic, topics_list, last_source_ids. |
| updated_at | string (ISO 8601) or null | Last update time. |

- **summary**: May be updated by the orchestrator (POST /context) after each turn or periodically; or the backend may never set it (orchestrator-only summary).
- **metadata**: Flexible; backend may store last_intent, last_topic so that follow-up expert can resolve “that” without full history. Orchestrator may also send metadata to upsert.

---

## 3. GET Context (Orchestrator → Backend)

- **Endpoint**: `GET /api/v1/saarthi/context/{conversation_id}`.
- **Response**: See [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md) (Context Response): conversation_id, summary?, metadata?, updated_at?.
- **404**: If no context exists for that conversation_id; orchestrator may treat as “no stored context” and rely only on conversation_history.

---

## 4. POST Context (Orchestrator → Backend)

- **Endpoint**: `POST /api/v1/saarthi/context`.
- **Body**:
  - **conversation_id** (required): string (UUID).
  - **summary** (optional): string.
  - **metadata** (optional): object.
- **Behavior**: Upsert context for that conversation_id. Replace summary and metadata (or merge — document which). Set updated_at.
- **Response**: 200 or 201 with stored context object (or minimal success).

Use case: After each turn, orchestrator may POST a short summary or metadata so that follow-up or future requests can use GET context when conversation_history is not sent (e.g. new request with only conversation_id).

---

## 5. Conversation History (Passed in Request)

- **conversation_history** is **not** stored by the backend by default; it is sent by the orchestrator in each expert request.
- **Format**: Array of messages: `[{ "role": "user" | "assistant", "content": "..." }]`. Typically last N messages (e.g. 5 or 10).
- **Follow-up expert**: Uses conversation_history (and optionally GET context) to resolve “that” and rewrite query for retrieval.

---

## 6. Who Updates Context

- **Option A**: Orchestrator updates context (POST /context) after each turn with summary and/or metadata. Backend only stores and returns it.
- **Option B**: Backend updates context internally (e.g. after each expert call, store last_intent and last_topic in metadata). Orchestrator only reads (GET).
- **Option C**: Hybrid: Orchestrator sends summary; backend may add metadata (e.g. last_source_ids from citations).

Document the chosen policy in the implementation; this doc only defines the shape and endpoints.

---

## 7. Retention and Limits

- **Retention**: How long to keep context (e.g. 24 hours, 7 days, or indefinite) is implementation-defined. Document in backend config.
- **Size limits**: summary length, metadata key count or size — implement reasonable limits to avoid abuse.

---

## 8. Phase 3+ (Optional): Student Profile

- **Future**: Backend may store a **student profile** (user_id or anonymous_id): topics queried, difficulty, questions marked helpful. Used for adaptive difficulty, prerequisite suggestions, progress tracking.
- **Not part of PoC**: Document in roadmap; not required for initial backend contract. Context in this doc is **conversation-level** only.
