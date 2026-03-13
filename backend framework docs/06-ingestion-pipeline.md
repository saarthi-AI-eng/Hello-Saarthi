# Ingestion Pipeline

This document describes the **ingestion flows** for video, notes, and code content: what data is consumed, how it is processed, and what is written to the backend (DB and/or vector store). No code — only specifications.

---

## 1. Overview

Ingestion is the process of:

1. **Acquiring** raw content (video files + metadata + transcripts, scanned notes, code files).
2. **Processing** (transcription, OCR/LaTeX, chunking, embedding).
3. **Storing** in the backend: relational DB for metadata and chunk metadata, vector DB for embeddings and searchable text.

The backend may expose **ingestion APIs** (e.g. trigger by POST) or **CLI/scripts** that run periodically. The orchestrator does **not** trigger ingestion; ingestion is a separate pipeline that populates the knowledge bases.

---

## 2. Video Ingestion

### 2.1 Input

- **Source**: Downloaded video dataset (e.g. from `download_videos.py` and `load_video_dataset.py`).
- **Per video**: Video file (MP4), metadata JSON (title, description, duration, upload_date, etc.), subtitle/transcript file (e.g. .vtt).

### 2.2 Steps

1. **Read metadata**: Parse `VIDEO_ID.info.json` (or equivalent) for title, description, duration, upload_date, channel.
2. **Read transcript**: Parse .vtt (or equivalent) to get timestamped text segments. Clean timestamps and join into segments (e.g. 60-second chunks with 10-second overlap, per Karthik approach Part B).
3. **Chunk**: Produce chunks with: video_id, start_sec, end_sec, text. Preserve speaker boundaries if multi-speaker.
4. **Optional**: Extract keyframes (e.g. every 5 seconds) and generate descriptions via VLM for visual search (Phase 2+).
5. **Embed**: Run embedding model on chunk text (and optionally on keyframe descriptions).
6. **Store**:
   - **Relational**: Insert or upsert video metadata row (id, external_id, title, duration_sec, transcript_path, etc.). Insert video_transcript_chunk rows (id, video_id, start_sec, end_sec, text).
   - **Vector DB**: Upsert documents with id, text, metadata (video_id, title, start_sec, end_sec, content_type="video"). Store embedding vector.

### 2.3 Output

- **DB**: Rows in `saarthi_video_metadata` and `saarthi_video_transcript_chunks` (if used).
- **Vector store**: Documents in the video collection (or in a unified collection with content_type=video), searchable by semantic query.

### 2.4 Failure Handling

- **Missing transcript**: Log and skip or use Whisper to generate transcript if configured.
- **Embedding failure**: Log, retry with backoff; do not commit partial chunk.
- **Duplicate video_id**: Upsert by video_id (replace or skip based on policy).

### 2.5 Video structured (Option 3 — hybrid, math/ML lectures)

For **high-accuracy RAG** (tutoring, exams, precise concepts): convert selected videos to **structured notes** (textbook-style, LaTeX), chunk **by meaning** (not time), then ingest. Pipeline:

