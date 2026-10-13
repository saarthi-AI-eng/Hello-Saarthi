# AI Part B — what was built (WBS v1.1 follow-up)

> **Superseded for the submission by `E:\SAARTHI\AI_WBS\AI_Team_WBS_v2_AsBuilt.md`** (11 Oct 2026): grounding rule, trained query classifier, Tier 0 check, citations, safety, feedback, MCQs, and updated measurements.

Scope: the AI-owned Part B directives that can run and be verified on the eval laptop.
Nothing here changes behaviour until you opt in, except four defaults:
**hints-first** for problem questions in the main chat, the **semantic cache**, **traces**,
and the **critic** now actually running after RAG answers (set `FAST_CHAT=1` to skip it on CPU).
All settings are listed (commented) at the end of `saarthi_backend/.env.example`.

## Status against Part B

| Lab ID / B item | Directive | Status | Where |
|---|---|---|---|
| 3.2.1 · B2 | Query classifier (cache / simple / complex) | **Done** — heuristic v0, optional `CLASSIFIER_MODE=llm` | `src/orchestrator/classifier.py` |
| 1.1.2 / 4.3 · B2 | Semantic cache, cosine ≥ 0.95, TTL 30 d | **Done** — scope-isolated, lexical guard, invalidated on re-index | `src/cache/semantic_cache.py` |
| 3.3.2 · B2 | Every answer cites a real chunk (regression) | **Done** — `citation` + `isolation` items in the gold set | `eval/gold.jsonl`, `eval/run_eval.py` |
| B2 | Freeze chunk metadata (course, page, timestamp, language) | **Done** — schema v1, written by all indexing paths | `src/retrieval/schema.py` |
| 3.1.1–3.1.2 · B3 | Hybrid + ColBERT + cross-encoder behind `retrieve()` | **Code done**: dense + BM25 + RRF live; ColBERT / rerank legs **skip** without GPU packages | `src/retrieval/` |
| 3.2.2 · B3 | Tiered routing local ↔ cloud by class + budget | **Done** — Tier 0/1/2; reads Product's budget flag | `src/utils/llm.py`, `src/utils/budget.py`, `src/orchestrator/policy.py` |
| 3.3.1 · B3 | Socratic default; direct after 3 stuck turns | **Done** — prompt pack for educator review; UI toggle "Hints first" | `src/orchestrator/socratic.py`, `src/prompts/socratic_pack.py`, `Chat.tsx` |
| 3.2.3+ · B3 | Weak-topic filter from 007 tables | **Done (read side)** — boosts, never filters | `saarthi_backend/service/weak_topics_service.py` |
| 5.1 · B3 | 50-question set + unattended script | **Done** — 50 items (16 objective `auto`, 34 `draft` for review) | `eval/` |
| B3 | `FAST_CHAT` to skip critic on CPU | **Done** | `src/orchestrator/graph.py` |
| 4.3 / 9.x · B1 | Traces: model, tier, tokens, cache, cite ids | **Done** — JSONL + summary script + admin metrics endpoint | `src/telemetry/traces.py`, `eval/trace_report.py`, `GET /api/admin/ai/metrics` |
| Phase 3 · B4 | Fine-tune on traces, self-hosted weights, VLM | **Not done** — needs labelled data + GPU (B4). Traces are the export. | — |
| B5 | Whisper, quota middleware, dashboards, OCR | **Not AI-owned** — untouched | — |

## How a chat turn works now (`/api/chat/stream`)

1. **Classify** the question → kind (`definition`, `conceptual`, `problem`, `followup`, `smalltalk`), complexity, wanted tier.
2. **Socratic stage** (main chat only): `hint` 1→2→3 for problem questions, `reveal` after 3 hints or when the student asks for the answer.
3. **Tier**: simple → Tier 1; complex → Tier 2 if `CLOUD_CHAT_MODEL` is set and the budget allows, else Tier 1. Router / critic / follow-up rewrite always stay on Tier 1.
4. **Tier 0 cache** lookup for cacheable turns (not follow-ups, not hint/reveal turns, not planning mode) inside the same scope (course / material / video / mode).
5. Answer (grounded document path or LangGraph), with weak topics boosting retrieval.
6. Write back to the cache, write one trace line.

The floating chatbot and document viewer (`/api/chat/message`) get steps 1, 3, 4 and 6 (no hints — they have no toggle).

## Things found while doing this (fixed)

