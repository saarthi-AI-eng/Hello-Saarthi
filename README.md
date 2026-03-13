# Saarthi Backend API

Backend-only repository for **Saarthi.ai** (FastAPI). The frontend lives in a separate repo.

## Stack

- **FastAPI** – REST API
- **PostgreSQL** – via asyncpg + SQLAlchemy 2 (async)
- **JWT** – auth (access + refresh, cookies)
- **AI service** – external chat/experts (configurable base URL)

## Setup

1. **Python 3.11+** and **PostgreSQL** installed.

2. **Virtual env** (from repo root):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r saarthi_backend/requirements.txt
   ```

4. **Environment** – copy and edit:
   ```bash
   cp saarthi_backend/.env.example saarthi_backend/.env
   ```
   Set at least:
   - `DATABASE_URL` – PostgreSQL connection string (e.g. `postgresql+asyncpg://user:pass@localhost:5432/saarthi`)
   - `JWT_SECRET` – strong secret in production
   - `AI_SERVICE_BASE_URL` – AI service base URL (or leave default)

5. **Database** – create DB then run migrations:
   ```bash
   python -m saarthi_backend.migrations.run_migrations
   ```
   Uses `DATABASE_URL` from `saarthi_backend/.env` (or env).

6. **Run server** (from repo root):
   ```bash
   cd saarthi_backend && python main.py
   ```
   Or: `python saarthi_backend/main.py` from root.  
   API: **http://localhost:8000** (docs: http://localhost:8000/docs).

## Project layout

```
saarthi_backend/
├── main.py              # App entry, lifespan, CORS, mounts
├── router.py            # /api/v1/saarthi – experts, retrieval, context, ingestion
├── deps.py              # get_db, get_current_user, get_pagination, get_ai_client
├── requirements.txt
├── .env.example
├── migrations/          # SQL migrations (run via run_migrations.py)
├── routers/             # /api – auth, chat, courses, videos, notes, quizzes, etc.
├── model/               # SQLAlchemy models
├── dao/                 # Data access
├── schema/              # Pydantic request/response
├── service/             # Auth, experts, retrieval, context, ingestion, seed
├── client/              # AI service HTTP client
└── utils/               # Config, JWT, password, exceptions, logging
```

## API overview

- **Auth**: `/api/auth` – signin, signup, refresh, me, logout
- **Chat**: `/api/chat` – message, conversations CRUD, send message
- **Courses**: `/api/courses` – CRUD, enrollments, assignments, materials, stream
- **Videos**: `/api/videos` – CRUD, progress, notes
- **Notes**: `/api/notes` – CRUD (standalone study notes)
- **Upload**: `POST /api/upload` – file upload → `uploads/`
- **Search**: `/api/search`
- **Orchestrator**: `/api/v1/saarthi` – experts, retrieval, context, ingestion

Static uploads served at `/uploads/`. Health: `GET /health`.

## Frontend

Point the frontend API base to this backend (e.g. `VITE_API_URL=http://localhost:8000/api`). Frontend repo is separate.
