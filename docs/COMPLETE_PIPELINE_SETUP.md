# Complete Pipeline Setup — Raw PDFs/Videos to a Validated Qdrant KB

This is the single, start-to-finish guide for recreating the Saarthi content
ingestion + automated QA + BGE-M3/Qdrant knowledge-base pipeline on a new
computer, from a fresh `git clone` to a validated, queryable Qdrant
collection. Every command below is a real command this codebase implements
— nothing here is generic boilerplate.

It supersedes nothing: `docs/KB_PIPELINE_SETUP.md` (BGE-M3/Qdrant internals)
and `docs/PIPELINE_SETUP_AND_USAGE.md` (OCR/transcription internals) are
still the deeper references for their respective stages. This document is
the one that walks the whole chain end to end and gets a new machine from
zero to a working pipeline.

Everything in this guide was exercised on this project's own development
machine (Windows 11, RTX 4060 Laptop GPU) during the session that wrote it.
Linux commands are given as the documented equivalent but were **not**
run on Linux this session — called out explicitly wherever that applies.

---

## 5.1 Architecture

```
 RAW PDFs (data/raw/notes/)         RAW VIDEOS (data/raw/videos/)
        |                                    |
        v                                    v
 scripts/ingest_notes.py            scripts/ingest_videos.py
 (Tesseract + optional                (faster-whisper, or
  PaddleOCR GPU fallback,              .vtt/.srt sidecar)
  math/region analysis)
        |                                    |
        +------------------+-----------------+
                           |
                           v
              source_content/ocr/*.jsonl
              source_content/transcripts/*.jsonl
                  (ContentRecord JSONL, qa_status=pending)
                           |
                           v
             scripts/run_content_qa.py   (src/content_qa/)
       page/segment-level scoring -> qa_status: approved | pending | rejected
                           |
                           v
            qa_status=pending ---> /qa-review dashboard (qa_reviewer role)
            |                      accept -> approved | reject -> rejected
            |                      reprocess -> reprocess_requested
            v                      (writes back to the SAME JSONL file —
      qa_status=approved            picked up by the next run below)
            |
                           v
             scripts/normalize_content_kb.py
         (default: only approved; --allow-pending also includes pending;
          rejected/reprocess_requested are NEVER included, with or
          without --allow-pending)
                           |
                           v
                    NormalizedDoc JSONL
                           |
                           v
             scripts/chunk_content_kb.py   (src/knowledge_base/chunker.py)
     structural + optional semantic-boundary + size-aware chunking
                           |
                           v
                      chunks.jsonl
                           |
                           v
             scripts/embed_chunks_kb.py   (src/knowledge_base/embedder.py)
          BAAI/bge-m3, 1024-dim dense vectors, content-hash-aware
                           |
                           v
                   embeddings.jsonl
                           |
                           v
          src/knowledge_base/qdrant_store.py  -> Qdrant upsert
       (deterministic chunk_id -> point UUID, idempotent, content-hash gated)
                           |
                           v
             scripts/validate_kb_qdrant.py  +  scripts/export_kb_qdrant.py
```

`scripts/build_kb_qdrant.py` is the single orchestrator that chains
ingestion (optional) -> QA -> normalize -> chunk -> embed -> Qdrant upsert
-> a diagnostics block -> a manifest, in one command (§5.9).

