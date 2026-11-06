# data/processed/

Raw output of transcription/OCR, in canonical `ContentRecord` JSONL
(`scripts/schemas.py`). One `.jsonl` per source file, plus a human-readable
`.txt`/`.md` companion for transcripts.

- `transcripts/` — written by `scripts/ingest_videos.py`.
- `ocr/` — written by `scripts/ingest_notes.py`.

Not yet cleaned — expect ASR/OCR artifacts. Not indexed into the knowledge
base directly; `scripts/clean_content.py` reads from here and writes to
`data/cleaned/`.
