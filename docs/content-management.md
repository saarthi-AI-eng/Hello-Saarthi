# Content Management / Data Ingestion Pipeline

Audience: the Saarthi Content Management team ingesting lecture videos and
notes into the platform's knowledge base.

## 1. Pipeline architecture

```
RAW  -->  PROCESSED  -->  CLEANED  -->  QA APPROVED  -->  INDEXED
```

| Stage | Directory | Produced by | Shape |
|---|---|---|---|
| RAW | `data/raw/videos/`, `data/raw/notes/` | you, by hand | source files (mp4/pdf/png/...) |
| PROCESSED | `data/processed/transcripts/`, `data/processed/ocr/` | `scripts/ingest_videos.py`, `scripts/ingest_notes.py` | canonical `ContentRecord` JSONL, straight off ASR/OCR |
| CLEANED | `data/cleaned/transcripts/`, `data/cleaned/ocr/` | `scripts/clean_content.py` | same JSONL shape, extraction artifacts removed |
| QA APPROVED | (a status field on the cleaned record, not a new directory) | a human reviewer, by editing `qa_status` | `qa_status: approved` |
| INDEXED | `knowledge_base/unified/vector_store/` | `scripts/build_knowledge_base.py` / `scripts/update_knowledge_base.py` | FAISS vector store |

Every stage after RAW reads and writes the same canonical shape —
`scripts.schemas.ContentRecord` — as JSONL. That single contract is what
lets OCR, transcription, cleaning, and KB construction evolve
independently: swap the OCR engine, change the Whisper model size, or
rewrite the cleaner, and nothing downstream has to change as long as it
still emits/consumes `ContentRecord` JSON.

This pipeline is **additive** to the existing Saarthi codebase. It does
not modify `saarthi_backend/service/indexing_service.py` (the
per-course/per-video FAISS system backing course-material and video-transcript
chat) at all. It extends `src/tools/kb_ops.py` (the per-agent FAISS system
backing `notes_agent`/`books_agent`/`video_agent`) with one new, opt-in
retrieval path — see §10.

## 2. Directory structure

```
scripts/                   pipeline scripts (this doc's commands)
data/
  raw/videos/               drop lecture videos here (+ optional .vtt/.srt/.json sidecars)
  raw/notes/                drop scanned/handwritten notes here (+ optional .json sidecar)
  processed/transcripts/    ingest_videos.py output (JSONL + human-readable .txt)
  processed/ocr/            ingest_notes.py output (JSONL)
  cleaned/transcripts/      clean_content.py output
  cleaned/ocr/               clean_content.py output
  catalog/                  content_catalog.csv, validation_report.{json,txt}
  evaluation/                golden_questions.jsonl, evaluation_results.json,
                              ocr_ground_truth.jsonl, ocr_evaluation_results.json
  demo/                     see data/demo/README.md
knowledge_base/unified/      unified FAISS index + manifest.json + fingerprints.json
logs/ingestion_log.json      append-only log of every ingestion/build/update operation
```

Large/generated content (raw media, JSONL output, catalog CSVs, the unified
KB) is git-ignored; only the directory structure and READMEs are tracked.

## 3. Video ingestion

`scripts/ingest_videos.py` converts video into timestamp-preserving
transcript records.

```
video -> audio extraction (ffmpeg) -> speech-to-text -> segment records -> canonical metadata -> JSONL (+ .txt)
```

Speech-to-text is behind a small provider interface
(`TranscriptionProvider`) so nothing hard-codes one model. `--provider auto`
(the default) tries these in order, and **never requires an OpenAI API key**:

1. A `.vtt`/`.srt` sidecar next to the video (`lecture_05.mp4` + `lecture_05.vtt`), if present.
2. `LocalWhisperProvider` — local, via the optional `faster-whisper` package (default model `base`; override with `--whisper-model` or the `SAARTHI_WHISPER_MODEL` env var). Needs ffmpeg for audio extraction (auto-detected — see §14).
3. `OpenAITranscriptionProvider` — only reached if `faster-whisper` genuinely isn't installed; requires `OPENAI_API_KEY`.