1. **Input**: `transcripts/{video_id}.json` (from Layer 1). Video title from production JSONL.
2. **Convert**: LLM rewrites transcript → textbook-style explanation; all math in LaTeX; logical sections (e.g. ## Model, ## Objective, ## Solution). Preserve intent, fix ASR errors.
3. **Chunk**: By section (one concept per chunk); if a section is long, split by paragraph under same section title. Max chunk size ~3800 chars.
4. **Store**: `vector_data_structured/{video_id}.json` with id, text, metadata (video_id, source: "video_structured", content_type: "video_structured", priority: 1.0, title, section_title, section_index). See **vector-db-text-format.txt** §2b.

**Hybrid**: Keep time-based chunks in `vector_data/` (content_type=video) for all videos. Add `vector_data_structured/` only for selected videos (manifest). At retrieval, prefer video_structured when available (e.g. by priority or content_type filter). Script: `build_structured_video_data.py` (--video-id or --manifest).

---

## 3. Notes Ingestion

### 3.1 Input

- **Source**: Digitized notes — either images (scanned pages) or already OCR’d text with LaTeX formulas.
- **Per document**: Page images or text files; optional mapping to subject (SS, DSP, PR, MBSA) and page numbers.

### 3.2 Steps

1. **OCR** (if images): Use pix2tex (LaTeX-OCR) to convert handwritten/formula content to LaTeX. Optional: LLM correction for formula fixes.
2. **Chunk**: Chunk by logical sections (not fixed token count). Keep full equations in one chunk. Include section headers as metadata. Overlap: e.g. 2 sentences between chunks.
3. **Embed**: Run embedding model on chunk text.
4. **Store**:
   - **Relational**: Insert note_chunk rows (id, source_doc_id, subject, page_number, chunk_index, text, metadata).
   - **Vector DB**: Upsert documents with id, text, metadata (source_doc_id, subject, page_number, content_type="notes").

### 3.3 Output

- **DB**: Rows in `saarthi_note_chunks`.
- **Vector store**: Documents in the notes collection (or unified with content_type=notes).

### 3.4 Failure Handling

- **OCR failure**: Log, mark document as failed; optional manual review queue.
- **Chunk too large**: Split by sentence or fallback to max token size; preserve context in metadata.

---

## 4. Code Ingestion

### 4.1 Input

- **Source**: Solved computer assignments and course code (e.g. .py files). Optional: mapping to topic and exercise number.

### 4.2 Steps

1. **Parse**: Use AST (or equivalent) to extract functions/classes. One chunk per function (or per file if small).
2. **Extract metadata**: Docstring, signature, topic/exercise from file path or config.
3. **Embed**: Run embedding model on function text (signature + docstring + body) or on docstring + signature only (configurable).
4. **Store**:
   - **Relational**: Insert code_chunk rows (id, source_file_path, function_name, language, text, topic_tags).
   - **Vector DB**: Upsert documents with id, text, metadata (source_file_path, function_name, language, content_type="code").

### 4.3 Output

- **DB**: Rows in `saarthi_code_chunks`.
- **Vector store**: Documents in the code collection (or unified with content_type=code).

---

## 5. Solved Exercises Ingestion

### 5.1 Input

- **Source**: Digitized solved exercises (problem statement + step-by-step solution). May come from notes or separate documents.

### 5.2 Steps

1. **Parse**: Extract problem statement and solution steps (structure may be manual or semi-automated).
2. **Chunk**: One chunk per problem (or per step if fine-grained retrieval is needed).
3. **Embed**: Run embedding model on problem + solution text.
4. **Store**:
   - **Relational**: Insert solved_exercise rows (id, subject, topic, problem_text, solution_text, steps).
   - **Vector store**: Upsert documents with content_type="exercise".

### 5.3 Output

- **DB**: Rows in `saarthi_solved_exercises`.
- **Vector store**: Documents searchable for problem-solving expert.

---

## 6. Ingestion Triggers

- **Batch**: Script or job that runs over Dataset/ and notes/code directories; can be scheduled (cron) or run manually.
- **API** (optional): `POST /api/v1/saarthi/ingestion/video`, `POST /api/v1/saarthi/ingestion/notes`, etc., with body specifying source path or list of IDs. Useful for re-ingesting after fixes.
- **Idempotency**: Re-running ingestion for the same source_id should be safe (upsert by source_id or id).

---

## 7. Data Dependencies

- **Video**: Depends on downloaded videos and transcripts (e.g. from `download_videos.py` and `load_video_dataset.py`).
- **Notes**: Depends on Data Team’s digitized notes (OCR/LaTeX output).
- **Code**: Depends on Product/Data Team’s code mapping (verified, executable scripts linked to topics).
- **Exercises**: Depends on digitized solved exercises.

Ingestion does **not** depend on the orchestrator or the LLM; it only depends on raw content and backend storage.
