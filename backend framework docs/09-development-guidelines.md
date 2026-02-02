# Development Guidelines

This document adapts the **existing coding guidelines** (e.g. OmniSage / workbench) for the Saarthi.ai backend. Follow these conventions when implementing the backend. For full details, refer to the project’s `coding-guidelines/` docs; this file summarizes and Saarthi-specific rules.

---

## 1. Layering

- **Router**: Entry point only. Validate input (Pydantic), call service, return response. No business logic, no DB access, no exception handling (let global handler catch).
- **Service**: All business logic, retrieval orchestration, commits. Calls DAOs and retrieval. Uses exception decorator; commits only here.
- **DAO**: Database operations only. No business logic, no exception handling. Returns data to service.
- **Retrieval**: Internal module called by services. No HTTP; returns chunks with metadata.

---

## 2. Router

- Every route has **response_model** (Pydantic schema) and **status_code** on success (200, 201 as appropriate).
- Request body validated with Pydantic schemas only.
- DB session via **Depends(get_async_db_session)** (or equivalent); pass session to service.
- **No exception handling** in router; only call service and return result. Exceptions bubble to global handler.
- **Logging**: Log at router entry: endpoint name, key params (e.g. intent, conversation_id). Do not log full body if it contains PII.
- **Auth** (if used): Use dependency (e.g. AuthValidator or custom) for protected routes; document which routes are public vs protected.
- Endpoint names: **RESTful, self-explanatory** (e.g. `POST /api/v1/saarthi/experts/theory`, not `/exp/t`).

---

## 3. Service

- Every service function has the **exception decorator** (e.g. `@handle_exceptions(logger=logger, rollback_on_exception=True)`). Use project’s actual decorator name (e.g. `handle_exception` or `handle_exceptions`).
- **Commits** only in service; never in router or DAO.
- **Rollback**: Use `rollback_on_exception=True` for multi-step or transactional operations.
- **Helpers**: Place helper functions **above** the service function that uses them; name with leading **underscore** (e.g. `_build_citations`, `_format_video_timestamp`).
- **Helpers**: Do not catch exceptions; raise **HTTPException** for business-rule violations (e.g. validation, “not found”). Let unexpected errors propagate to the decorator.
- **Logging**: Log at service entry: function name, key params (query, intent, content_types). Do not log full conversation_history if long or PII.
- **DAO usage**: Instantiate DAO(s) in the service, pass session; call DAO methods; commit after all writes.

---

## 4. DAO

- Every DAO class **inherits from BaseDAO** (or project’s base). Constructor: `__init__(self, session)` (or `db`); pass session to base.
- **No exception handling**; let errors propagate to service.
- **Naming**: Class name ends with `DAO` (e.g. `VideoMetadataDAO`, `NoteChunkDAO`). Methods: `get_*_by_id`, `insert_*`, `update_*`, `list_*`, `delete_*`.
- Prefer **SQLAlchemy** for queries; raw SQL only for complex cases. DAOs **perform DB operations and return data**; no business logic.
- **Logging** (optional): Log at DAO for non-trivial operations (e.g. “DAO: fetching video by id”, id). Avoid logging large result sets.

---

## 5. Schemas (Pydantic)

- **Naming**: `{Entity}CreateRequest`, `{Entity}UpdateRequest`, `{Entity}Response`, `{Entity}ListResponse`, `{Entity}ListQuery`. Request suffix `Request` or `Query`; response suffix `Response`.
- **Money**: Use custom type (e.g. MoneyDecimal) for money fields if applicable.
- **Config**: Use `ConfigDict(from_attributes=True)` for response schemas that are built from ORM models. Use `populate_by_name=True` if using aliases.
- **Validation**: Use Field(...) for required, max_length, ge/le; keep validation in schema, not in service (except business rules).

---

## 6. Models (SQLAlchemy)

- All models **inherit from a single Base** (e.g. from `utils.config_model` or common library).
- **Table names**: Prefixed (e.g. `saarthi_video_metadata`, `saarthi_note_chunks`).
- **Primary key**: Prefer UUID for new tables; document any use of auto-increment.
- **Timestamps**: created_at, updated_at with timezone where applicable.

---

## 7. Logging

- **Per-module logger**: One logger per file (e.g. `logger = CloudWatchLogger(__name__)` or project’s logger). Name after the file/module.
- **Mandatory points**:
  - **Router**: Log when endpoint is called; include endpoint name and key params (not full body).
  - **Service**: Log when entering service function; include function name and key params.
  - **DAO**: Log for non-trivial DB operations (operation type, id).
- **Context**: Include request_id, session_id, user_id (if available) for tracing. Do not log passwords, tokens, or full conversation content.
- **Levels**: DEBUG for verbose; INFO for normal flow; WARNING for recoverable issues; ERROR for failures.

---

## 8. Errors and Exceptions

- **Router**: No try/except; let global exception handler return consistent error response (see [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md) error shape).
- **Service**: Use exception decorator; in helpers raise **HTTPException** with safe, user-facing message and appropriate status_code (400, 404, 422, etc.).
- **DAO**: No exception handling; propagate DB errors to service.
- **Error response**: Always return `{ "success": false, "error": { "code", "message", "details" } }` for 4xx/5xx; use consistent codes (e.g. VALIDATION_ERROR, NOT_FOUND, RETRIEVAL_ERROR).

---

## 9. API Prefix and Tags

- All backend routes under **one prefix**: `/api/v1/saarthi/`.
- Use **tags** for OpenAPI grouping (e.g. `tags=["experts"]`, `tags=["retrieval"]`, `tags=["context"]`).

---

## 10. Tests

- **DAO tests**: Unit tests for each DAO (get, insert, update, list, delete) with test DB or mocks.
- **Service tests**: Unit tests for each expert service and retrieval service; mock DAO and retrieval layer.
- **Integration tests** (optional): Test full request/response for key endpoints (e.g. POST expert, POST retrieval/search) with test DB and test vector store.
- **Conftest**: Shared fixtures (session, test client, sample data) in `tests/conftest.py`.

---

## 11. Saarthi-Specific Notes

- **No omnisage_common_lib dependency required**: If this project does not use the common library, implement a local Base (SQLAlchemy), local logger, and optional auth deps. Keep the same **layering and naming** as above.
- **Orchestrator contract**: All expert and retrieval endpoints must accept and return the shapes defined in [03-orchestrator-to-backend-contract.md](03-orchestrator-to-backend-contract.md) and [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md). Do not change response shape without updating those docs and coordinating with Shrijeet.
- **Ingestion**: Ingestion scripts/APIs are separate from the “query” path; they may run in batch or on-demand but do not block the orchestrator.

---

## 12. Reference

- Project coding guidelines: `coding-guidelines/docs/backend_guideline/` (logging, data_validation, sqlalchemy_model, router, service_function, daos).
- Workbench structure: `workbench/backend/` for concrete layout (router, service, dao, model, schema, utils, SQL, tests).