If none of the three are available, ingestion fails with a clear error
naming exactly what's missing — it never silently produces an empty
transcript.

Course/lecture/topic are never invented: they come from (in priority
order) CLI args > a `<name>.json` manifest sidecar > filename reformatting
(e.g. `lecture_05.mp4` → lecture label `"Lecture 05"` — a relabeling of the
filename, not a guess). If none of those give a topic, `topic` is left
`null`.

```bash
python -m scripts.ingest_videos --input data/raw/videos --output data/processed/transcripts --provider auto
python -m scripts.ingest_videos --file lecture_05.mp4 --course "Signals and Systems" --lecture "Lecture 05" --topic "Fourier Transform"
```

## 4. Notes OCR

`scripts/ingest_notes.py` turns scanned/handwritten notes into per-page
records.

```
PDF/image -> page extraction -> image preprocessing -> OCR -> whitespace cleanup -> metadata -> qa_status=pending JSONL
```

For a PDF page that already has an extractable text layer, that text is
used directly — no OCR, and `metadata.ocr_confidence` is `null` (OCR
confidence is meaningless for a native text layer; it is never invented).
Only image-based/scanned pages are rendered (via `pypdfium2`, default 350
DPI — configurable with `--dpi`) and OCR'd with `pytesseract` (optional —
see `requirements-content-pipeline.txt`).

**Every page in range always produces a record — OCR ingestion never
silently drops a page.** A page whose best attempt comes back empty or
low-confidence still gets a `ContentRecord` (`metadata.low_confidence:
true`), so it shows up in `validate_content`/`build_catalog` for manual
follow-up instead of vanishing from the output. Nothing here ever
"corrects" a recognized formula based on assumptions — only what a backend
actually produced is stored.

**Multi-attempt OCR.** Each scanned page is OCR'd many times and whichever
attempt ranks best wins (never empty text over real text, then highest
confidence — see `_attempt_rank`):

1. **Five preprocessing variants** — including the completely untouched
   original render (preprocessing must never be the *only* option, since it
   can occasionally hurt a clean/faint scan): grayscale+CLAHE+deskew;
   + adaptive threshold; + Otsu threshold with a light morphological close
   (reconnects strokes binarization fragments); + unsharp-mask sharpening.
2. ...crossed with **three Tesseract page-segmentation modes** (`--psm 6`
   uniform block, `--psm 4` single column, `--psm 11` sparse text for
   scattered handwriting/equations), always with `--oem 1` (the LSTM neural
   engine) and `preserve_interword_spaces=1`. **No character whitelist is
   ever configured** — one could silently strip math symbols (π, ω, ∑, ...)
   the pipeline didn't anticipate.
