# BGE-M3 + Qdrant Knowledge Base Pipeline — Setup Guide

A separate, self-hosted knowledge-base pipeline alongside the existing
OpenAI + FAISS system (`scripts/build_knowledge_base.py`,
`src/tools/kb_ops.py`) — built deliberately with **no paid API** (BGE-M3,
local) and **no cloud account requirement** (Qdrant OSS, self-hosted).
This guide is practical and reflects only commands/options that actually
exist in this repository.

## 1. Architecture Overview

```
RAW CONTENT (PDF/video — already handled by ingest_notes.py / ingest_videos.py)
    |
    v
OCR OUTPUT / TRANSCRIPTS (ContentRecord JSONL — unchanged, existing format)
    |
    v
NORMALIZATION          scripts/normalize_content_kb.py   -> normalized_docs.jsonl
    |
    v
CHUNKING               scripts/chunk_content_kb.py       -> chunks.jsonl
    |
    v
EMBEDDING (BGE-M3)     scripts/embed_chunks_kb.py         -> embeddings.jsonl
    |
    v
QDRANT UPSERT          (inside build_kb_qdrant.py)        -> saarthi_knowledge_base_v1
    |
    v
VALIDATION             scripts/validate_kb_qdrant.py      -> validation_report.json
    |
    v
EXPORT / BACKUP        scripts/export_kb_qdrant.py        -> export_<timestamp>/
```

Single-command orchestration: `scripts/build_kb_qdrant.py` runs
normalize → chunk → embed → upsert and writes a combined manifest. Every
stage is also independently runnable.

## 2. Complete Pipeline Block Diagram

See §1 — this *is* the actual pipeline, not an idealized one. Reusable
logic lives in `src/knowledge_base/` (`config.py`, `schema.py`,
`chunker.py`, `embedder.py`, `qdrant_store.py`); each `scripts/*_kb.py`
file is a thin CLI wrapper around it.

## 3. Prerequisites

- Python (same interpreter as the rest of this repo — 3.12 or 3.13, see
  `docs/PIPELINE_SETUP_AND_USAGE.md` §1).
- The existing OCR/video pipeline already set up and already producing
  `ContentRecord` JSONL (this pipeline *consumes* that output — it does
  not run OCR or transcription itself).
- Docker Desktop (for local Qdrant) — see §9.
- ~3GB free disk for the BGE-M3 model cache, plus whatever your actual
  chunk/embedding/Qdrant data needs (highly dataset-size-dependent;
  budget generously, e.g. 10GB+, for a real course's worth of content).

## 4. Hardware Requirements

- Benchmarked on this project's own RTX 4060 Laptop GPU (8GB VRAM) — the
  default `embedding_batch_size: 16` is conservative for that card.
- CPU-only works — slower, never crashes, never silently falls back to
  a degraded behavior without logging it (see §31).
- No minimum RAM measured specifically for this new pipeline; the
  existing OCR pipeline was developed on 16.8GB RAM, and BGE-M3 itself
  needs a few GB during inference.

## 5. Python Version

Same interpreter as the OCR pipeline. No separate virtual environment is
required — `requirements-kb.txt` is additive to what's already installed.

## 6. Dependency Installation

```powershell
pip install -r requirements-kb.txt
```
This installs `qdrant-client`, `tqdm`, `tiktoken`, `pyyaml`, and
`FlagEmbedding` (the BGE-M3 wrapper — downloads model weights on first
use, not at install time; see §8). It does **not** install or upgrade
`torch` — this project already depends on `torch==2.10.0` via
`saarthi_backend/requirements.txt`; FlagEmbedding uses whatever build is
already present (CPU or CUDA).

## 7. CUDA/GPU Setup and Verification

Same GPU as the OCR pipeline uses (see
`docs/PIPELINE_SETUP_AND_USAGE.md` §3) — if PaddleOCR already reports
`device='gpu'` there, embedding can use the same card. Verify PyTorch
itself sees it (BGE-M3 runs on PyTorch, not PaddlePaddle):
```powershell
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```
If `False`: the installed `torch==2.10.0` wheel may be the CPU-only
build (this was confirmed to be the case for this project's own
development environment earlier this session — see
`docs/analogfilters-latest-math-ocr-evaluation.md` for how that was
diagnosed for a different component). Embedding will then run on CPU
automatically (`embedding_device: auto` in `configs/kb_pipeline.yaml`) —
slower, but functional; this is expected, not a bug to chase before your
first real run.

Force a specific device:
```powershell
python -m scripts.embed_chunks_kb --device cpu
python -m scripts.build_kb_qdrant --device cpu
```

## 8. BGE-M3 Model Download and Cache Configuration

**Manual step — not done automatically during implementation.** The
first time you run `scripts.embed_chunks_kb` (directly or via
`build_kb_qdrant`), `FlagEmbedding` downloads `BAAI/bge-m3` (~2.2GB) from
Hugging Face to `<SAARTHI_KB_DATA_ROOT>\models` (configurable via
`embedding_model`/the `models_cache_dir` property — see
`src/knowledge_base/config.py`). This requires:
- Network access to huggingface.co.
- ~2.2GB free disk at that cache path.

No Hugging Face account or token is needed for this public model. If
the download fails partway, re-running the same command resumes/retries
via `huggingface_hub`'s own cache (nothing in this pipeline needs to
handle that itself).

