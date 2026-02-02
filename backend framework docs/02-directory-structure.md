# Directory Structure

This document describes the **target directory layout** for the Saarthi.ai backend. All paths are relative to the backend root (e.g. `backend/` or project root where the backend lives).

---

## 1. Top-Level Layout

```
backend/
├── main.py                    # FastAPI app entry; CORS; router mount; health/root/shutdown
├── requirements.txt
├── .env.example
│
├── router.py                  # Single router file: all HTTP endpoints (or routers/ per domain)
│
├── model/                     # SQLAlchemy ORM models (persistence entities)
├── schema/                    # Pydantic schemas (request/response validation)
├── dao/                       # Data Access Objects (DB operations only)
├── service/                   # Business logic: experts, retrieval orchestration, ingestion
├── retrieval/                 # Hybrid retrieval engine (ColBERT, Dense, BM25, RRF, re-ranker)
├── ingestion/                 # Ingestion pipelines: video, notes, code (optional submodules)
│
├── utils/                     # Shared utilities: auth_deps, config_model, constants, validators
├── SQL/                        # Database migrations (numbered .sql files)
├── tests/                     # Unit and integration tests
└── scripts/                   # DB create/migrate, seed, env helpers
```

---

## 2. Folder Responsibilities

### 2.1 `model/`

- **Purpose**: SQLAlchemy ORM models for tables used by the backend.
- **Convention**: One file per entity, e.g. `video_metadata_model.py`, `note_chunk_model.py`. Table names prefixed (e.g. `saarthi_video_metadata`).
- **Content**: Model classes only; all inherit from a single Base (e.g. from `utils.config_model` or common library).

### 2.2 `schema/`

- **Purpose**: Pydantic models for API request and response validation.
- **Convention**: One file per domain or entity; schemas named `{Entity}CreateRequest`, `{Entity}UpdateRequest`, `{Entity}Response`, `{Entity}ListResponse`, etc.
- **Content**: No business logic; only field definitions, validators, and `ConfigDict` where needed.

### 2.3 `dao/`

- **Purpose**: Database access only. No business logic, no exception handling.
- **Convention**: One file per entity, class name `*DAO`, inherits from BaseDAO. Methods: `get_*_by_id`, `insert_*`, `update_*`, `list_*`, `delete_*`.
- **Content**: SQLAlchemy queries or raw SQL for complex cases; return data to service layer.

### 2.4 `service/`

- **Purpose**: Business logic called by the router. Orchestrates DAOs, retrieval, and external calls.
- **Convention**: One file per domain or expert, e.g. `theory_expert_service.py`, `retrieval_service.py`, `video_ingestion_service.py`.
- **Content**: Service functions with exception decorator; commits only here; helpers prefixed with `_`.

### 2.5 `retrieval/`

- **Purpose**: Hybrid retrieval implementation used by expert services.
- **Suggested layout**:
  - Query preprocessing.
  - ColBERT, Dense, BM25 clients/wrappers.
  - Reciprocal Rank Fusion.
  - Cross-encoder re-ranker.
  - Top-k result formatting for the rest of the backend.
- **Interface**: Services call retrieval module with query and options; retrieval returns ranked chunks with metadata (source_id, type, score, text, etc.).

### 2.6 `ingestion/`

- **Purpose**: Pipelines that populate vector store and optional DB from raw content.
- **Suggested layout** (optional submodules):
  - Video: transcript extraction, chunking, embedding, write to vector DB.
  - Notes: OCR/LaTeX, chunking, embedding, write to vector DB.
  - Code: AST/function extraction, chunking, embedding, write to vector DB.
- **Content**: Scripts or service-style functions; can be triggered by API or CLI.

### 2.7 `utils/`

- **Purpose**: Shared backend utilities.
- **Typical files**:
  - `config_model.py`: SQLAlchemy Base.
  - `auth_deps.py`: Auth and optional tenant/session resolution (if needed).
  - `constants.py`: Pagination limits, default config.
  - `validators.py`: Reusable validation helpers.
  - `db_utils.py`: Session helpers, connection config.
  - `enums.py`: Shared enums (e.g. intent, content type).

### 2.8 `SQL/`

- **Purpose**: Database migrations.
- **Convention**: Numbered scripts, e.g. `00_run_all_migrations.sql`, `01_create_video_metadata_table.sql`, etc. Run in order.

### 2.9 `tests/`

- **Purpose**: Unit tests (DAO, service) and integration tests (API).
- **Convention**: `test_*_dao.py`, `test_*_service.py`, `conftest.py` for fixtures; optional `integration/` for API tests.

### 2.10 `scripts/`

- **Purpose**: One-off or operational scripts.
- **Examples**: Create DB, run migrations, seed data, generate tokens.

---

## 3. API Prefix

- All backend APIs are under a single prefix, e.g. `/api/v1/saarthi/`.
- Mounted in `main.py` (e.g. `app.include_router(router, prefix="/api/v1/saarthi", tags=["saarthi"])`).

---

## 4. Orchestrator Placement

- The **orchestrator** (LangGraph, Shrijeet) may live:
  - In the **same repo** under e.g. `backend/orchestrator/` or `orchestrator/`, calling backend services via internal imports or HTTP, or
  - In a **separate repo**, calling the backend only via HTTP.
- This documentation assumes the orchestrator **calls the backend via HTTP**; the same contract applies if calls are in-process (same process, same request/response shapes).

---

## 5. What Lives Outside This Directory

- **Frontend / UI**: Separate app (Streamlit/React); calls backend APIs.
- **Dataset / raw assets**: Video files, notes images, code repos — referenced by ingestion; paths configured via env or config.
- **Vector DB data**: Stored by ChromaDB/Qdrant; not versioned as code.
- **Coding guidelines**: Existing project guidelines (e.g. `coding-guidelines/`) apply; [09-development-guidelines.md](09-development-guidelines.md) adapts them for Saarthi backend.