**Two virtual environments, by design** (§5.3/5.4 explain why): `.venv`
(main — FastAPI backend, BGE-M3/torch with CUDA, Qdrant client) and
`.venv-ocr` (PaddleOCR GPU + its own `paddle`, isolated from the main
venv's CUDA torch).

---

## 5.2 Prerequisites

| Requirement | Needed for | Notes |
|---|---|---|
| Python 3.13 | everything | This project was built/tested on 3.13.2. The `paddlepaddle-gpu` wheel in §5.4 is a `cp313` build — a different Python version needs a different wheel URL. |
| Git | cloning | — |
| Docker Desktop (Windows/macOS) or Docker Engine (Linux) | Qdrant | Self-hosted Qdrant OSS via `docker-compose.kb.yml`. No Qdrant Cloud account needed or used. |
| NVIDIA GPU + driver | **optional** — speeds up BGE-M3 embedding and PaddleOCR | Both fall back to CPU automatically (device auto-detected at runtime, never hardcoded) if no CUDA-enabled GPU is found. CPU-only is fully supported, just slower. |
| ~10GB free disk | model weights + a small KB | BGE-M3 (~2.2GB), PaddleOCR models (~100MB), faster-whisper `base` model (~150MB), plus whatever you ingest. |
| Internet access | first run only | Downloads model weights (Hugging Face, PaddleX's own model hub) and PyPI/wheel packages. Fully offline after that (models cache locally — §5.5). |

GPU acceleration is **optional everywhere** in this pipeline — every
device selection in this codebase (`detect_embedding_device()` in
`src/knowledge_base/embedder.py`, `_detect_paddleocr_device()` in
`scripts/ingest_notes.py`) checks the actual framework's CUDA API at
runtime and falls back to CPU with a log message, never a crash. Nothing
assumes an RTX 4060 or any specific GPU.

---

## 5.3 Clone and Repository Setup

```powershell
git clone <this-repository-url> Hello-Saarthi-26
cd Hello-Saarthi-26

# Main environment — backend + BGE-M3 + Qdrant client + content QA
python -m venv ..\.venv
..\.venv\Scripts\pip install -r requirements.txt
..\.venv\Scripts\pip install -r requirements-kb.txt
..\.venv\Scripts\pip install -r requirements-content-pipeline.txt

# OCR environment — PaddleOCR GPU, isolated (see §5.4 for why)
python -m venv ..\.venv-ocr
..\.venv-ocr\Scripts\pip install -r requirements-ocr-venv.txt
```

Linux/macOS equivalent (not run this session — documented, not verified
here):
```bash
git clone <this-repository-url> Hello-Saarthi-26
cd Hello-Saarthi-26
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt -r requirements-kb.txt -r requirements-content-pipeline.txt
python3 -m venv ../.venv-ocr
../.venv-ocr/bin/pip install -r requirements-ocr-venv.txt
```

**Why two virtual environments:** `paddlepaddle-gpu` (PaddleOCR's GPU
backend) and a CUDA-enabled `torch` (needed in the main venv for GPU
BGE-M3 embedding) each bundle their own private `cudnn_cnn64_9.dll`.
`paddleocr`'s own dependency chain (`paddlex` → `modelscope`)
unconditionally imports `torch` internally, so loading PaddleOCR and a
CUDA torch in the **same process** crashes on Windows with
`OSError: [WinError 127] The specified procedure could not be found.`
— confirmed by direct reproduction on this project's machine, both import
orders. Installing PaddleOCR in its own venv (where `modelscope`'s own
`torch` dependency resolves to the plain CPU build — no bundled GPU
cudnn, nothing to collide with) sidesteps this while keeping **both**
PaddleOCR and BGE-M3 on GPU. `requirements-ocr-venv.txt`'s header comment
has the full technical writeup. `scripts/build_kb_qdrant.py --run-ingestion`
runs ingestion as a subprocess through `.venv-ocr` automatically — see
`_ocr_python_executable()` in that file.

If you don't need GPU-accelerated handwriting/math OCR at all, you can
skip `.venv-ocr` entirely and just use Tesseract (the always-available
default) — see §5.12's CPU fallback note.

---

## 5.4 GPU Setup

**Main venv (`torch`, for BGE-M3):**
```powershell
..\.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu130
```
(pick the `cuXXX` tag matching your installed CUDA driver from
https://pytorch.org/get-started/locally/ — this project used `cu130`
against driver 581.42 / CUDA 13.0. `requirements.txt` already brings in a
CPU-only torch via `docling`'s own dependency chain; installing the CUDA
wheel afterward, as above, replaces it in-place.)

Verify:
```powershell
..\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

**OCR venv (`paddlepaddle-gpu`, for PaddleOCR):**
```powershell
..\.venv-ocr\Scripts\pip install https://paddle-whl.cdn.bcebos.com/stable/cu126/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp313-cp313-win_amd64.whl
```
(match `cuXXX`/`cpXXX` to your CUDA driver and Python version from
https://www.paddlepaddle.org.cn/packages/stable/ — a CPU-only machine
should install plain `pip install "paddlepaddle>=3.1"` instead; PaddleOCR
auto-detects and runs CPU-only fine either way.)

Verify:
```powershell
..\.venv-ocr\Scripts\python.exe -c "import paddle; print(paddle.device.is_compiled_with_cuda(), paddle.device.cuda.device_count())"
```

**Diagnosing a DLL conflict:** if you ever see
`OSError: [WinError 127] ... cudnn_cnn64_9.dll ...` while running
ingestion, it means PaddleOCR and a CUDA torch ended up loaded in the
**same process** — check you're invoking `scripts/ingest_notes.py` /
`scripts/ingest_videos.py` through `.venv-ocr`'s own `python.exe`, not the
main venv's (`scripts/build_kb_qdrant.py --run-ingestion` does this for
you automatically; `SAARTHI_OCR_VENV_PYTHON` overrides the auto-detected
`.venv-ocr` path if yours lives elsewhere).

**CPU fallback:** both BGE-M3 and PaddleOCR run on CPU with zero
configuration if no CUDA GPU/driver is found — `embedding_device: auto` in
`configs/kb_pipeline.yaml` and `_detect_paddleocr_device()` in
`scripts/ingest_notes.py` both check at runtime and fall back silently
with a log message. CPU PaddleOCR is measured ~24x slower than GPU on
this project's hardware (`docs/ocr-benchmark-final-report.md`); CPU
BGE-M3 embedding is slower per-batch but entirely usable for small/medium
corpora.

---

## 5.5 Model Downloads

| Model | Size | Downloaded by | Cached at |
|---|---|---|---|
| BAAI/bge-m3 | ~2.2GB | `src/knowledge_base/embedder.py` (first embedding run) | `config.models_cache_dir` = `<SAARTHI_KB_DATA_ROOT>/models` (via `HF_HOME`/Hugging Face's own cache — set explicitly so weights never land inside the repo or your user profile by accident) |
| PaddleOCR detection + recognition models | ~100MB | `paddleocr` itself, first use of `SAARTHI_HANDWRITING_OCR=paddleocr` | `~/.paddlex/official_models/` (PaddleX's own default — not currently redirected into `SAARTHI_KB_DATA_ROOT`; a documented limitation, §5.12) |
| faster-whisper model (`base` by default) | ~150MB | `faster_whisper.WhisperModel`, first video transcription | `faster-whisper`'s own Hugging Face Hub cache (`~/.cache/huggingface`) |

All three are downloaded once and reused on every subsequent run — no
network access needed after the first successful run of each stage.
Override the whisper model size with `--whisper-model` on
`scripts/ingest_videos.py` or `SAARTHI_WHISPER_MODEL`.

---

## 5.6 External Data Directory

Everything this pipeline generates lives under one configurable root,
**outside this Git repository** — set via `SAARTHI_KB_DATA_ROOT`
(`.env.kb` or your shell).

- Windows example: `E:\SaarthiData`
- Linux/macOS example: `/srv/saarthi-data` or `~/saarthi-data`

| Subdirectory | Contents | Config property |
|---|---|---|
| `source_content/ocr/` | OCR output JSONL (`scripts.ingest_notes`) | `config.ocr_output_dir` |
| `source_content/transcripts/` | Transcript JSONL (`scripts.ingest_videos`) | `config.transcripts_dir` |
| `qa_reports/` | Automated QA JSONL+CSV reports | `config.qa_reports_dir` |
| `knowledge_base/normalized/` | `normalized_docs.jsonl` | `config.normalized_dir` |
| `knowledge_base/chunks/` | `chunks.jsonl` | `config.chunks_dir` |
| `knowledge_base/embeddings/` | `embeddings.jsonl` + checkpoint | `config.embeddings_dir` |
| `knowledge_base/manifests/` | Per-run manifest JSON | `config.manifests_dir` |
| `knowledge_base/reports/` | Validation reports | `config.reports_dir` |
| `knowledge_base/exports/` | Timestamped export/backup bundles | `config.exports_dir` |
| `models/` | BGE-M3 cache | `config.models_cache_dir` |
| `logs/` | Pipeline logs | `config.logs_dir` |
| `qdrant/storage/` | Qdrant's own bind-mounted storage (via `docker-compose.kb.yml`) | — |

`config.ensure_directories()` creates every one of these automatically on
first use — never destructive, never clears existing data. Raw source
PDFs/videos stay inside the repo under `data/raw/notes/` /
`data/raw/videos/` (small, already gitignored for their actual content —
only `.gitkeep`/`README.md` are tracked).

### 5.6a Raw Input Layout: Recursive, Collision-Safe

`scripts/ingest_notes.py` discovers PDFs/images **recursively** under
`data/raw/notes/` (`.rglob`, not just the top level) — a real dataset
(e.g. a Google-Drive export) nests files under per-month/per-topic
subfolders, and earlier versions of this script only saw files directly
in the root. Two files with the **same filename in different folders**
(confirmed on this project's real data: `Apr05_2021.pdf` under both
`04_Apr/` and `April/`, genuinely different content) are automatically
disambiguated — the OCR output filename and the record's `source_id`
get prefixed with the immediate parent folder name
(`04_Apr_Apr05_2021` / `April_Apr05_2021`), so neither output nor
content ID silently collides. Files directly at the root (no subfolder)
keep their exact plain filename, unchanged from before.

---

## 5.7 Environment Configuration

```powershell
copy .env.kb.example .env.kb
notepad .env.kb   # set SAARTHI_KB_DATA_ROOT to YOUR real path
```

| Variable | Required? | Purpose |
|---|---|---|
| `SAARTHI_KB_DATA_ROOT` | **Yes** | `load_config()` raises a clear `ValueError` if unset and nothing in `configs/kb_pipeline.yaml` sets `data_root` either. |
| `QDRANT_URL` | No (defaults `http://localhost:6333`) | Self-hosted Qdrant OSS endpoint. |
| `QDRANT_API_KEY` | No (local dev) | Leave blank for an unauthenticated local instance. |
| `QDRANT_COLLECTION` | No (defaults `saarthi_knowledge_base_v1`) | — |
| `SAARTHI_KB_EMBED_DEVICE` | No (defaults `auto`) | Force `cpu`/`cuda`. |
| `SAARTHI_KB_EMBED_BATCH_SIZE` | No | — |
| `SAARTHI_HANDWRITING_OCR` | No (default: off, Tesseract-only) | `paddleocr` or `trocr` — enables the improved math/handwriting OCR fallback (§5.4/§5.10). |
| `SAARTHI_REGION_ANALYSIS` | No (default: off) | `1` enables bbox-level math/diagram region detection. |
| `SAARTHI_MATH_ANALYSIS` | No (default: off) | `1` enables per-equation-block analysis (needs PaddleOCR's per-line boxes — only has effect combined with the above). |
| `SAARTHI_OCR_VENV_PYTHON` | No | Overrides the auto-detected sibling `.venv-ocr\Scripts\python.exe`. |

**Verified, not assumed:** `.env.kb` is loaded by `scripts/env_loader.py`
(`load_env_file()`), called from `src/knowledge_base/config.py::load_config()`
(covers every KB-pipeline script) **and** from
`scripts/ingest_notes.py`/`scripts/ingest_videos.py`'s own `main()`
(covers direct invocation and the `.venv-ocr` subprocess, which never
imports `src.knowledge_base.config`). A real shell-set environment
variable always wins over `.env.kb` — `load_env_file()` only sets a
variable that isn't already present (`os.environ`-level precedence, not a
new config layer). This was tested directly this session: a fresh process
with none of the three OCR flags set picked them up correctly from
`.env.kb`, and an explicitly-set shell variable correctly overrode it.
Override one variable for a single run without touching `.env.kb`:
```powershell
$env:SAARTHI_HANDWRITING_OCR = "trocr"   # this run only
python -m scripts.build_kb_qdrant --run-ingestion
```

---

## 5.8 Qdrant Setup

```powershell
docker compose -f docker-compose.kb.yml up -d
```
Starts `qdrant/qdrant:v1.12.4`, ports 6333 (HTTP/gRPC-over-HTTP) and 6334
(gRPC), storage bind-mounted to
`<SAARTHI_KB_DATA_ROOT>/qdrant/storage` — visible and backupable outside
Docker, not a named Docker volume. The collection
(`saarthi_knowledge_base_v1`, 1024-dim, COSINE distance) is created
automatically on first upsert by `src/knowledge_base/qdrant_store.py`.

**Backup (snapshot):**
```powershell
python -m scripts.export_kb_qdrant --qdrant-snapshot
```
Triggers a real server-side snapshot and tells you the exact `curl`
command to download it into the export directory (the snapshot itself
lives on the Qdrant server's own disk until downloaded). Verify it's a
real, readable backup — don't just trust a 0 exit code:
```powershell
tar -tvf <export_dir>\<snapshot_file>.snapshot | head
```
A genuine Qdrant snapshot is a POSIX tar archive containing
`<shard>/segments/*.tar`, `<shard>/wal/*`, `config.json`, etc. — verified
directly this session against a real 32-point collection.

**Restore:** stop Qdrant, place the `.snapshot` file under the
collection's `snapshots/` directory in the bind-mounted storage path, then
`POST /collections/<name>/snapshots/recover` with
`{"location": "file:///qdrant/snapshots/<name>/<file>.snapshot"}`
(Qdrant's own snapshot-restore API — not wrapped by a script in this
repo; see Qdrant's own docs for the exact payload for your version).

**Safe cleanup of stale points** (e.g. after a `chunk_schema_version`
bump, or a re-OCR that changed `chunk_id`s): never delete-and-recreate the
whole collection. Identify stale points by comparing each point's
`chunk_schema_version` payload field against the current
`config.chunk_schema_version`, cross-check against the current
`chunks.jsonl`'s `chunk_id` set, write a report, then delete **only**
those specific point IDs:
```python
from src.knowledge_base.config import load_config
from src.knowledge_base.qdrant_store import QdrantKBStore
config = load_config()
client = QdrantKBStore(config)._ensure_client()
points, _ = client.scroll(collection_name=config.qdrant_collection, limit=10_000, with_payload=True, with_vectors=False)
stale_ids = [p.id for p in points if p.payload.get("chunk_schema_version") != config.chunk_schema_version]
client.delete(collection_name=config.qdrant_collection, points_selector=stale_ids, wait=True)
```
Take a verified snapshot backup **first** (above), and only proceed once
you've confirmed it's a readable archive and the stale/current split is
unambiguous (any point whose `chunk_id` doesn't appear in the current
`chunks.jsonl` is unidentifiable, by construction, only when its schema
version also doesn't match — in practice a schema-version mismatch alone
is a clean, unambiguous signal, as verified on this project's own
collection: 43 stale points identified and removed this way, leaving
exactly the 14 canonical ones, confirmed by `validate_kb_qdrant` reporting
zero warnings afterward and a real retrieval query returning correct
results).

**Never expose Qdrant unauthenticated to the public internet.** For
access from another device on your own network, bind Docker to that
host's IP instead of `localhost`-only and set a real `QDRANT_API_KEY`
(Qdrant supports API-key auth natively) — do not rely on network
obscurity alone.

**Qdrant Cloud as an alternative/addition to local Docker:** this
pipeline also supports `QDRANT_BACKEND=cloud` as a fully independent
second database — see `docs/LOCAL_QDRANT_PIPELINE.md` and
`docs/CLOUD_QDRANT_PIPELINE.md` for the two separate, complete runbooks,
and `scripts/migrate_qdrant_local_to_cloud.py` for the explicit, manual
migration path between them (never automatic).

---

## 5.9 Running the Complete Pipeline

**Recommended, real production pattern** (notes/PDFs only, approved-only
— verified on this project's actual dataset: 126 input files → 260
approved → 206 chunks → 206 Cloud/local Qdrant points):
```powershell
# OCR/PDF ingestion only — never touches videos, recursive (see §5.6a)
..\.venv-ocr\Scripts\python.exe -m scripts.ingest_notes --output "<DATA_ROOT>\source_content\ocr"

# QA -> normalize (approved-only by default) -> chunk -> embed -> Qdrant upsert
python -m scripts.build_kb_qdrant
```
Two separate commands, deliberately: `--run-ingestion` on
`build_kb_qdrant` also invokes `ingest_videos.py` — use it only when you
actually want video transcription too. Production uploads should also
**not** pass `--allow-pending` — only `approved` content belongs in the
KB; `pending` goes through manual review first (§5.9a), `rejected`/
`reprocess_requested` stay excluded permanently.

**Everything in one command** (OCR + video transcription + QA + build,
including unreviewed `pending` content — development/demo use only):
```powershell
python -m scripts.build_kb_qdrant --run-ingestion --allow-pending
```

**Individual stages** (same order `build_kb_qdrant` runs them in):
```powershell
# 1. Ingest notes (via .venv-ocr if SAARTHI_HANDWRITING_OCR is set)
..\.venv-ocr\Scripts\python.exe -m scripts.ingest_notes --output "<DATA_ROOT>\source_content\ocr"
# 2. Ingest videos
..\.venv-ocr\Scripts\python.exe -m scripts.ingest_videos --output "<DATA_ROOT>\source_content\transcripts"
# 3. Automated QA
python -m scripts.run_content_qa
# 4. Normalization (default: approved-only; see --allow-pending below)
python -m scripts.normalize_content_kb
# 5. Chunking
python -m scripts.chunk_content_kb
# 6. Embedding
python -m scripts.embed_chunks_kb
# 7. Qdrant upsert — done inside build_kb_qdrant.py; no standalone script
#    (run `python -m scripts.build_kb_qdrant --skip-normalize --skip-chunk --skip-embeddings`
#    minus --skip-embeddings if you need just the upsert step from existing embeddings.jsonl)
# 8. Validation
python -m scripts.validate_kb_qdrant
# 9. Export
python -m scripts.export_kb_qdrant --qdrant-snapshot
```

Linux/macOS: same commands, `python3` instead of `python`, forward
slashes in paths (not verified on Linux this session).

**Flag reference:**
| Flag | Effect |
|---|---|
| `--run-ingestion` | Also runs steps 1-2 first, through `.venv-ocr`, before the rest. Without it, the pipeline reuses whatever's already in `source_content/ocr`/`transcripts`. |
| `--allow-pending` | Normalization also includes `qa_status=pending` records. **Rejected is never included, with or without this flag.** Omit it to get the strict default: approved-only. |
| `--force-rebuild` | Re-embeds and re-upserts every chunk regardless of content-hash match — needed after an embedding-model change. |
| `--qa-force` | Re-scores every record in automated QA regardless of `qa_version`/content-hash match — needed after editing `configs/content_qa.yaml`'s weights/thresholds. |
| `--skip-qa` / `--skip-normalize` / `--skip-chunk` / `--skip-embeddings` / `--skip-qdrant` | Skip individual stages, e.g. to inspect intermediate output. |
| `--sample N` | Only the first N input files — the small-sample test below. |
| `--device auto\|cuda\|cpu` | Force the embedding device for this run. |

**Reusing vs. re-running ingestion:** omit `--run-ingestion` to reuse
existing OCR/transcript output (cheap — normalize/chunk/QA always
re-process their inputs in full, since text-only processing is fast; only
embedding and the Qdrant upsert are content-hash-gated and genuinely
skip unchanged work). Add `--run-ingestion` only when you have new or
changed raw files in `data/raw/notes`/`data/raw/videos`.

**Incremental/idempotent reruns:** a bare rerun of the same command only
re-embeds/re-uploads chunks whose content actually changed since last
time (`embeddings.checkpoint.jsonl`, keyed by `chunk_id` + content hash;
Qdrant's own `content_hash` payload field, independently). Automated QA
is idempotent the same way (`qa_version` + content hash) — verified this
session: a bare rerun of `run_content_qa` skipped all 56 already-scored
records and never reloaded any model.

---

## 5.9a Manual QA Review (`pending` content)

Auto-QA assigns `approved` (score ≥85), `pending` (60-84), or `rejected`
(<60; critical failures force this regardless of score). Only `approved`
reaches the KB by default. `pending` content needs a human — the
`qa_reviewer` role's dashboard (`/qa-review` in the web app; seed an
account with `python -m saarthi_backend.scripts.seed_qa_reviewer`) lists
every pending page/segment, side by side with the rendered source page,
an editable text box, and any equation second-opinion suggestions.
Accept/Reject/Send-for-reprocessing there flips that record's
`qa_status` directly in its OCR JSONL file — the same file
`normalize_content_kb.py` already reads, so an `accept` makes it
eligible for the **next** `build_kb_qdrant` run with zero extra steps;
nothing is pushed to Qdrant immediately from the dashboard itself.

**Improving Auto-QA's scoring without re-running OCR/embedding.** If
you find Auto-QA's calibration is wrong in a specific, evidence-backed
way (not just "I want fewer pending items") — e.g. a whole category of
pages scoring too generously or too harshly for an identifiable reason
— the fix belongs in `src/content_qa/pdf_qa.py` / `video_qa.py` (the
scoring logic), never in `configs/content_qa.yaml`'s weights/thresholds
just to shift counts. After such a fix, bump `qa_version` in
`configs/content_qa.yaml`, then re-score everything **without touching
OCR, embedding, or Qdrant at all**:
```powershell
python -m scripts.run_content_qa
```
The version bump makes every record eligible for re-evaluation
automatically (no `--force` needed); this is pure CPU, no GPU, no model
load, no network — verified on this project's real 126-file dataset:
1120 records re-scored in under a second. Only records whose new status
actually changed get rewritten; already-`approved` records are
untouched (and therefore nothing new needs to go to Qdrant unless the
fix caused *new* approvals).

---

## 5.10 Small-Sample Test

Before processing a full corpus, verify the whole chain on 1-2 small
files:
```powershell
python -m scripts.build_kb_qdrant --run-ingestion --sample 2 --allow-pending
```

Then verify each claim concretely, don't just trust exit code 0:
- **PaddleOCR actually used:** `grep '"ocr_engine": "paddleocr"' <DATA_ROOT>\source_content\ocr\*.jsonl` — only appears if `SAARTHI_HANDWRITING_OCR=paddleocr` is set and the page's Tesseract confidence wasn't already "high".
- **Tesseract fallback works:** every page without that flag set, or whose Tesseract confidence was already high, shows `"ocr_engine": "tesseract"`.
- **Math/region metadata populated:** `"math_equation_blocks"` and `"math_regions"` are non-empty only with `SAARTHI_MATH_ANALYSIS=1`/`SAARTHI_REGION_ANALYSIS=1` set, and only on pages PaddleOCR actually processed (needs its per-line boxes).
- **Video transcription succeeds:** check the `.txt`/`.jsonl` pair exists under `source_content/transcripts/` and `ingest_videos`'s own exit code / "N succeeded, 0 failed" log line.
- **Automated QA decisions generated:** `cat <DATA_ROOT>\qa_reports\latest_qa_report.jsonl` — real score/status/issues per record, or check the `counts` dict in `run_content_qa`'s own log line.
- **BGE-M3 on GPU:** the embedding stage's log line says `device='cuda'` (or check `embed_chunks_kb.run()`'s returned `device` field in the manifest).
- **Qdrant points inserted:** `python -m scripts.validate_kb_qdrant` — `qdrant_point_count` in the report.
- **Validation passes:** the same report's `warnings`/`errors` lists are empty.

Do not run the full dataset until this passes cleanly.

---

## 5.11 Full Dataset Processing

```powershell
# Notes/PDFs only, production (approved-only, no video processing):
..\.venv-ocr\Scripts\python.exe -m scripts.ingest_notes --output "<DATA_ROOT>\source_content\ocr"
python -m scripts.build_kb_qdrant
```
(no `--sample`, no `--allow-pending`, no `--run-ingestion`). Discovery
is recursive and collision-safe (§5.6a) — a nested, multi-folder export
is handled correctly, not just a flat directory of files.

**Verified on this project's real dataset**: 122 PDFs (1064 pages, 584MB,
recursively nested in dated subfolders) → 126 OCR output files → 260
approved / 607 pending / 252 rejected after Auto-QA → 206 chunks → 206
embedded, 1024-dim → 206 Qdrant points, 0 duplicates, 0 validation
warnings. The 607 `pending` need manual review (§5.9a) before they can
ever reach the KB — that is expected, not a failure.

Both `ingest_notes.py`/`ingest_videos.py` and
`run_content_qa`/`embed_chunks_kb` show a `tqdm` progress bar with
per-file/per-batch ETA. **Disk space:** OCR JSONL output is small
(kilobytes per page); the dominant cost is the BGE-M3 model cache (~2.2GB,
once) and whatever Qdrant storage your corpus's vector count needs
(scale roughly linearly with chunk count × 1024 dims × 4 bytes ×
Qdrant's own index overhead — 206 chunks was well under 1MB).

**Recovery after interruption:** just re-run the same command. Ingestion
re-processes any file whose output JSONL doesn't already exist (per-file,
not per-run, in `ingest_notes.py`/`ingest_videos.py`); QA, embedding, and
the Qdrant upsert are all content-hash/version-gated and only redo what
actually changed or is missing — nothing re-downloads a model or
re-embeds unchanged chunks on a resumed run.

---

## 5.12 Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `OSError: [WinError 127] ... cudnn_cnn64_9.dll ...` | PaddleOCR + CUDA torch loaded in the same process | Run ingestion through `.venv-ocr`, not the main venv (§5.3/5.4). |
| `SAARTHI_HANDWRITING_OCR=paddleocr` set but every page still shows `"ocr_engine": "tesseract"` | Wrong venv (main venv's torch silently breaks the paddle import, caught and logged as a warning, not a crash) | Confirm you're running `-m scripts.ingest_notes` via `.venv-ocr\Scripts\python.exe`. |
| `paddle.device.is_compiled_with_cuda()` is `False` | Installed plain `paddlepaddle` instead of `paddlepaddle-gpu`, or a CUDA/driver mismatch | Reinstall the matching GPU wheel (§5.4); CPU fallback still works, just slower. |
| `torch.cuda.is_available()` is `False` | CPU-only torch installed (the `requirements.txt`/`docling` default) | Install the CUDA wheel explicitly (§5.4). |
| Video ingestion: `open() got an unexpected keyword argument 'metadata_errors'` | PyAV ≥19 removed a kwarg `faster-whisper`'s `audio.py` still passes | Already pinned `av<19` in both `requirements-content-pipeline.txt` and `requirements-ocr-venv.txt`; if already broken, `pip install "av==18.1.0"` in the affected venv. |
| Normalization produces 0 documents despite real OCR output existing | Every record's `qa_status` is `pending`/`rejected` and `--allow-pending` wasn't passed, or automated QA genuinely rejected everything | Check `<DATA_ROOT>\qa_reports\latest_qa_report.jsonl` for real per-record reasons; pass `--allow-pending` if the content is just unreviewed, not actually bad. |
| Normalized docs exist but chunks are empty | `chunk_min_tokens`/`chunk_max_tokens` in `configs/kb_pipeline.yaml` too aggressive for very short content | Adjust the config; this is a real config/content mismatch, not a bug to work around silently. |
| `qdrant-client` version/server mismatch warning | Client pip-installed newer than the pinned `qdrant/qdrant:v1.12.4` server image | Harmless for this pipeline's basic calls; pin `qdrant-client<1.13` or bump the server image if you want it silenced. |
| `Qdrant point count does not match unique chunk count` | Stale points from a prior build/schema version | Expected after a schema bump or re-OCR; see §5.8's safe cleanup procedure — never auto-delete-and-recreate. |
| Insufficient disk space mid-run | Model cache or Qdrant storage larger than available disk | Point `SAARTHI_KB_DATA_ROOT` at a drive with more free space; nothing in this pipeline requires it to be on the same drive as the repo. |
| Missing model cache after a fresh clone | Expected — model weights are never committed to Git | First real run downloads them (§5.5); needs network access that one time. |

---

## 5.13 GitHub Contribution Workflow

**Commit:** source code (`scripts/*.py`, `src/**/*.py`), configs
(`configs/*.yaml`), requirements files, `docker-compose.kb.yml`,
`.env.kb.example` (placeholders only), tests (`tests/**`), documentation.

**Never commit:** `.env.kb` (real values, gitignored), `.venv/`/`.venv-ocr/`
(gitignored), anything under your `SAARTHI_KB_DATA_ROOT` (lives outside
the repo entirely — structurally nothing to accidentally commit), model
weights, Qdrant storage/snapshots, generated OCR/transcript/chunk/
embedding JSONL (none of that is produced inside the repo tree).

```powershell
git checkout -b feature/my-change
# make changes
python -m pytest -q                 # full suite must still pass
git status --short                  # review exactly what's staged — check
                                     # for anything that looks like real
                                     # data or a credential before adding
git add <specific files>            # never a blind `git add -A` without reviewing status first
git commit -m "..."
git push -u origin feature/my-change
gh pr create --title "..." --body "..."
```

This session did **not** commit or push anything, per explicit
instruction — the above is a workflow reference, not something already
done.

---

## 5.14 Reproducibility Checklist

- [ ] `.venv` created, `requirements.txt` + `requirements-kb.txt` +
      `requirements-content-pipeline.txt` installed.
- [ ] CUDA torch installed in `.venv` (optional) — `torch.cuda.is_available()` returns `True`, or you've accepted CPU-only.
- [ ] `.venv-ocr` created, `requirements-ocr-venv.txt` + the matching
      `paddlepaddle-gpu` wheel installed (optional) — `paddle.device.is_compiled_with_cuda()` returns `True`, or you've accepted CPU-only/Tesseract-only.
- [ ] Docker Desktop/Engine running; `docker compose -f docker-compose.kb.yml up -d` succeeds.
- [ ] `.env.kb` created from `.env.kb.example`, `SAARTHI_KB_DATA_ROOT` set to a real path outside the repo.
- [ ] A fresh shell (no manually-exported vars) can run `python -m scripts.build_kb_qdrant --sample 1 --run-ingestion --allow-pending` successfully — proves `.env.kb` is actually being read.
- [ ] Small-sample test (§5.10) passes every bullet, with real evidence (grep'd output, report contents), not just exit code 0.
- [ ] `python -m pytest -q` passes (synthetic/mocked suite — no GPU, no Docker required).
- [ ] `python -m scripts.validate_kb_qdrant` reports zero warnings/errors on the small sample.
- [ ] `python -m scripts.export_kb_qdrant --qdrant-snapshot` produces a bundle whose snapshot file is a valid, listable tar archive (`tar -tvf`).
- [ ] You understand the two-venv split and can explain why PaddleOCR and BGE-M3 don't share a process.