## 9. Docker Desktop Installation and Startup

**Manual step.** Docker is already installed on this machine
(`docker --version` reported `29.5.3` when checked). You must:
1. Start Docker Desktop (if not already running).
2. Verify: `docker ps` should succeed without a connection error.

## 10. Qdrant Local Setup

```powershell
$env:SAARTHI_KB_DATA_ROOT = "E:\SaarthiData"
docker compose -f docker-compose.kb.yml up -d
```
Verify it's up:
```powershell
curl http://localhost:6333/collections
```
Should return `{"result":{"collections":[]},...}` on a fresh instance.

## 10b. Qdrant Cloud (Optional Dual-Backend Support)

Every script in this pipeline (`build_kb_qdrant.py`, `validate_kb_qdrant.py`,
`export_kb_qdrant.py`) goes through one centralized client factory
(`QdrantKBStore._ensure_client()` in `src/knowledge_base/qdrant_store.py`),
which resolves to either backend based on `QDRANT_BACKEND` (`local` —
default, this section — or `cloud`). **Local remains fully independent and
unaffected** — nothing here changes local behavior unless you explicitly
set `QDRANT_BACKEND=cloud`. Switching the backend does **not** migrate
data; local and Cloud are separate databases. Full setup, a side-by-side
comparison table, and the explicit migration utility
(`scripts/migrate_qdrant_local_to_cloud.py`) are in the two dedicated
runbooks: `docs/LOCAL_QDRANT_PIPELINE.md` and
`docs/CLOUD_QDRANT_PIPELINE.md` — not duplicated here.

## 11. Qdrant Persistent Storage Configuration

`docker-compose.kb.yml` bind-mounts
`${SAARTHI_KB_DATA_ROOT}\qdrant\storage` into the container — **not** a
Docker named volume, specifically so the data is visible and backupable
outside Docker, and lives under your configured data root rather than
Docker's own internal volume storage. Do not point
`SAARTHI_KB_DATA_ROOT` (or that subpath specifically) at a OneDrive/
Google-Drive-synced folder — Qdrant's storage engine is not designed for
concurrent file-sync access.

## 12. Data Directory Setup

**Manual step.** Create (or let the pipeline create — `ensure_directories()`
runs automatically at the start of every stage) your data root:
```powershell
mkdir E:\SaarthiData
```
Expected structure once populated (see `src/knowledge_base/config.py`'s
`KBConfig` properties for the authoritative list):
```
E:\SaarthiData\
  source_content\ocr\          <- copy/point your existing OCR JSONL output here
  source_content\transcripts\  <- copy/point your existing transcript JSONL output here
  knowledge_base\normalized\
  knowledge_base\chunks\
  knowledge_base\embeddings\
  knowledge_base\manifests\
  knowledge_base\exports\
  knowledge_base\reports\
  models\                       <- BGE-M3 cache
  qdrant\storage\
  logs\
```