3. A **region-based pass**: the winning variant is split into text bands
   (row-projection gaps, padded so boundary content isn't cut off) and each
   band is OCR'd separately, which can out-score whole-page segmentation on
   pages where handwriting/diagrams/equations are unevenly distributed.
4. An **optional handwriting-model fallback** (see below) — only tried if
   the best Tesseract/region result is still low-confidence.

`metadata.extraction_method`/`preprocessing`/`psm` record exactly which
attempt won; `metadata.ocr_confidence` is that attempt's own reported
confidence — `null` only if no backend confidence was available at all,
never a fabricated number.

**Confidence tiers** (`metadata.confidence_tier`): `high` (≥0.70), `moderate`
(0.50–0.70, usable but marked), `low` (<0.50, empty text, or unverifiable/
`null` confidence — treated conservatively, not optimistically).
`metadata.low_confidence` is `true` iff the tier is `low`, kept for
backward compatibility with existing filtering.

**Optional handwriting-specialized OCR fallback.** Set
`SAARTHI_HANDWRITING_OCR=trocr` or `SAARTHI_HANDWRITING_OCR=paddleocr` to let
a genuinely low-confidence page also try a second engine. It is never
required — if the backend's dependencies aren't available or the model
can't load, ingestion logs a warning and keeps the Tesseract result. Even
when it runs, the fallback's result only replaces Tesseract's if it
actually ranks better (see `_attempt_rank`) — it is never trusted blindly.

- `trocr`: [TrOCR](https://huggingface.co/microsoft/trocr-base-handwritten)
  (model configurable via `SAARTHI_TROCR_MODEL`), region-cropped using the
  same bands Tesseract's region pass detected — TrOCR is a line/short-text
  recognizer, not a full-page layout model. Needs `transformers`/`torch`
  (already part of this repo's dependency set for `docling`, so usually
  already installed). In practice, for dense math/diagram-heavy notes (as
  opposed to the plain handwritten prose it was trained on), it often does
  **not** outscore the multi-attempt Tesseract pass.

- `paddleocr`: runs on the whole page (it does its own text detection, so it
  doesn't need Tesseract's regions). Needs `paddleocr`+`paddlepaddle` —
  **not** installed by default; see `requirements-content-pipeline.txt` for
  why (a genuinely heavy dependency tree) and the install command. Configure
  with:
  - `SAARTHI_PADDLEOCR_LANG` (default `en`)
  - `SAARTHI_PADDLEOCR_DET_MODEL` / `SAARTHI_PADDLEOCR_REC_MODEL` (default:
    unset, letting PaddleOCR pick its own default for the language — on the
    installed PaddleOCR 3.7.0 this resolved to `PP-OCRv6_medium_det`/`_rec`,
    not a lightweight model; set these explicitly to e.g.
    `PP-OCRv5_mobile_det` / `en_PP-OCRv5_mobile_rec` for a smaller/faster
    download if that matters more than peak accuracy)
  - `SAARTHI_PADDLEOCR_DEVICE` (default `cpu`; set to e.g. `gpu:0` if
    available)
  - `SAARTHI_PADDLEOCR_MKLDNN` (default off/disabled). **Known issue**: with
    PaddlePaddle 3.3.1 on this project's Windows/CPU environment, enabling
    oneDNN (mkldnn) crashed with
    `NotImplementedError: ConvertPirAttribute2RuntimeAttribute...` during
    the PP-OCRv5 detection model's inference — set `SAARTHI_PADDLEOCR_MKLDNN=1`
    only if your environment doesn't hit this (it can be noticeably faster
    on CPU when it works).

  Per-line recognized text, confidence, and bounding box are preserved in
  `metadata.ocr_lines` (only populated for the `paddleocr` engine — Tesseract
  and TrOCR results leave it `null`). **PaddleOCR's per-line confidence and
  Tesseract's per-word confidence are not on the same scale** (different
  scoring methods entirely) — `_attempt_rank` compares them as a practical
  heuristic, not a calibrated cross-engine score; see
  `scripts/evaluate_ocr.py` below for a measured, not assumed, comparison.
  PaddleOCR's general multilingual recognition model is **not** a dedicated
  English handwriting model the way `trocr-base-handwritten` is — there is
  no English-specific "handwritten" PaddleOCR recognition model as of
  PaddleOCR 3.x. It still produced usable text on real handwritten
  engineering notes in testing (see evaluation results below), but that is
  a measured outcome for this specific content, not a guarantee.

Preprocessing itself stays conservative where it can — no destructive fixed
threshold forced on every page, a blank-margin crop that only fires when it
wouldn't touch real content — specifically to avoid destroying thin
handwritten strokes or equation symbols; the untouched-original variant is
always tried too, as an escape hatch when any processing hurts more than it helps.

```bash
python -m scripts.ingest_notes --input data/raw/notes --output data/processed/ocr --course "Signals and Systems"
python -m scripts.ingest_notes --file notes_012.pdf --page 4
```

## 5. OCR evaluation (CER/WER)

`scripts/evaluate_ocr.py` compares OCR engines against a small, manually
transcribed ground-truth set — `data/evaluation/ocr_ground_truth.jsonl`, one
JSON object per page:

```json
{"source": "data/raw/notes/FFT-Notes-images-3.pdf", "page": 1, "difficulty": "dense_notation", "description": "...", "text": "<reference transcription>"}
```

It reports Character Error Rate (CER), Word Error Rate (WER), exact-word
accuracy (`1 - WER`), exact-line accuracy (order-insensitive — whether a
reference line was recovered intact anywhere in the output, not whether line
order matched), empty-page rate, and mean processing time per page — never a
claimed accuracy number the script didn't actually measure. CER/WER are
computed with a plain Levenshtein edit distance (stdlib only); see
`_normalize_for_cer`/`_normalize_for_wer` in the script for the exact
normalization rules (whitespace/newlines collapsed for both; WER additionally
lowercases — punctuation is never stripped, since it may be meaningful
math/technical notation).

```bash
python -m scripts.evaluate_ocr                               # tesseract + paddleocr (the defaults)
python -m scripts.evaluate_ocr --engines tesseract,paddleocr,trocr
python -m scripts.evaluate_ocr --ground-truth data/evaluation/ocr_ground_truth.jsonl
```

Writes `data/evaluation/ocr_evaluation_results.json` (per-page detail +
aggregate metrics per engine) and prints a summary table. If the
ground-truth file is missing or empty, it says so and exits non-zero rather
than reporting fabricated numbers — see `data/evaluation/README.md` for how
the existing set was built and how to extend it.

## 6. Cleaning

`scripts/clean_content.py` removes extraction artifacts only — never
rewrites content. Every transformation is deterministic (regex-based, no
LLM calls).

- Transcripts: whitespace collapse, non-speech ASR tags (`[Music]`,
  `[inaudible]`, ...), collapsing accidental immediate word repeats,
  spacing-before-punctuation fixes.
- OCR: hyphenated line-break repair, duplicate-line removal, and
  repeated-header/footer removal (only when a line recurs on ≥60% of a
  document's pages and the document has ≥3 pages — never a false positive
  on a short document).

Mathematical/technical notation (`x[n]`, `x(t)`, `X(jω)`, `δ(t)`, `H(z)`,
...) is left untouched by every rule above. Timestamps, page numbers, and
paragraph/section boundaries (a single blank line) are preserved.

```bash
python -m scripts.clean_content --input data/processed --output data/cleaned
python -m scripts.clean_content --input data/processed --output data/cleaned --dry-run
```

## 7. QA process

Every record's `qa_status` starts at `pending` when ingestion writes it.
A human reviewer edits the cleaned JSONL (or a future review UI — not part
of this pipeline) to set `qa_status` to `approved` or `rejected`. There is
no separate "QA" script — QA is a status field, enforced as a **gate**
before indexing (§9). `not_required` is available for content types that
don't need review.

## 8. Catalog

`scripts/build_catalog.py` scans `data/raw/`, `data/processed/`, and
`data/cleaned/`, deduplicates by `content_id` (cleaned wins over
processed), and writes `data/catalog/content_catalog.csv` plus a console
summary (video/notes/index counts). Raw files with no processed/cleaned
output yet appear as `discovered` (or `failed`, cross-referenced against
`logs/ingestion_log.json`) placeholder rows, so the catalog always reflects
everything sitting in `data/raw/`, not just what's been ingested.

```bash
python -m scripts.build_catalog
```

## 9. Validation

`scripts/validate_content.py` checks cleaned records: non-empty text,
required fields present, video timestamp ordering/duplication, note page
numbers, OCR confidence range. Writes
`data/catalog/validation_report.{json,txt}` and exits non-zero if
anything is invalid — safe to wire into a CI/pre-indexing gate.

```bash
python -m scripts.validate_content
```

## 10. Knowledge-base building

`scripts/build_knowledge_base.py` is the **QA gate**: by default only
`processing_status == "processed"` AND `qa_status` in `{"approved",
"not_required"}` are indexed. `qa_status == "rejected"` is *never* indexed,
even in demo mode.

