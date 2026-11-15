# Local (Self-Hosted Docker) Qdrant Pipeline Runbook

This document covers **only** the local, self-hosted Qdrant pipeline —
`QDRANT_BACKEND=local` (the default; nothing here needs changing from
what already works). For Qdrant Cloud, see `docs/CLOUD_QDRANT_PIPELINE.md`.
Local and Cloud are **independent databases** — this pipeline never
synchronizes them; switching `QDRANT_BACKEND` only changes which one the
next command talks to.

Every command below is a real command from this codebase (`scripts/*.py`'s
own `argparse` definitions), not generic boilerplate.

---

## 1. Prerequisites and Environment Setup

- Python 3.13, two virtual environments (`.venv`, `.venv-ocr`) — see
  `docs/COMPLETE_PIPELINE_SETUP.md` §5.2-5.3 for the one-time setup.
- Docker Desktop (Windows/macOS) or Docker Engine (Linux).
- `SAARTHI_KB_DATA_ROOT` set, pointing outside this repo.

## 2. Starting the Local Qdrant Docker Container

```powershell
docker compose -f docker-compose.kb.yml up -d
```
Starts `qdrant/qdrant:v1.12.4`, ports `6333` (HTTP/gRPC-over-HTTP) and
`6334` (gRPC), storage bind-mounted to
`<SAARTHI_KB_DATA_ROOT>\qdrant\storage`.

## 3. Verifying Qdrant Is Running

```powershell
curl http://localhost:6333/collections
```
A fresh instance returns `{"result":{"collections":[]},...}`.

## 4. Configuring `.env.kb` for Local Mode

```powershell
copy .env.kb.example .env.kb
```
Set `SAARTHI_KB_DATA_ROOT`. Leave `QDRANT_BACKEND=local` (the default —
you can omit it entirely) and `QDRANT_URL=http://localhost:6333`,
`QDRANT_API_KEY=` blank. `QDRANT_CLOUD_URL`/`QDRANT_CLOUD_API_KEY` are
irrelevant in local mode and can stay empty.

## 5. Activating the Correct Python Environment

```powershell
..\.venv\Scripts\Activate.ps1
```
(Ingestion steps below use `.venv-ocr`'s own `python.exe` explicitly
instead — see why in `docs/COMPLETE_PIPELINE_SETUP.md` §5.3.)

## 6. Running OCR and Video Ingestion

```powershell
..\.venv-ocr\Scripts\python.exe -m scripts.ingest_notes --output "<DATA_ROOT>\source_content\ocr"
..\.venv-ocr\Scripts\python.exe -m scripts.ingest_videos --output "<DATA_ROOT>\source_content\transcripts"
```
Or let the orchestrator run both for you (§9).

## 7. Running Auto-QA

```powershell
python -m scripts.run_content_qa
```
Backend-agnostic — doesn't touch Qdrant at all, scores OCR/transcript
JSONL in place. Identical regardless of which Qdrant backend you'll
upsert into later.

## 8. Normalization and Chunking

```powershell
python -m scripts.normalize_content_kb          # default: approved-only
python -m scripts.normalize_content_kb --allow-pending   # also include pending
python -m scripts.chunk_content_kb
```

## 9. BGE-M3 Embedding Generation

```powershell
python -m scripts.embed_chunks_kb
```
Or the single-command orchestrator for steps 6-12 together:
```powershell
python -m scripts.build_kb_qdrant --run-ingestion --allow-pending
```
This always talks to whichever backend `QDRANT_BACKEND` currently
resolves to (local, by default) — explicit, not implicit; check
`.env.kb` if you're unsure which one is active.

## 10. Upserting Into Local Qdrant

Done automatically inside `build_kb_qdrant.py` (step 9's command) via
`src/knowledge_base/qdrant_store.py::QdrantKBStore.upsert_chunks()` —
idempotent, content-hash-gated, deterministic point IDs. No separate
standalone "upsert" script exists; run `build_kb_qdrant.py` with
`--skip-normalize --skip-chunk` if you only need to re-upsert from an
existing `chunks.jsonl`/`embeddings.jsonl`.

## 11. Validating the Local Collection

```powershell
python -m scripts.validate_kb_qdrant
```
Reports chunk/embedding/Qdrant-point counts, duplicate IDs, missing
metadata — writes `<DATA_ROOT>\knowledge_base\reports\latest_validation_report.json`.

## 12. Exporting and Backing Up Local Data

```powershell
python -m scripts.export_kb_qdrant --qdrant-snapshot
```
Bundles `chunks.jsonl` + schema + manifest + validation report, and
triggers a real server-side Qdrant snapshot (downloaded separately via
the `curl` command the script prints — see
`docs/COMPLETE_PIPELINE_SETUP.md` §5.8 for verifying it's a real,
readable archive, not just trusting exit code 0).

## 13. Stopping and Restarting Docker

```powershell
docker compose -f docker-compose.kb.yml stop     # stop, keep the container+data
docker compose -f docker-compose.kb.yml up -d    # restart, same bind-mounted storage
docker compose -f docker-compose.kb.yml down      # remove the container (storage on disk is untouched — it's bind-mounted, not a container volume)
```

## 14. Troubleshooting Common Local Pipeline Errors

| Symptom | Fix |
|---|---|
| `ResponseHandlingException: ... actively refused it` / connection refused on `localhost:6333` | Docker Desktop itself isn't running, or the container isn't up — `docker compose -f docker-compose.kb.yml up -d`, verify with step 3. |
| Normalization produces 0 docs | Check `qa_status` — see `docs/KB_PIPELINE_SETUP.md` §17's callout; `--allow-pending` or check `<DATA_ROOT>\qa_reports\latest_qa_report.jsonl`. |
| `Qdrant point count does not match unique chunk count` | Stale points from a prior schema version/build — see `docs/COMPLETE_PIPELINE_SETUP.md` §5.8's safe cleanup procedure. |
| `qdrant-client` version/server mismatch warning | Harmless for this pipeline's calls; pin `qdrant-client<1.13` or bump `docker-compose.kb.yml`'s image tag if you want it silenced. |
| OCR/GPU errors | See `docs/COMPLETE_PIPELINE_SETUP.md` §5.4/§5.12 — not Qdrant-related. |

---

**Local and Cloud are independent databases.** Running any of the
commands above never touches Qdrant Cloud, and nothing here requires
`QDRANT_CLOUD_URL`/`QDRANT_CLOUD_API_KEY` to be set at all.