## 13. Environment Variable Configuration

Copy `.env.kb.example` to `.env.kb` (or export the variables directly):
```powershell
copy .env.kb.example .env.kb
```
Required: `SAARTHI_KB_DATA_ROOT`. Optional: `QDRANT_URL`,
`QDRANT_API_KEY` (leave blank for local dev), `QDRANT_COLLECTION`,
`SAARTHI_KB_EMBED_DEVICE`, `SAARTHI_KB_EMBED_BATCH_SIZE`. See
`src/knowledge_base/config.py`'s `_ENV_OVERRIDES` for the authoritative
mapping. **Never commit `.env.kb`** — it's for your local values only.

## 14. Input File Organization

Point `source_content/ocr` and `source_content/transcripts` at (or copy
into them) the existing output of:
```powershell
python -m scripts.ingest_notes --output "E:\SaarthiData\source_content\ocr"
python -m scripts.ingest_videos --output "E:\SaarthiData\source_content\transcripts"
```
(Exact commands for those two pipelines: see
`docs/PIPELINE_SETUP_AND_USAGE.md` §4-§5 — unchanged by this task.)
Both now show a `tqdm` per-file progress bar.

## 15-16. Running PDF/Video Ingestion

`build_kb_qdrant.py` can also run both ingestion stages for you first,
writing straight into this config's `ocr_output_dir`/`transcripts_dir`:
```powershell
python -m scripts.build_kb_qdrant --run-ingestion --allow-pending
```
This is the single command that covers the whole chain: raw PDFs/videos
in `data/raw/notes` and `data/raw/videos` → OCR/transcription → KB
build. Omit `--run-ingestion` to reuse ingestion output you already
have, as before.

**Ingestion always runs as a separate subprocess**, never in-process —
see §13b for why, and the one-time `.venv-ocr` setup it needs if you
want `SAARTHI_HANDWRITING_OCR=paddleocr`'s improved math/handwriting OCR
to actually take effect.

## 13b. Enabling the Improved Math/Handwriting OCR (PaddleOCR)

`scripts/ingest_notes.py` has three opt-in environment variables for
better-than-Tesseract OCR on handwritten/mathematical pages:
`SAARTHI_HANDWRITING_OCR=paddleocr`, `SAARTHI_REGION_ANALYSIS=1`,
`SAARTHI_MATH_ANALYSIS=1`. **Without them, every page is Tesseract-only**
— no code difference from `Hello-Saarthi`, just these flags defaulting
off.