```bash
python -m scripts.build_knowledge_base            # production: approved-only
python -m scripts.build_knowledge_base --allow-pending   # DEMO MODE — also indexes qa_status=pending
```

`--allow-pending` prints `DEMO MODE: indexing QA-pending content.` — it
exists so a demo doesn't stall on manual QA, and it is never the default.

**Why KB construction is independent of OCR/transcription internals**: the
builder only ever reads canonical `ContentRecord` JSONL from
`data/cleaned/`. It has no idea whether a transcript came from
`faster-whisper` or a `.vtt` sidecar, or whether a note page came from a
native PDF text layer or Tesseract. That decoupling means the OCR engine,
the Whisper model, or the cleaning rules can all change independently
without touching this script.

Chunking is content-aware, not a blind fixed-size splitter:
- Video: `video → timestamp segment (the record itself) → semantic chunk`. A transcript segment is already a natural, timestamp-bounded unit; only an unusually long segment falls back to a bounded splitter, and every resulting sub-chunk keeps the segment's original `start_time`/`end_time` (never invents a sub-timestamp).
- Notes: `document → page (the record) → logical section (blank-line paragraph) → semantic chunk`. Splitting happens on paragraph boundaries first, so an equation block isn't split mid-formula unless that single paragraph is itself still too large.

Every chunk's `Document.metadata` carries: `content_id`, `content_type`,
`source_id`, `source`, `course`, `topic`, `lecture`, `page`, `start_time`,
`end_time`, `processing_status`, `qa_status`.

Output: `knowledge_base/unified/vector_store/` (FAISS) +
`knowledge_base/unified/manifest.json` (embedding model used, build time,
record/chunk counts).

### Integration with the existing per-agent knowledge bases

`src/tools/kb_ops.py` already backs the live `notes_agent`, `books_agent`,
and `video_agent` retrievers via per-agent indexes at
`knowledge_base/<agent>/vector_store/`. This pipeline does **not** replace
that. Instead, `kb_ops.get_retriever()` gained one new, opt-in branch:

```
SAARTHI_USE_UNIFIED_KB=true
```

When set, `notes_agent` and `video_agent` are routed to the unified index
above, pre-filtered by `content_type` (`{"handwritten_note", "pdf_note"}`
and `{"video_transcript"}` respectively) so an agent never sees another
agent's content. `books_agent` always uses its legacy index — this
pipeline does not ingest book content. If the unified index is missing or
empty for a given expert, `kb_ops.py` falls back to that expert's legacy
per-agent index automatically. With the flag unset (the default), behavior
is byte-for-byte unchanged from before this pipeline existed.

The embedding model used to *query* the unified index is read from its own
`manifest.json` (not hard-coded), so it always matches whatever model
`build_knowledge_base.py`/`update_knowledge_base.py` actually built it
with.

## 11. Incremental updates

`scripts/update_knowledge_base.py` avoids re-embedding unchanged content.
Each record gets a SHA-256 fingerprint over `(source, source_id, text,
metadata)` — not file mtime, since mtime changes on every checkout/copy
even when content doesn't. A record is classified NEW (no prior
fingerprint), CHANGED (fingerprint differs), or UNCHANGED (matches). For a
CHANGED record, its old chunks are deleted from the FAISS docstore before
the new ones are added, so re-running never duplicates vectors.

```bash
python -m scripts.update_knowledge_base
```

Output:

```
NEW: 3
CHANGED: 2
UNCHANGED: 95
FAILED: 0
```

## 12. Retrieval evaluation

`scripts/evaluate_retrieval.py` measures retrieval quality against
`data/evaluation/golden_questions.jsonl` — top-1/3/5 source accuracy, topic
accuracy, content-type accuracy, missing-content rate. It reports what it
actually measured; **no accuracy number is claimed unless this script
produced it**.

```bash
python -m scripts.evaluate_retrieval
```

## 13. Demo commands

See [data/demo/README.md](../data/demo/README.md) for the full walkthrough. Summary:

