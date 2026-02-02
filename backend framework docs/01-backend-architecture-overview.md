# Backend Architecture Overview

This document describes the high-level architecture of the Saarthi.ai backend and how it fits with the orchestrator and the rest of the system.

---

## 1. Role of the Backend

The backend is the **data and retrieval engine** that:

- **Stores** and **indexes** content: notes, video transcripts, solved exercises, code files.
- **Exposes APIs** that the orchestrator (and optionally the UI) call to get answers, citations, and related content.
- **Runs retrieval**: hybrid retrieval (ColBERT + Dense + BM25 → RRF → re-ranker) and returns ranked chunks with metadata.
- **Serves expert logic**: each expert (Theory, Problem-Solving, Video, Code, Multimodal) is backed by backend services that perform retrieval and return structured responses.

The **orchestrator** (Shrijeet, LangGraph) owns:

- Query classification and intent detection.
- Routing to the correct expert.
- Conversation state and flow.

The **backend** does **not** own the orchestrator graph; it only provides the services and APIs the orchestrator calls.

---

## 2. High-Level Layering

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Shrijeet)                       │
│              LangGraph · Query classification · Routing          │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP / in-process calls
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND API LAYER                            │
│   Router(s) · Request validation · Response shaping             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                                │
│   Expert services · Retrieval orchestration · Business logic     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌───────────────────┐ ┌───────────────┐ ┌───────────────────┐
│   RETRIEVAL       │ │   DAO LAYER   │ │   EXTERNAL        │
│   ENGINE          │ │   (if needed) │ │   (Vector DB,     │
│   ColBERT+Dense   │ │   Persistence │ │   Ollama, etc.)   │
│   +BM25+RRF       │ │               │ │                   │
└───────────────────┘ └───────────────┘ └───────────────────┘
```

- **API layer**: FastAPI routers; validate input; call services; return responses. No business logic.
- **Service layer**: Expert logic, retrieval orchestration, commits, transactions. Calls DAOs and retrieval.
- **DAO layer**: Database access only. No business logic, no exception handling.
- **Retrieval engine**: Hybrid retrieval implementation; used by services.
- **External**: Vector DB (ChromaDB/Qdrant), LLM (Ollama), etc.

---

## 3. Integration with Orchestrator

- The orchestrator **sends** a classified request (e.g. intent = THEORY, query text, conversation_id) to the backend.
- The backend **returns** a structured response: answer text, citations, video timestamps, code snippets, confidence, etc., as defined in the contract and response docs.
- The orchestrator uses that response to update state and send the final reply to the user.

Details of request and response shapes are in:

- [03-orchestrator-to-backend-contract.md](03-orchestrator-to-backend-contract.md)
- [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md)

---

## 4. Phased Knowledge Graph (Reminder)

Per the clarification document:

- **Weeks 1–6**: No knowledge graph. Backend provides hybrid retrieval only.
- **Weeks 7–9**: Lightweight KG for content linking (Topic ↔ Video/Notes/Code). Backend may expose “related content” APIs.
- **Weeks 10–12**: Prerequisite relationships; backend may expose “prerequisites for topic X” and adaptive suggestions.
- **Post-PoC**: Full GraphRAG if scaling.

The backend design should allow adding KG-backed services later without changing the orchestrator contract where possible.

---

## 5. Technology Assumptions (Reference)

- **API**: FastAPI, async.
- **Persistence**: SQLAlchemy async, PostgreSQL (or SQLite for PoC).
- **Vector store**: ChromaDB (dev), Qdrant (production).
- **LLM**: Local (Ollama) — may be called from backend or from orchestrator; contract should be clear who calls LLM for final answer generation.
- **Logging**: Structured logging (e.g. per-module logger); context: user_id, session_id, request_id where available.

Exact tech choices are decided during implementation; this doc describes the logical architecture.