**Do not set `SAARTHI_HANDWRITING_OCR=paddleocr` and run ingestion in the
same Python process as BGE-M3 embedding.** Confirmed by direct testing on
this project's machine: `paddlepaddle-gpu` and a CUDA-enabled `torch`
(this repo's main venv needs the latter for GPU BGE-M3 embedding) each
bundle their own private `cudnn_cnn64_9.dll`; `paddleocr`'s own dependency
chain (`paddlex` → `modelscope`) unconditionally imports `torch`
internally regardless of whether OCR needs it, so loading paddle and a
CUDA torch together in one process crashes with `OSError: [WinError 127]`
— reproduced with both import orders. `ingest_notes.py`'s own fallback
catches this (`except Exception`, logs a warning, keeps the Tesseract
result) so it never hard-crashes, but it also means the improvement
silently never activates if you just set the env var and run everything
in one process.

**Fix: a dedicated `.venv-ocr` virtual environment, isolated from the
main venv's CUDA torch.** One-time setup:
```powershell
cd E:\Saarthi
python -m venv .venv-ocr
.venv-ocr\Scripts\pip install -r Hello-Saarthi-26\requirements-ocr-venv.txt
.venv-ocr\Scripts\pip install https://paddle-whl.cdn.bcebos.com/stable/cu126/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp313-cp313-win_amd64.whl
```
(Match the wheel's `cuXXX`/`cpXXX` to your CUDA driver and Python version
from https://www.paddlepaddle.org.cn/packages/stable/ if different; see
`requirements-ocr-venv.txt`'s header comment for the CPU-only alternative
and the full rationale.) Verified end to end on this project's RTX 4060:
paddle correctly reports `is_compiled_with_cuda()==True`,
`device_count()==1`, and a real `PaddleOCR(device="gpu")` instance runs a
prediction successfully in this isolated venv (one harmless `cuDNN 9.9 vs
9.5` compatibility warning logged, not fatal).

`python -m scripts.build_kb_qdrant --run-ingestion` auto-detects a
sibling `E:\Saarthi\.venv-ocr` and runs `ingest_notes`/`ingest_videos`
through it automatically (as a subprocess — see the comment on
`_ocr_python_executable()` in `build_kb_qdrant.py`). Override with
`SAARTHI_OCR_VENV_PYTHON=<path to python.exe>` if yours lives elsewhere.
Running `ingest_notes.py`/`ingest_videos.py` directly instead of through
`build_kb_qdrant`? Invoke them with `.venv-ocr`'s own python the same way:
```powershell
E:\Saarthi\.venv-ocr\Scripts\python.exe -m scripts.ingest_notes --output "E:\SaarthiData\source_content\ocr"
```
Then set the env vars and run (main venv or `.venv-ocr` — only the
ingestion step itself needs isolation):
```powershell
$env:SAARTHI_HANDWRITING_OCR = "paddleocr"
$env:SAARTHI_REGION_ANALYSIS = "1"
$env:SAARTHI_MATH_ANALYSIS = "1"
python -m scripts.build_kb_qdrant --run-ingestion --allow-pending
```
Verified this session on this project's real small sample (3 PDFs, 1
video, not the full dataset): ran successfully end to end with these
three flags set, no `WinError 127`, `ingestion.notes_exit_code=0`.

## 17. Running Normalization

```powershell
python -m scripts.normalize_content_kb --config configs/kb_pipeline.yaml
python -m scripts.normalize_content_kb --allow-pending   # include qa_status=="pending" records too (dev only)
```
**Important — `qa_status` gate:** every record OCR/transcription
produces starts as `qa_status="pending"` (this project has no manual
QA-review step that promotes records to `"approved"`; it's the same
convention the older `scripts/build_knowledge_base.py` uses). Without
`--allow-pending`, normalization silently drops every `"pending"`
record — on a fresh ingestion run this means **all** input is filtered
out, producing 0 normalized docs, 0 chunks, 0 embeddings, 0 Qdrant
points, with every stage still reporting "success". Until a review
tool exists, pass `--allow-pending` on every real run (it's the normal
case here, not just a dev convenience).

## 18. Running Chunking

```powershell
python -m scripts.chunk_content_kb
python -m scripts.chunk_content_kb --semantic-boundaries   # also use BGE-M3 to refine boundaries (loads the model; slower)
```

## 19. Running Embedding Generation

```powershell
python -m scripts.embed_chunks_kb
python -m scripts.embed_chunks_kb --resume
python -m scripts.embed_chunks_kb --device cpu --batch-size 8
```

## 20. Starting Qdrant

See §10.

## 21. Running the Complete Pipeline

```powershell
python -m scripts.build_kb_qdrant --config configs/kb_pipeline.yaml --allow-pending
```
Add `--run-ingestion` to also OCR/transcribe raw input first (§15-16).
`--allow-pending` is required today — see §17's callout; dropping it
silently empties every downstream stage.

After every run, a diagnostics block is logged with real stage counts:
```text
========== KB PIPELINE DIAGNOSTICS ==========
Normalization: input files=3  normalized docs=39  failed files=0
Chunking: input docs=39  chunks generated=13
Embedding: input chunks=13  embedded=13 (new=13, cached=0)  failed=0  device=cuda
Qdrant: chunks total=13  uploaded=13  skipped(unchanged)=0  skipped(no vector)=0
=============================================
```
If any stage that received input produces zero output, the pipeline
**raises an error** (after still writing the manifest, for debugging)
instead of reporting success — e.g. normalization receiving N files but
producing 0 docs, chunking receiving N docs but producing 0 chunks,
embedding/upload receiving N chunks but writing/uploading 0. It never
silently reports a build as complete when nothing was actually indexed.