```bash
python -m scripts.ingest_videos --input data/raw/videos --output data/processed/transcripts
python -m scripts.ingest_notes --input data/raw/notes --output data/processed/ocr --course "Signals and Systems"
python -m scripts.clean_content --input data/processed --output data/cleaned
python -m scripts.validate_content
python -m scripts.build_catalog
python -m scripts.build_knowledge_base --allow-pending
python -m scripts.evaluate_retrieval
python -m scripts.evaluate_ocr    # optional: compare OCR engines, needs data/evaluation/ocr_ground_truth.jsonl
```

PowerShell equivalents are identical — these are plain `python -m` module
invocations, not shell scripts, so no PYTHONPATH setup or platform-specific
syntax is needed. Just run from the repo root (`Hello-Saarthi/`).

## 14. Troubleshooting

- **`ffmpeg not found`** — on Windows, `winget install --id Gyan.FFmpeg.Essentials -e` (or provide a `.vtt`/`.srt` sidecar instead, which needs no ffmpeg/model at all). Its installer only updates PATH for *new* shells; `scripts/ingest_videos.py` also auto-detects a winget-installed build directly under `%LOCALAPPDATA%\Microsoft\WinGet\Packages`, so no shell restart or PATH edit is required. For a non-default install location, set `FFMPEG_CMD` to the full path of `ffmpeg.exe`.
- **`faster-whisper is not installed`** — `pip install -r requirements-content-pipeline.txt`, or provide a `.vtt`/`.srt` sidecar, or use `--provider openai` with `OPENAI_API_KEY` set. With `--provider auto` (the default) and no sidecar, local `faster-whisper` transcription is always tried first — OpenAI is only used if `faster-whisper` genuinely isn't installed, and never required.
- **`pytesseract is not installed`** — same requirements file; also needs the Tesseract *binary* installed separately (not pip-installable — see that file's comments).
- **`tesseract is not installed or not in PATH`** (pytesseract is installed, but the binary isn't found) — on Windows, install it with `winget install --id UB-Mannheim.TesseractOCR -e` (or the wiki linked in `requirements-content-pipeline.txt`). Its installer doesn't always register itself on PATH; `scripts/ingest_notes.py` auto-detects the default install locations (`C:\Program Files\Tesseract-OCR\tesseract.exe`, the `(x86)` variant, and `%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe`) and points `pytesseract.pytesseract.tesseract_cmd` at whichever one exists, so no PATH edit or admin rights are needed. For a non-default install location, set the `TESSERACT_CMD` environment variable to the full path of `tesseract.exe` — it always takes priority.
- **`SAARTHI_HANDWRITING_OCR=paddleocr requires the paddleocr and paddlepaddle packages`** — install them separately: `pip install "paddlepaddle>=3.1" "paddleocr>=3.0"` (not in `requirements-content-pipeline.txt` — see that file's comments for why). First use downloads models to `~/.paddlex/official_models/` — needs network access once.
- **`NotImplementedError: ConvertPirAttribute2RuntimeAttribute...`** during PaddleOCR inference — a known PaddlePaddle 3.3.1 oneDNN/PIR CPU-backend crash on this project's test environment. `SAARTHI_PADDLEOCR_MKLDNN` already defaults to disabled for this reason; if you set it to `1` and hit this, unset it again.
- **`No eligible content to index`** from `build_knowledge_base.py`** — nothing has `qa_status=approved` yet. Approve some cleaned records, or pass `--allow-pending` for a demo.
- **`Unified KB enabled but unavailable for <agent>`** (log line from `kb_ops.py`) — `SAARTHI_USE_UNIFIED_KB=true` is set but `knowledge_base/unified/vector_store/` doesn't exist yet, or this agent has no unified content mapping (e.g. `books_agent`). The agent falls back to its legacy index automatically — this is informational, not an error.
- **CWD matters** — like the existing `indexing_service.py`/`kb_ops.py`, all pipeline paths are relative to the repo root (`Hello-Saarthi/`). Run every command from there.
