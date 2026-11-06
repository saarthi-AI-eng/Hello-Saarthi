# data/

Working area for the content management / ingestion pipeline (see
[docs/content-management.md](../docs/content-management.md)). Data flows
one directory at a time and is never mutated in place:

```
raw/  ->  processed/  ->  cleaned/  ->  (QA approved)  ->  indexed into knowledge_base/
```

- `raw/` — original source files you drop in by hand (videos, note scans/PDFs). Never generated, never overwritten by a script.
- `processed/` — canonical `ContentRecord` JSONL produced by `scripts/ingest_videos.py` / `scripts/ingest_notes.py`, straight off the transcription/OCR engines. Still may contain artifacts (ASR repeats, OCR line-break issues).
- `cleaned/` — same JSONL shape, after `scripts/clean_content.py` has removed extraction artifacts. This is what QA reviewers and `scripts/build_catalog.py` / `scripts/build_knowledge_base.py` should read.
- `catalog/` — generated `content_catalog.csv` and validation reports (`scripts/build_catalog.py`, `scripts/validate_content.py`).
- `evaluation/` — hand-written golden question sets (`golden_questions.jsonl`) used by `scripts/evaluate_retrieval.py`, plus generated evaluation results.
- `demo/` — a self-contained walkthrough for a live demo. See [demo/README.md](demo/README.md).

Large/generated content under `raw/`, `processed/`, `cleaned/`, and `catalog/`
is git-ignored (see repo `.gitignore`) — only this directory structure and
its READMEs are tracked, via `.gitkeep` files.
