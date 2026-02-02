# Retrieval Layer

This document describes the **hybrid retrieval engine**: how it is composed, how expert services call it, and what interfaces it exposes. No code — only specifications.

---

## 1. Purpose

The retrieval layer:

- Takes a **query** (and optional filters).
- Runs **multiple retrievers** (ColBERT, Dense, BM25).
- **Fuses** results (Reciprocal Rank Fusion).
- **Re-ranks** with a cross-encoder (optional).
- Returns **top-k chunks** with metadata (source_id, text, score, content_type, etc.) for the service layer to use in building expert responses.

Per the phased approach, **Weeks 1–6**: no knowledge graph; retrieval is purely hybrid (ColBERT + Dense + BM25 + RRF + re-ranker). KG is added later for content linking and prerequisites.

---

## 2. Pipeline Overview

```
Query (text)
    │
    ▼
┌─────────────────────┐
│ Query preprocessor  │  Spell correction, query expansion, math notation normalization (optional)
└──────────┬──────────┘
           │
           ▼
    ┌──────┴──────┬──────────────┐
    ▼            ▼              ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ColBERTv2│ │ Dense   │ │  BM25   │
│(Late Int)│ │(Semantic)│ │(Keyword)│
└────┬────┘ └────┬────┘ └────┬────┘
     │ Top-20   │ Top-20    │ Top-20
     └──────────┴─────┬─────┘
                     ▼
          ┌──────────────────────┐
          │ Reciprocal Rank      │
          │ Fusion (RRF)         │
          │ k=60 (or configurable)│
          └──────────┬───────────┘
                     ▼
          ┌──────────────────────┐
          │ Cross-encoder        │
          │ Re-ranker            │
          │ (final relevance)    │
          └──────────┬───────────┘
                     ▼
          ┌──────────────────────┐
          │ Top-K results        │
          │ (with metadata)      │
          └──────────────────────┘
```

---

## 3. Components (Logical)

### 3.1 Query Preprocessor

- **Input**: Raw query string.
- **Output**: Cleaned/expanded query (and optionally multiple query variants for multi-vector retrieval).
- **Optional**: Spell correction, synonym expansion, LaTeX/math normalization so that "FT" and "Fourier Transform" align with indexed content.

### 3.2 ColBERT (Late Interaction)

- **Role**: Token-level matching; good for precise technical terms.
- **Input**: Query text.
- **Output**: Ranked list of chunk ids (or chunk objects) with scores; top-20 (or configurable).
- **Backend**: RAGatouille or equivalent; index built from same chunks as Dense/BM25.

### 3.3 Dense Retriever (Semantic)

- **Role**: Semantic similarity via embedding.
- **Input**: Query text (embedded with same model as index).
- **Output**: Top-20 chunks by cosine similarity (or equivalent).
- **Backend**: Vector DB (ChromaDB/Qdrant) with a single embedding model (e.g. sentence-transformers or BGE).

### 3.4 BM25 (Sparse / Keyword)

- **Role**: Exact keyword and term matching.
- **Input**: Query text (tokenized).
- **Output**: Top-20 chunks by BM25 score.
- **Backend**: Same text store indexed for BM25 (e.g. Elasticsearch, or in-memory rank_bm25 over chunk text).

### 3.5 Reciprocal Rank Fusion (RRF)

- **Formula**: For each document d, RRF_score(d) = Σ 1 / (k + rank_i(d)), where k = 60 (or configurable), rank_i(d) = rank of d in retriever i.
- **Input**: Three ranked lists (ColBERT, Dense, BM25).
- **Output**: Single ranked list (combined, deduplicated by chunk id).

### 3.6 Cross-Encoder Re-Ranker

- **Role**: Rerank the fused list by relevance (query, chunk text).
- **Input**: Query + top-N fused chunks (e.g. top 20).
- **Output**: Re-scored and re-ordered top-K (e.g. 5).
- **Backend**: Cross-encoder model (e.g. ms-marco or domain-specific).

---

## 4. Interface to Services

### 4.1 Programmatic (Service Layer)

Expert services (and any other backend code) call the retrieval layer with:

- **query**: string.
- **content_types**: optional list ["notes", "video", "code", "exercises"]; default all.
- **top_k**: integer (default 5).
- **include_scores**: boolean (default true).

**Return**: List of chunk objects: { content_type, source_id, text, score?, metadata }.

The retrieval module is **internal** to the backend; it is not necessarily exposed as a separate microservice. The **API** `POST /api/v1/saarthi/retrieval/search` is a thin wrapper that calls this same interface and returns the shape defined in [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md).

### 4.2 API (Orchestrator)

See [03-orchestrator-to-backend-contract.md](03-orchestrator-to-backend-contract.md) and [04-backend-to-orchestrator-responses.md](04-backend-to-orchestrator-responses.md): `POST /api/v1/saarthi/retrieval/search` with body { query, content_types?, top_k?, include_scores? } and response { results, query, total_returned }.

---

## 5. Indexing Assumptions

- **Same chunks** are indexed in:
  - ColBERT index (if used),
  - Vector DB (embedding model),
  - BM25 index (text).
- **Metadata** (source_id, title, start_sec, end_sec, content_type) is stored with each chunk so that retrieval results can be turned into **citations** without an extra DB lookup (or with a lightweight lookup for richer display).

---

## 6. Configuration

- **Top-K per retriever**: 20 (or configurable).
- **RRF k**: 60 (or configurable).
- **Final top-K**: 5 (or configurable).
- **Re-ranker**: on/off and model name via config.
- **Content type filter**: Applied after retrieval (filter by content_type) or at query time (query only specific collections). Document which strategy is used.

---

## 7. Failure Handling

- **ColBERT/Dense/BM25 timeout or error**: Log; return partial results from healthy retrievers, or fail the request (configurable).
- **Vector DB down**: Return 503 or 500 with error code RETRIEVAL_ERROR; orchestrator may retry.
- **Empty results**: Return empty list; expert service may still generate an answer from LLM (orchestrator responsibility) or return a “no results” message.

---

## 8. Phased Additions

- **Weeks 7–9**: Optional lightweight KG for “related content” — after hybrid retrieval returns top-5, backend may query KG for same-topic content and append to context. Retrieval interface remains the same; only the **expert service** logic may add KG-based expansion.
- **Weeks 10–12**: Prerequisite check — expert may call KG for prerequisites and suggest content; retrieval interface unchanged.
- **Post-PoC**: GraphRAG / multi-hop over KG; retrieval may accept “expand via graph” option and return graph-augmented context. To be specified in a later doc.