- **`retrieved_chunks` was never filled**, so the critic always skipped with "no evidence" and the stream's excerpt-grounded path never ran. RAG experts now return their chunks.
- **The critic only ran after the video agent** — notes/books routes ended the graph. Now runs after all RAG agents unless `FAST_CHAT=1`.
- **`max_tokens` was ignored by Ollama**: `langchain-openai` 1.6 sends `max_completion_tokens`, which Ollama's OpenAI API ignores. The 1B router once generated 40,960 tokens (~7 min) before its fallback. `chat_llm()` now also sends `max_tokens` to non-OpenAI endpoints; router calls are capped (`ROUTER_MAX_TOKENS`). Worst routing call in the eval: 431 s → 2.4 s.
- **Cosine ≥ 0.95 alone is unsafe for STEM**: with `nomic-embed-text`, "Is x(t)=2x(t−1) causal?" vs "…2x(t+1)…" scores 0.98. The cache also requires the same math/number signature and no differing content words beyond neutral framing ("define", "explain", "what is").
- **Course-theory questions routed to `saarthi_agent`** (no knowledge base → uncited answer). The existing DSP heuristic now overrides that choice.
- **The 1B model ignored the hint rule** when the tutor prompt also said "teach fully, 250–500 words" and the user turn said "rewrite this draft". Hint turns now drop those lines and pass the draft as private reference.

## Measured on this laptop (Ollama, `llama3.2:1b` + `nomic-embed-text`, real course-1/2 indexes)

`python eval/run_eval.py --with-router`

| metric | value | gate |
|---|---|---|
| citation regression (unique marker + source) | 1.00 (6/6) | 1.00 |
| course isolation | 1.00 (4/4) | 1.00 |
| retrieval hit@3 | 0.90 | ≥ 0.80 |
| retrieval precision@3 | 0.57 | — |
| MRR | 0.83 | — |
| did it search | 1.00 | — |
| classifier | 1.00 (12/12) | ≥ 0.80 |
| routing (1B router) | 0.77 (10/13) | ≥ 0.70 |

Live `/api/chat/stream` checks: grounded answer 8.0 s → identical question from cache 2.1 s; no cache hit across courses;
Tier 2 (`llama3.1:8b` standing in for cloud) used for a complex question and dropped to Tier 1 once
`DAILY_CLOUD_TOKEN_BUDGET` was exhausted; one trace per turn with chunk ids and a hashed user id.

**These are AI regression gates, not the spec 1.5 KPIs.** 34 of the 50 gold items are `draft`
labels written by the AI team; per B2/B5 the 90% KPI is not claimed until educators/Product
review them (`--reviewed-only` scores only `auto` + `reviewed` items).

Known misses (left visible on purpose):
- "Fourier transform of a rectangular pulse" (ret-07, ret-15): the sinc chunk is outranked by
  generic Fourier chunks — the case the cross-encoder leg (`RETRIEVAL_RERANK=1`, GPU box) is for.
- Routing: eigenvalue question → books (want calculator), "exam in 2 days" → video (want saarthi),
  "latest 6G news" → saarthi (want web).

## Running it

```bash
# from Hello-Saarthi/, with Ollama (or the API) running
python eval/run_eval.py                 # ~1 min, no LLM calls except embeddings
python eval/run_eval.py --with-router   # + routing accuracy
python eval/run_eval.py --strict        # exit 1 on a regression (CI)
python eval/trace_report.py --days 14   # cache hit rate, tier mix, tokens/session, citations, latency
```

`GET /api/admin/ai/metrics` (admin bearer token) returns cache hit rate, today's tokens per tier,
and the tier configuration.

To try Tier 2 locally without a cloud key: `CLOUD_BASE_URL=http://localhost:11434/v1` and
`CLOUD_CHAT_MODEL=llama3.1:8b`.

## Needs other teams

- **Product**: daily caps → `DAILY_CLOUD_TOKEN_BUDGET` or the `CLOUD_BUDGET_FLAG_FILE` JSON; KPI dashboard from traces.
- **Educators**: review `src/prompts/socratic_pack.py` (two templates) and the `draft` items in `eval/gold.jsonl`.
- **Software**: write `saarthi_topic_mastery` (nothing writes it yet; quiz attempts below the passing score are used meanwhile).
- **Data / GPU box**: `pip install sentence-transformers` (+ `ragatouille` for ColBERT), set `RETRIEVAL_RERANK=1` / `RETRIEVAL_COLBERT=1`, then rerun the eval for precision@3.