## 22. Running a Small Sample

```powershell
python -m scripts.build_kb_qdrant --sample 2 --allow-pending
```
`--sample N` limits normalization to the first N input JSONL files
found — the cheapest way to test the whole chain end-to-end before
committing to a full run.

## 23. Running the Full Dataset

```powershell
python -m scripts.build_kb_qdrant --allow-pending
```
Verified this session against the small amount of real OCR/transcript
output already present under `E:\SaarthiData` (3 input files, 39
normalized docs, 13 chunks, 13 embeddings, 13 Qdrant points, 0 errors)
— not the full raw dataset. See §33's test summary for the synthetic
unit/integration coverage.

## 24. Resuming Interrupted Processing

```powershell
python -m scripts.build_kb_qdrant --resume
```
Resumes the embedding stage from its checkpoint
(`embeddings.checkpoint.jsonl`) — chunks already embedded are not
re-embedded. Normalization/chunking are cheap enough to always re-run in
full; only embedding (the expensive, GPU-bound stage) checkpoints.

## 25. Incremental Processing

Add new OCR/transcript JSONL files to `source_content/ocr` or
`/transcripts`, then re-run `build_kb_qdrant` (no flag needed) —
normalization/chunking re-process everything (cheap, text-only); both
the **embedding** stage (via `embeddings.checkpoint.jsonl`, keyed by
chunk_id + content_hash) and the **Qdrant upsert** stage (via each
point's stored `content_hash` payload field) skip any chunk whose
content hasn't changed since the last run — this is the unconditional
default, not something a flag has to enable. A chunk whose `chunk_id` is
unchanged but whose *text* changed is correctly detected (different
content_hash) and re-embedded/re-uploaded; a chunk that's byte-identical
to last run is skipped in both stages. `--force-rebuild` bypasses this
entirely when you need to (e.g. an embedding model change — see §27).

## 26. Rebuilding the KB from Saved Chunks

If you still have `chunks.jsonl` but want to re-embed/re-upload (e.g.
after a Qdrant collection was deleted):
```powershell
python -m scripts.build_kb_qdrant --skip-normalize --skip-chunk --force-rebuild
```

## 27. Rebuilding Embeddings When the Model Changes

Bump `chunk_schema_version` in `configs/kb_pipeline.yaml` if the chunk
*shape* changed; just change `embedding_model`/`embedding_revision` if
only the model changed, then:
```powershell
python -m scripts.build_kb_qdrant --skip-normalize --skip-chunk --force-rebuild
```
`--force-rebuild` re-embeds and re-upserts every chunk regardless of
`content_hash`, which is exactly what's needed when the *embedding*
(not the chunk content) is what changed.

## 28. Recreating the Qdrant Collection

Not currently exposed as a CLI flag (documented limitation — see §32).
Today: delete the collection manually, then re-run.
```powershell
curl -X DELETE http://localhost:6333/collections/saarthi_knowledge_base_v1
python -m scripts.build_kb_qdrant --skip-normalize --skip-chunk --force-rebuild
```

## 29. Validating the KB

```powershell
python -m scripts.validate_kb_qdrant
```
Writes `knowledge_base/reports/validation_report_<timestamp>.json` and
`.../latest_validation_report.json`. Checks chunk counts/sizes,
duplicate IDs, OCR-review-flag counts, embedding coverage, embedding
dimension consistency, and Qdrant point-count match. **Does not evaluate
retrieval quality** — that's explicitly out of scope, a separate AI-team
responsibility.

## 30. Exporting and Backing Up the KB

```powershell
python -m scripts.export_kb_qdrant
python -m scripts.export_kb_qdrant --qdrant-snapshot
```
Writes `chunks.jsonl` + `chunk_schema.txt` + `manifest.json` +
`validation_report.json` + `config_snapshot.json` to a timestamped
`knowledge_base/exports/export_<timestamp>/` directory. Embeddings are
**not** included in this bundle (they're deterministically regenerable
from `chunks.jsonl` + the pinned `embedding_model`/`embedding_revision`
— see §27); `--qdrant-snapshot` additionally triggers a real Qdrant-side
snapshot (the actual vector backup), whose download command is printed
when it succeeds.

## 31. Restoring the KB on Another Device

1. Clone the repo, install `requirements-kb.txt` (§6).
2. Copy an `export_<timestamp>/` directory to the new machine.
3. Set `SAARTHI_KB_DATA_ROOT` on the new machine; put `chunks.jsonl`
   under `<root>/knowledge_base/chunks/`.
4. Start Qdrant (§9-10) on the new machine.
5. If you have a Qdrant snapshot, restore it via Qdrant's own
   snapshot-restore API; otherwise:
   ```powershell
   python -m scripts.build_kb_qdrant --skip-normalize --skip-chunk --force-rebuild
   ```
   This re-embeds from `chunks.jsonl` and re-uploads — not
   bit-for-bit-identical to the original embeddings if the new machine's
   GPU/CPU numerics differ even slightly (expected; do not assume exact
   reproducibility across different hardware — see §32), but functionally
   equivalent for retrieval.

## 32. Giving the AI Team Access

**Mode A — local development** (what this guide sets up): Qdrant at
`http://localhost:6333` on your laptop, persisted to
`SAARTHI_KB_DATA_ROOT\qdrant\storage`. If your laptop is off, the
service is unreachable, but the data on disk is safe.

**Mode B — shared team server** (not set up this session — a future
step): Qdrant on an always-on machine, team members connect via that
machine's reachable address. Recommended: a private VPN (e.g.
[Tailscale](https://tailscale.com/)) rather than exposing Qdrant
directly to the public internet. The AI team needs, at minimum:
`QDRANT_URL` (the server's Tailscale/VPN address), `QDRANT_COLLECTION`
(`saarthi_knowledge_base_v1`), and the payload schema (`chunk_id`,
`source_id`, `source_type`, `text`, `course`, `unit`, `topic`, `page`/
`page_range`, `start_time`/`end_time`, `ocr_quality`,
`ocr_review_flagged`, `has_equation`, `equation_review_flagged`,
`content_hash`, `chunk_schema_version`, `token_count` — see
`src/knowledge_base/schema.py:Chunk.to_payload`). **Never expose an
unauthenticated Qdrant instance to the public internet** — if Mode B is
set up, configure `QDRANT_API_KEY` and firewall rules at that time; this
was not needed for local Mode A and so was not implemented/tested this
session.

## 33. Troubleshooting

- **"qdrant-client is not installed" / "FlagEmbedding is not
  installed"** — `pip install -r requirements-kb.txt`.
- **`ValueError: No KB data root configured`** — set
  `SAARTHI_KB_DATA_ROOT` or `data_root` in `configs/kb_pipeline.yaml`.
- **Qdrant connection refused** — Docker Desktop not running, or
  `docker compose -f docker-compose.kb.yml up -d` not yet run (§9-10).
- **CUDA out of memory during embedding** — the embedder halves its
  batch size and retries once automatically; if it still fails, lower
  `embedding_batch_size` in the config or pass `--batch-size 4`.
- **BGE-M3 download fails/stalls** — check network access to
  huggingface.co; re-running the same command resumes via
  `huggingface_hub`'s own cache.
- **Validation report shows `chunks_missing_embedding > 0`** — the
  embedding stage hasn't fully completed; re-run
  `python -m scripts.embed_chunks_kb --resume`.
- **Qdrant point count doesn't match chunk count** — expected if you
  changed `chunk_schema_version` and haven't deleted the old collection
  (§28), or if the upsert stage hasn't finished.
- **Normalization/chunking/embedding all report 0, pipeline still says
  "complete"** — this was a real bug, now fixed: `normalize_content_kb`
  found input files but 0 docs, every downstream stage correctly
  propagated the 0, and the old `build_kb_qdrant.py` still reported
  success. Root cause: every OCR/transcript record starts
  `qa_status="pending"` (no QA-review tool exists yet in this project),
  and normalization drops `"pending"` records unless `--allow-pending`
  is passed (§17). `build_kb_qdrant.py` now (a) logs a `KB PIPELINE
  DIAGNOSTICS` block with real per-stage counts after every run, and (b)
  raises an error instead of reporting success whenever a stage received
  nonzero input but produced zero output. Fix: always pass
  `--allow-pending` until a review step exists (§21).
- **Video ingestion fails with `open() got an unexpected keyword argument
  'metadata_errors'`** — PyAV ≥19 removed the `metadata_errors` kwarg
  `faster-whisper`'s own `audio.py` still passes to `av.open()`. Fixed by
  pinning `av<19` in `requirements-content-pipeline.txt` and
  `requirements-ocr-venv.txt`; if you already have a broken `av`
  installed, `pip install "av==18.1.0"` in the affected venv.
- **`qdrant-client` version/server mismatch warning** — this project's
  `requirements-kb.txt` pins `qdrant-client>=1.7.0` (open-ended) while
  `docker-compose.kb.yml` runs server image `qdrant/qdrant:v1.12.4`; a
  newly-installed client can end up several minor versions ahead and log
  a compatibility warning. Harmless for the basic upsert/count/search
  calls this pipeline uses, but pin the client
  (`qdrant-client>=1.7.0,<1.13`) or bump the server image if you want the
  warning gone.

## Security Considerations

- `QDRANT_API_KEY` is read from an environment variable only, never
  hardcoded, and never logged (confirmed: `src/knowledge_base/qdrant_store.py`
  never prints `self.config.qdrant_api_key`).
- No OpenAI key or any paid-API credential is required anywhere in this
  pipeline.
- `.env.kb` is for local values only — `.env.kb.example` (committed)
  contains no real credentials, only placeholders/comments.

## GitHub Data Exclusion

Nothing this pipeline generates needs a `.gitignore` entry *for this
pipeline specifically*, because every generated artifact lives under
`SAARTHI_KB_DATA_ROOT`, which is configured to be **outside this Git
repository entirely** (e.g. `E:\SaarthiData`, not `E:\Saarthi\Hello-
Saarthi-26\...`) — there is structurally nothing for Git to accidentally
pick up. Only `configs/kb_pipeline.yaml`, `requirements-kb.txt`,
`.env.kb.example`, `docker-compose.kb.yml`, the `src/knowledge_base/` and
`scripts/*_kb.py` source files, and `tests/kb/` are tracked — confirmed
via `git status` showing exactly these files as new/changed, nothing
under a data directory.

## Remaining Limitations (stated plainly)

- No CLI flag to recreate/drop the Qdrant collection (§28) — a manual
  `curl -X DELETE` step today.
- Qdrant Cloud restore (from a downloaded snapshot) isn't wrapped by a
  script — Qdrant's own snapshot-recover HTTP API, documented in
  `docs/CLOUD_QDRANT_PIPELINE.md`.
- Heading/section hierarchy extraction (`Chunk.heading`) is not yet
  implemented — always `None` currently; the field exists in the schema
  for when it is.
- Cross-hardware embedding reproducibility is not bit-for-bit guaranteed
  (§31) — expected floating-point numerical variation across different
  GPUs/CPUs, not a bug.
- This guide and the pipeline were validated against **synthetic test
  fixtures (253 tests, including a full
  normalize→chunk→embed→upsert→validate→export integration test with a
  mocked embedding model and an in-memory Qdrant client), plus one real
  run against the small amount of real OCR/transcript output already
  present under `E:\SaarthiData`** (3 input files → 39 docs → 13 chunks →
  13 real BGE-M3 embeddings on CUDA → 13 live Qdrant points, validated
  clean) — **not against the full raw dataset**, per the explicit
  instruction not to process it in bulk during implementation. Running it on your real content is
  the next, manual step, described throughout this guide.
