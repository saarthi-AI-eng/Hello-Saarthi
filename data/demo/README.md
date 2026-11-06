# Demo walkthrough

A short, self-contained path from a raw video/notes file to a working,
queryable knowledge base. Run every command from the repo root
(`Hello-Saarthi/`) — no PYTHONPATH setup needed, these are plain
`python -m scripts.<name>` invocations. PowerShell and bash commands are
identical here.

## 1. Add sample files

Put one short video into `data/raw/videos/`. If you don't have a
transcription model installed, also drop a matching `.vtt` or `.srt`
sidecar next to it (same filename, different extension) — ingestion will
use it directly instead of running speech-to-text:

```
data/raw/videos/
    lecture_05.mp4
    lecture_05.vtt
```

Put 2-3 note images or a small PDF into `data/raw/notes/`:

```
data/raw/notes/
    notes_012.pdf
```

## 2. Run video transcription

```bash
python -m scripts.ingest_videos --input data/raw/videos --output data/processed/transcripts --course "Signals and Systems"
```

Produces `data/processed/transcripts/lecture_05.jsonl` (canonical records)
and `lecture_05.txt` (human-readable, with timestamps):

```
Lecture 05
00:12:32 --> 00:13:21
"...the sampling theorem states that..."
```

## 3. Run OCR

```bash
python -m scripts.ingest_notes --input data/raw/notes --output data/processed/ocr --course "Signals and Systems"
```

Each page becomes one record, e.g. `NOTE_012_PAGE_04`, `qa_status:
pending`, with an honest OCR confidence (or `null` if the page used a
native PDF text layer instead of OCR).

## 4. Clean

```bash
python -m scripts.clean_content --input data/processed --output data/cleaned
```

## 5. Approve demo records

Cleaning does not approve content — QA is a deliberate gate (see
[docs/content-management.md](../../docs/content-management.md)). For a
live demo, either:

- edit a few records in `data/cleaned/**/*.jsonl` and set `"qa_status":
  "approved"`, or
- skip approval and pass `--allow-pending` in step 7 — this is exactly
  what that flag is for, and it prints a visible `DEMO MODE` warning so
  the QA gate stays visible rather than silently bypassed.

## 6. Build the catalog

```bash
python -m scripts.validate_content
python -m scripts.build_catalog
```

Prints a validation report and a VIDEOS/NOTES/INDEX summary, and writes
`data/catalog/content_catalog.csv`.

## 7. Build the knowledge base

```bash
python -m scripts.build_knowledge_base --allow-pending
```

Writes `knowledge_base/unified/vector_store/`. Re-run
`python -m scripts.build_catalog` afterward and the same records now show
`indexed: yes`.

## 8. Run a retrieval query

Add a question or two to `data/evaluation/golden_questions.jsonl` (one
JSON object per line — see `data/evaluation/README.md`), then:

```bash
python -m scripts.evaluate_retrieval
```

This is the same evaluation loop used for the platform's retrieval KPIs —
it prints only what it actually measured against your demo KB, not a
claimed accuracy number.

## 9. (Optional) enable the unified KB for live agents

To have the running `notes_agent`/`video_agent` actually query this demo
KB instead of their legacy per-agent indexes, set before starting the
backend:

```bash
export SAARTHI_USE_UNIFIED_KB=true   # PowerShell: $env:SAARTHI_USE_UNIFIED_KB = "true"
```
